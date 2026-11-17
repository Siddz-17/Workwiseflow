import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..config import get_settings
from ..db import get_db
from ..models import Chunk, Document, User, new_id, utcnow
from ..schemas import ChunkOut, DocumentDetail, DocumentOut, DocumentPatch, TextDocumentIn, UserOut
from ..services.ingestion import link_versions
from ..services.jobs import enqueue_ingestion
from ..services.parsing import SUPPORTED, ext_of
from ..services.storage import get_storage
from .common import check_project, get_in_workspace

router = APIRouter(prefix="/api/workspaces/{ws}/documents", tags=["documents"])


def safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\- ]+", "_", name or "file").strip() or "file"
    return name[-120:]


def store_document(
    db: Session,
    ws: str,
    user: User,
    *,
    title: str,
    filename: str,
    data: bytes,
    mime: str,
    project_id: str | None,
    kind: str,
) -> Document:
    doc_id = new_id()
    path = f"{ws}/{doc_id}/{safe_name(filename)}"
    get_storage().put(path, data, mime)
    doc = Document(
        id=doc_id,
        workspace_id=ws,
        project_id=project_id,
        title=title,
        kind=kind,
        filename=filename,
        mime_type=mime,
        storage_path=path,
        size_bytes=len(data),
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()
    link_versions(db, doc)
    return doc


def create_text_document(
    db: Session, ws: str, user: User, *, title: str, content: str, project_id: str | None, kind: str, background
) -> Document:
    doc = store_document(
        db, ws, user, title=title, filename=f"{safe_name(title)[:80]}.md", data=content.encode("utf-8"),
        mime="text/markdown", project_id=project_id, kind=kind,
    )
    db.commit()
    enqueue_ingestion(doc.id, background)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(
    ws: str,
    project_id: str | None = None,
    kind: str | None = None,
    include_meetings: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(db, user, ws)
    q = select(Document).where(Document.workspace_id == ws)
    if project_id:
        q = q.where(Document.project_id == project_id)
    if kind:
        q = q.where(Document.kind == kind)
    elif not include_meetings:
        q = q.where(Document.kind != "meeting")
    return db.scalars(q.order_by(Document.created_at.desc())).all()


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    ws: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    project_id: str | None = Form(None),
    kind: str = Form("document"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(db, user, ws, "member")
    if kind not in ("document", "record"):
        raise HTTPException(400, "kind must be 'document' or 'record' (use /meetings for meeting notes)")
    ext = ext_of(file.filename or "")
    if ext not in SUPPORTED:
        raise HTTPException(415, f"Unsupported file type '{ext or 'unknown'}'. Supported: {', '.join(sorted(SUPPORTED))}")
    data = await file.read()
    limit = get_settings().max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(413, f"File exceeds {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "Empty file")
    doc = store_document(
        db, ws, user,
        title=(title or re.sub(r"\.[^.]+$", "", file.filename or "Untitled")).strip()[:300],
        filename=file.filename or "upload",
        data=data,
        mime=file.content_type or "application/octet-stream",
        project_id=check_project(db, ws, project_id),
        kind=kind,
    )
    db.commit()
    enqueue_ingestion(doc.id, background)
    return doc


@router.post("/text", response_model=DocumentOut, status_code=201)
def create_from_text(
    ws: str, body: TextDocumentIn, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_role(db, user, ws, "member")
    return create_text_document(
        db, ws, user, title=body.title.strip(), content=body.content, project_id=check_project(db, ws, body.project_id),
        kind=body.kind, background=background,
    )


@router.get("/{did}", response_model=DocumentDetail)
def get_document(ws: str, did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    d = get_in_workspace(db, Document, did, ws)
    chunks = db.scalars(select(Chunk).where(Chunk.document_id == d.id).order_by(Chunk.ordinal)).all()
    out = DocumentDetail.model_validate({**DocumentOut.model_validate(d).model_dump(), "chunks": [ChunkOut.model_validate(c) for c in chunks]})
    if d.uploaded_by and (u := db.get(User, d.uploaded_by)):
        out.uploader = UserOut.model_validate(u)
    return out


@router.get("/{did}/file")
def download(ws: str, did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    d = get_in_workspace(db, Document, did, ws)
    data = get_storage().get(d.storage_path)
    fname = safe_name(d.filename or d.title)
    return Response(
        data,
        media_type=d.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


@router.patch("/{did}", response_model=DocumentOut)
def update_document(ws: str, did: str, body: DocumentPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    d = get_in_workspace(db, Document, did, ws)
    data = body.model_dump(exclude_unset=True)
    if data.get("title"):
        d.title = data["title"].strip()
    if "project_id" in data:
        d.project_id = check_project(db, ws, data["project_id"])
        for c in db.scalars(select(Chunk).where(Chunk.document_id == d.id)):
            c.project_id = d.project_id
    if data.get("verified"):
        d.last_verified_at = utcnow()
    db.commit()
    return d


@router.post("/{did}/reprocess", response_model=DocumentOut)
def reprocess(ws: str, did: str, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    d = get_in_workspace(db, Document, did, ws)
    d.status = "pending"
    db.commit()
    enqueue_ingestion(d.id, background)
    return d


@router.delete("/{did}", status_code=204)
def delete_document(ws: str, did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    d = get_in_workspace(db, Document, did, ws)
    path = d.storage_path
    # Restore the previous version as current if we're deleting the latest one.
    for prev in db.scalars(select(Document).where(Document.superseded_by_id == d.id)):
        prev.superseded_by_id = None
    db.delete(d)
    db.commit()
    if path:
        try:
            get_storage().delete(path)
        except Exception:  # noqa: BLE001  (orphaned blobs are harmless; the row is gone)
            pass
