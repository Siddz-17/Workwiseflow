from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..config import get_settings
from ..db import get_db
from ..models import ActionItem, Decision, Document, Meeting, OpenQuestion, User
from ..schemas import MeetingDetail, MeetingOut, QuestionOut
from ..services.jobs import enqueue_ingestion
from ..services.parsing import SUPPORTED, ext_of
from .common import check_project, get_in_workspace
from .documents import safe_name, store_document
from .records import action_out, decision_out

router = APIRouter(prefix="/api/workspaces/{ws}/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingOut])
def list_meetings(
    ws: str, project_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_role(db, user, ws)
    q = select(Meeting).where(Meeting.workspace_id == ws)
    if project_id:
        q = q.where(Meeting.project_id == project_id)
    return db.scalars(q.order_by(Meeting.held_on.desc(), Meeting.created_at.desc())).all()


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(
    ws: str,
    background: BackgroundTasks,
    title: str = Form(...),
    held_on: date | None = Form(None),
    project_id: str | None = Form(None),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a transcript/notes file, or paste the text. Extraction runs in the background."""
    require_role(db, user, ws, "member")
    if file is not None and file.filename:
        ext = ext_of(file.filename)
        if ext not in SUPPORTED:
            raise HTTPException(415, f"Unsupported file type '{ext}'")
        data, filename, mime = await file.read(), file.filename, file.content_type or "text/plain"
    elif text and text.strip():
        data, filename, mime = text.encode("utf-8"), f"{safe_name(title)[:80]}.txt", "text/plain"
    else:
        raise HTTPException(400, "Provide a transcript file or paste the notes")
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File too large")
    project_id = check_project(db, ws, project_id)
    held_on = held_on or date.today()
    doc = store_document(
        db, ws, user,
        title=f"{title.strip()} ({held_on.isoformat()})",
        filename=filename, data=data, mime=mime, project_id=project_id, kind="meeting",
    )
    meeting = Meeting(
        workspace_id=ws, project_id=project_id, document_id=doc.id, title=title.strip(), held_on=held_on, created_by=user.id
    )
    db.add(meeting)
    db.commit()
    enqueue_ingestion(doc.id, background)
    return meeting


@router.get("/{mid}", response_model=MeetingDetail)
def get_meeting(ws: str, mid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    m = get_in_workspace(db, Meeting, mid, ws)
    decisions = db.scalars(select(Decision).where(Decision.meeting_id == m.id).order_by(Decision.created_at)).all()
    actions = db.scalars(select(ActionItem).where(ActionItem.meeting_id == m.id).order_by(ActionItem.created_at)).all()
    questions = db.scalars(select(OpenQuestion).where(OpenQuestion.meeting_id == m.id)).all()
    return MeetingDetail(
        **MeetingOut.model_validate(m).model_dump(),
        decisions=[decision_out(db, d) for d in decisions],
        action_items=[action_out(db, a) for a in actions],
        open_questions=[QuestionOut.model_validate(q) for q in questions],
    )


@router.post("/{mid}/reprocess", response_model=MeetingOut)
def reprocess_meeting(ws: str, mid: str, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    m = get_in_workspace(db, Meeting, mid, ws)
    if not m.document_id:
        raise HTTPException(400, "This meeting has no source transcript")
    m.status = "pending"
    db.commit()
    enqueue_ingestion(m.document_id, background)
    return m


@router.delete("/{mid}", status_code=204)
def delete_meeting(ws: str, mid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    m = get_in_workspace(db, Meeting, mid, ws)
    for model in (Decision, ActionItem, OpenQuestion):
        for row in db.scalars(select(model).where(model.meeting_id == m.id)):
            db.delete(row)
    if m.document_id and (doc := db.get(Document, m.document_id)):
        db.delete(doc)
    db.delete(m)
    db.commit()
