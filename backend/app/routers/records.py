"""Decisions, action items, open questions and knowledge-gap endpoints."""

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_role
from ..db import get_db
from ..models import ActionItem, Conflict, Decision, Document, Meeting, OpenQuestion, User, utcnow
from ..schemas import (
    ActionIn,
    ActionOut,
    ActionPatch,
    ConflictOut,
    DecisionIn,
    DecisionOut,
    DecisionPatch,
    GapsOut,
    OutdatedOut,
    QuestionOut,
    QuestionPatch,
    StatusPatch,
)
from ..services.embeddings import get_embedder
from ..services.gaps import embed_decisions, gap_report, scan_conflicts
from ..services.textutil import cosine
from .common import check_project, get_in_workspace

router = APIRouter(prefix="/api/workspaces/{ws}", tags=["records"])


def _meeting_title(db: Session, meeting_id: str | None) -> str | None:
    if not meeting_id:
        return None
    m = db.get(Meeting, meeting_id)
    return m.title if m else None


def decision_out(db: Session, d: Decision) -> DecisionOut:
    out = DecisionOut.model_validate(d)
    out.meeting_title = _meeting_title(db, d.meeting_id)
    return out


def action_out(db: Session, a: ActionItem) -> ActionOut:
    out = ActionOut.model_validate(a)
    out.overdue = bool(a.due_on and a.status != "done" and a.due_on < date.today())
    out.meeting_title = _meeting_title(db, a.meeting_id)
    return out


# ------------------------------------------------------------------------------------------- decisions


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(
    ws: str,
    q: str | None = None,
    status: str | None = None,
    project_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(db, user, ws)
    stmt = select(Decision).where(Decision.workspace_id == ws)
    if status:
        stmt = stmt.where(Decision.status == status)
    if project_id:
        stmt = stmt.where(Decision.project_id == project_id)
    decisions = list(db.scalars(stmt.order_by(Decision.decided_on.desc().nulls_last(), Decision.created_at.desc())))
    if q and q.strip():
        # Rank by keyword match first, then semantic similarity, so "pricing" finds "move to usage-based billing".
        needle = q.lower()
        embed_decisions(db, decisions)
        db.commit()
        qv = get_embedder().embed([q], task="query")[0]
        scored = []
        for d in decisions:
            hay = f"{d.title} {d.rationale or ''} {d.approved_by or ''} {d.source_quote or ''}".lower()
            score = (1.0 if needle in hay else 0.0) + cosine(qv, d.embedding or [])
            scored.append((score, d))
        floor = 0.5 if get_embedder().name == "gemini" else 0.15
        decisions = [d for s, d in sorted(scored, key=lambda x: x[0], reverse=True) if s >= floor]
    return [decision_out(db, d) for d in decisions]


@router.post("/decisions", response_model=DecisionOut, status_code=201)
def create_decision(ws: str, body: DecisionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    d = Decision(
        workspace_id=ws,
        project_id=check_project(db, ws, body.project_id),
        title=body.title.strip(),
        rationale=body.rationale,
        approved_by=body.approved_by,
        decided_on=body.decided_on or date.today(),
        status=body.status,
        created_by=user.id,
    )
    db.add(d)
    db.flush()
    embed_decisions(db, [d])
    scan_conflicts(db, ws, only_decision_ids={d.id})
    db.commit()
    return decision_out(db, d)


@router.patch("/decisions/{did}", response_model=DecisionOut)
def update_decision(ws: str, did: str, body: DecisionPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    d = get_in_workspace(db, Decision, did, ws)
    data = body.model_dump(exclude_unset=True)
    if "superseded_by_id" in data and data["superseded_by_id"]:
        if data["superseded_by_id"] == d.id:
            raise HTTPException(400, "A decision can't supersede itself")
        get_in_workspace(db, Decision, data["superseded_by_id"], ws)
        d.status = "superseded"
    if "project_id" in data:
        data["project_id"] = check_project(db, ws, data["project_id"])
    if data.pop("confirm", None):
        d.last_confirmed_at = utcnow()
    text_changed = "title" in data or "rationale" in data
    for k, v in data.items():
        setattr(d, k, v)
    if text_changed:
        d.embedding = None
        embed_decisions(db, [d])
    if d.status in ("superseded", "revoked"):
        for c in db.scalars(
            select(Conflict).where(Conflict.workspace_id == ws, Conflict.status == "open", or_(Conflict.a_ref == d.id, Conflict.b_ref == d.id))
        ):
            c.status = "resolved"
    db.commit()
    return decision_out(db, d)


@router.delete("/decisions/{did}", status_code=204)
def delete_decision(ws: str, did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    db.delete(get_in_workspace(db, Decision, did, ws))
    db.commit()


# ---------------------------------------------------------------------------------------------- actions


@router.get("/actions", response_model=list[ActionOut])
def list_actions(
    ws: str,
    status: str | None = None,
    overdue: bool = False,
    unassigned: bool = False,
    mine: bool = False,
    project_id: str | None = None,
    meeting_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(db, user, ws)
    stmt = select(ActionItem).where(ActionItem.workspace_id == ws)
    if status == "incomplete":
        stmt = stmt.where(ActionItem.status != "done")
    elif status:
        stmt = stmt.where(ActionItem.status == status)
    if overdue:
        stmt = stmt.where(ActionItem.status != "done", ActionItem.due_on < date.today())
    if unassigned:
        stmt = stmt.where(
            ActionItem.owner_user_id.is_(None), or_(ActionItem.owner_name.is_(None), ActionItem.owner_name == "")
        )
    if mine:
        stmt = stmt.where(ActionItem.owner_user_id == user.id)
    if project_id:
        stmt = stmt.where(ActionItem.project_id == project_id)
    if meeting_id:
        stmt = stmt.where(ActionItem.meeting_id == meeting_id)
    stmt = stmt.order_by(ActionItem.status == "done", ActionItem.due_on.is_(None), ActionItem.due_on, ActionItem.created_at.desc())
    return [action_out(db, a) for a in db.scalars(stmt)]


def _resolve_owner(db: Session, ws: str, a: ActionItem, data: dict) -> None:
    if data.get("owner_user_id"):
        from ..models import Membership

        m = db.scalar(select(Membership).where(Membership.workspace_id == ws, Membership.user_id == data["owner_user_id"]))
        if m is None:
            raise HTTPException(400, "Owner must be a workspace member")
        if "owner_name" not in data:
            a.owner_name = m.user.name or m.user.email


@router.post("/actions", response_model=ActionOut, status_code=201)
def create_action(ws: str, body: ActionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    a = ActionItem(
        workspace_id=ws,
        project_id=check_project(db, ws, body.project_id),
        title=body.title.strip(),
        owner_name=body.owner_name,
        owner_user_id=body.owner_user_id,
        due_on=body.due_on,
    )
    _resolve_owner(db, ws, a, body.model_dump(exclude_unset=True))
    db.add(a)
    db.commit()
    return action_out(db, a)


@router.patch("/actions/{aid}", response_model=ActionOut)
def update_action(ws: str, aid: str, body: ActionPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    a = get_in_workspace(db, ActionItem, aid, ws)
    data = body.model_dump(exclude_unset=True)
    if "project_id" in data:
        data["project_id"] = check_project(db, ws, data["project_id"])
    _resolve_owner(db, ws, a, data)
    if data.get("owner_user_id") is None and "owner_user_id" in data and "owner_name" not in data:
        a.owner_name = None
    for k, v in data.items():
        setattr(a, k, v)
    if "status" in data:
        a.completed_at = utcnow() if a.status == "done" else None
    db.commit()
    return action_out(db, a)


@router.delete("/actions/{aid}", status_code=204)
def delete_action(ws: str, aid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    db.delete(get_in_workspace(db, ActionItem, aid, ws))
    db.commit()


# --------------------------------------------------------------------------------------- questions/gaps


@router.patch("/questions/{qid}", response_model=QuestionOut)
def update_question(
    ws: str,
    qid: str,
    body: QuestionPatch,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(db, user, ws, "member")
    q = get_in_workspace(db, OpenQuestion, qid, ws)
    q.status = body.status
    if body.answer is not None:
        q.answer = body.answer
    if body.status == "answered" and body.answer and body.save_as_document:
        # Answering a gap feeds the knowledge base, so the next person who asks gets a cited answer.
        from .documents import create_text_document

        create_text_document(
            db, ws, user, title=f"Q&A: {q.question[:200]}", content=f"Question: {q.question}\n\nAnswer: {body.answer}",
            project_id=q.project_id, kind="record", background=background,
        )
    db.commit()
    return q


@router.get("/gaps", response_model=GapsOut)
def gaps(ws: str, project_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    r = gap_report(db, ws, project_id)
    return GapsOut(
        questions=[QuestionOut.model_validate(q) for q in r["questions"]],
        outdated=[OutdatedOut(document=o["document"], reason=o["reason"]) for o in r["outdated"]],
        conflicts=[ConflictOut.model_validate(c) for c in r["conflicts"]],
    )


@router.post("/gaps/scan")
def scan(ws: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    found = scan_conflicts(db, ws)
    db.commit()
    return {"new_conflicts": found}


@router.patch("/conflicts/{cid}", response_model=ConflictOut)
def update_conflict(ws: str, cid: str, body: StatusPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    c = get_in_workspace(db, Conflict, cid, ws)
    c.status = body.status
    db.commit()
    return c


@router.post("/documents/{did}/verify")
def verify_document(ws: str, did: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "member")
    d = get_in_workspace(db, Document, did, ws)
    d.last_verified_at = utcnow()
    db.commit()
    return {"ok": True}
