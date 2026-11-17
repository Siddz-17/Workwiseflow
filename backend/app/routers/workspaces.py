from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import RANK, get_current_user, require_role
from ..db import get_db
from ..models import (
    ActionItem,
    Conflict,
    Decision,
    Document,
    Invite,
    Meeting,
    Membership,
    OpenQuestion,
    Project,
    User,
    Workspace,
)
from ..schemas import (
    InviteIn,
    InviteOut,
    InviteResult,
    MemberOut,
    MeOut,
    OverviewOut,
    ProjectIn,
    ProjectOut,
    RoleIn,
    UserOut,
    WorkspaceIn,
    WorkspaceOut,
)
from .common import get_in_workspace
from .records import action_out, decision_out

router = APIRouter(prefix="/api", tags=["workspaces"])


def _ws_out(ws: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(id=ws.id, name=ws.name, created_at=ws.created_at, role=role)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Workspace, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Workspace.created_at)
    ).all()
    return MeOut(user=UserOut.model_validate(user), workspaces=[_ws_out(w, r) for w, r in rows])


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
def create_workspace(body: WorkspaceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = Workspace(name=body.name.strip(), created_by=user.id)
    db.add(ws)
    db.flush()
    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
    db.add(Project(workspace_id=ws.id, name="General", description="Default project"))
    db.commit()
    return _ws_out(ws, "owner")


@router.get("/workspaces/{ws}", response_model=WorkspaceOut)
def get_workspace(ws: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = require_role(db, user, ws)
    return _ws_out(db.get(Workspace, ws), m.role)


@router.patch("/workspaces/{ws}", response_model=WorkspaceOut)
def rename_workspace(ws: str, body: WorkspaceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = require_role(db, user, ws, "admin")
    w = db.get(Workspace, ws)
    w.name = body.name.strip()
    db.commit()
    return _ws_out(w, m.role)


@router.delete("/workspaces/{ws}", status_code=204)
def delete_workspace(ws: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "owner")
    db.delete(db.get(Workspace, ws))
    db.commit()


# ---------------------------------------------------------------------------------------------- members


@router.get("/workspaces/{ws}/members", response_model=list[MemberOut])
def list_members(ws: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    ms = db.scalars(select(Membership).where(Membership.workspace_id == ws).order_by(Membership.created_at))
    return [MemberOut(user=UserOut.model_validate(m.user), role=m.role, joined_at=m.created_at) for m in ms]


@router.post("/workspaces/{ws}/invites", response_model=InviteResult, status_code=201)
def invite(ws: str, body: InviteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    me_ = require_role(db, user, ws, "admin")
    if RANK[body.role] > RANK[me_.role]:
        raise HTTPException(403, "You can't grant a role higher than your own")
    email = body.email.lower()
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user:
        m = db.scalar(select(Membership).where(Membership.workspace_id == ws, Membership.user_id == existing_user.id))
        if m:
            raise HTTPException(409, "Already a member")
        m = Membership(workspace_id=ws, user_id=existing_user.id, role=body.role)
        db.add(m)
        db.commit()
        return InviteResult(
            status="added", member=MemberOut(user=UserOut.model_validate(existing_user), role=m.role, joined_at=m.created_at)
        )
    inv = db.scalar(select(Invite).where(Invite.workspace_id == ws, Invite.email == email))
    if inv:
        inv.role = body.role
    else:
        inv = Invite(workspace_id=ws, email=email, role=body.role, invited_by=user.id)
        db.add(inv)
    db.commit()
    return InviteResult(status="invited", invite=InviteOut.model_validate(inv))


@router.get("/workspaces/{ws}/invites", response_model=list[InviteOut])
def list_invites(ws: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "admin")
    return db.scalars(select(Invite).where(Invite.workspace_id == ws).order_by(Invite.created_at)).all()


@router.delete("/workspaces/{ws}/invites/{invite_id}", status_code=204)
def revoke_invite(ws: str, invite_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "admin")
    db.delete(get_in_workspace(db, Invite, invite_id, ws))
    db.commit()


def _owner_count(db: Session, ws: str) -> int:
    return db.scalar(
        select(func.count()).select_from(Membership).where(Membership.workspace_id == ws, Membership.role == "owner")
    )


@router.patch("/workspaces/{ws}/members/{user_id}", response_model=MemberOut)
def change_role(ws: str, user_id: str, body: RoleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    me_ = require_role(db, user, ws, "admin")
    m = db.scalar(select(Membership).where(Membership.workspace_id == ws, Membership.user_id == user_id))
    if m is None:
        raise HTTPException(404, "Member not found")
    if RANK[body.role] > RANK[me_.role] or RANK[m.role] > RANK[me_.role]:
        raise HTTPException(403, "You can't manage roles above your own")
    if m.role == "owner" and body.role != "owner" and _owner_count(db, ws) == 1:
        raise HTTPException(400, "A workspace needs at least one owner")
    m.role = body.role
    db.commit()
    return MemberOut(user=UserOut.model_validate(m.user), role=m.role, joined_at=m.created_at)


@router.delete("/workspaces/{ws}/members/{user_id}", status_code=204)
def remove_member(ws: str, user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    me_ = require_role(db, user, ws, "viewer" if user_id == user.id else "admin")
    m = db.scalar(select(Membership).where(Membership.workspace_id == ws, Membership.user_id == user_id))
    if m is None:
        raise HTTPException(404, "Member not found")
    if user_id != user.id and RANK[m.role] > RANK[me_.role]:
        raise HTTPException(403, "You can't remove someone with a higher role")
    if m.role == "owner" and _owner_count(db, ws) == 1:
        raise HTTPException(400, "Transfer ownership before the last owner leaves")
    db.delete(m)
    db.commit()


# --------------------------------------------------------------------------------------------- projects


@router.get("/workspaces/{ws}/projects", response_model=list[ProjectOut])
def list_projects(ws: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)
    return db.scalars(select(Project).where(Project.workspace_id == ws).order_by(Project.created_at)).all()


@router.post("/workspaces/{ws}/projects", response_model=ProjectOut, status_code=201)
def create_project(ws: str, body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "admin")
    p = Project(workspace_id=ws, name=body.name.strip(), description=body.description)
    db.add(p)
    db.commit()
    return p


@router.patch("/workspaces/{ws}/projects/{pid}", response_model=ProjectOut)
def update_project(ws: str, pid: str, body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "admin")
    p = get_in_workspace(db, Project, pid, ws)
    p.name, p.description = body.name.strip(), body.description
    db.commit()
    return p


@router.delete("/workspaces/{ws}/projects/{pid}", status_code=204)
def delete_project(ws: str, pid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws, "admin")
    db.delete(get_in_workspace(db, Project, pid, ws))
    db.commit()


# --------------------------------------------------------------------------------------------- overview


@router.get("/workspaces/{ws}/overview", response_model=OverviewOut)
def overview(ws: str, project_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(db, user, ws)

    def scoped(q, model):
        q = q.where(model.workspace_id == ws)
        return q.where(model.project_id == project_id) if project_id else q

    def count(model, *conds):
        return db.scalar(scoped(select(func.count()).select_from(model), model).where(*conds)) or 0

    today = date.today()
    open_ = ActionItem.status != "done"
    recent_decisions = db.scalars(
        scoped(select(Decision), Decision).where(Decision.status == "active").order_by(Decision.created_at.desc()).limit(5)
    ).all()
    upcoming = db.scalars(
        scoped(select(ActionItem), ActionItem)
        .where(open_)
        .order_by(ActionItem.due_on.is_(None), ActionItem.due_on, ActionItem.created_at.desc())
        .limit(6)
    ).all()
    recent_docs = db.scalars(
        scoped(select(Document), Document).where(Document.kind != "meeting").order_by(Document.created_at.desc()).limit(5)
    ).all()
    conflicts = db.scalar(
        select(func.count())
        .select_from(Conflict)
        .where(Conflict.workspace_id == ws, Conflict.status == "open", Conflict.is_conflict.is_(True))
    )
    return OverviewOut(
        documents=count(Document, Document.kind != "meeting"),
        meetings=count(Meeting),
        decisions_active=count(Decision, Decision.status == "active"),
        actions_open=count(ActionItem, open_),
        actions_overdue=count(ActionItem, open_, ActionItem.due_on < today),
        actions_unassigned=count(ActionItem, open_, ActionItem.owner_user_id.is_(None), or_(ActionItem.owner_name.is_(None), ActionItem.owner_name == "")),
        open_questions=count(OpenQuestion, OpenQuestion.status == "open"),
        conflicts=conflicts or 0,
        recent_decisions=[decision_out(db, d) for d in recent_decisions],
        upcoming_actions=[action_out(db, a) for a in upcoming],
        recent_documents=list(recent_docs),
    )
