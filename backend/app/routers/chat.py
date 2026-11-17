from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import ChatMessage, ChatThread, User
from ..schemas import AskIn, AskOut, MessageOut, ThreadDetail, ThreadOut
from ..services.qa import ask
from .common import check_project

router = APIRouter(prefix="/api/workspaces/{ws}/chat", tags=["chat"])


def _own_thread(db: Session, ws: str, tid: str, user: User) -> ChatThread:
    t = db.get(ChatThread, tid)
    if t is None or t.workspace_id != ws or t.user_id != user.id:
        raise HTTPException(404, "Thread not found")
    return t


@router.get("/threads", response_model=list[ThreadOut])
def list_threads(ws: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    return db.scalars(
        select(ChatThread)
        .where(ChatThread.workspace_id == ws, ChatThread.user_id == user.id)
        .order_by(ChatThread.updated_at.desc())
    ).all()


@router.get("/threads/{tid}", response_model=ThreadDetail)
def get_thread(ws: str, tid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    t = _own_thread(db, ws, tid, user)
    msgs = db.scalars(select(ChatMessage).where(ChatMessage.thread_id == t.id).order_by(ChatMessage.created_at)).all()
    return ThreadDetail(**ThreadOut.model_validate(t).model_dump(), messages=[MessageOut.model_validate(m) for m in msgs])


@router.delete("/threads/{tid}", status_code=204)
def delete_thread(ws: str, tid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    db.delete(_own_thread(db, ws, tid, user))
    db.commit()


@router.post("/ask", response_model=AskOut)
def ask_workspace(ws: str, body: AskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    try:
        thread, q, a = ask(
            db, user, ws, body.question.strip(), thread_id=body.thread_id, project_id=check_project(db, ws, body.project_id)
        )
    except LookupError:
        raise HTTPException(404, "Thread not found") from None
    return AskOut(thread=ThreadOut.model_validate(thread), question=MessageOut.model_validate(q), answer=MessageOut.model_validate(a))
