from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["viewer", "member", "admin", "owner"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _utc(self):
        # SQLite drops tzinfo; every stored timestamp is UTC, so say so on the wire.
        for k, v in self.__dict__.items():
            if isinstance(v, datetime) and v.tzinfo is None:
                object.__setattr__(self, k, v.replace(tzinfo=timezone.utc))
        return self


class UserOut(ORM):
    id: str
    email: str
    name: str | None


class WorkspaceIn(ORM):
    name: str = Field(min_length=1, max_length=200)


class WorkspaceOut(ORM):
    id: str
    name: str
    created_at: datetime
    role: Role | None = None


class MeOut(ORM):
    user: UserOut
    workspaces: list[WorkspaceOut]


class MemberOut(ORM):
    user: UserOut
    role: Role
    joined_at: datetime


class InviteIn(ORM):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    role: Role = "member"


class InviteOut(ORM):
    id: str
    email: str
    role: Role
    created_at: datetime


class InviteResult(ORM):
    status: Literal["added", "invited"]
    member: MemberOut | None = None
    invite: InviteOut | None = None


class RoleIn(ORM):
    role: Role


class ProjectIn(ORM):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectOut(ORM):
    id: str
    name: str
    description: str | None
    created_at: datetime


class DocumentOut(ORM):
    id: str
    project_id: str | None
    title: str
    kind: str
    filename: str | None
    mime_type: str | None
    size_bytes: int
    status: str
    error: str | None
    summary: str | None
    char_count: int
    version: int
    superseded_by_id: str | None
    uploaded_by: str | None
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChunkOut(ORM):
    id: str
    ordinal: int
    page: int | None
    content: str


class DocumentDetail(DocumentOut):
    chunks: list[ChunkOut]
    uploader: UserOut | None = None


class DocumentPatch(ORM):
    title: str | None = None
    project_id: str | None = None
    verified: bool | None = None


class TextDocumentIn(ORM):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    project_id: str | None = None
    kind: Literal["document", "record"] = "document"


class Citation(ORM):
    n: int
    document_id: str
    chunk_id: str
    title: str
    kind: str
    page: int | None
    snippet: str
    score: float


class MessageOut(ORM):
    id: str
    role: str
    content: str
    citations: list[Citation] = []
    confidence: float | None
    answered: bool
    created_at: datetime


class ThreadOut(ORM):
    id: str
    title: str
    project_id: str | None
    created_at: datetime
    updated_at: datetime


class ThreadDetail(ThreadOut):
    messages: list[MessageOut]


class AskIn(ORM):
    question: str = Field(min_length=2, max_length=2000)
    thread_id: str | None = None
    project_id: str | None = None


class AskOut(ORM):
    thread: ThreadOut
    question: MessageOut
    answer: MessageOut


class MeetingOut(ORM):
    id: str
    project_id: str | None
    document_id: str | None
    title: str
    held_on: date
    attendees: list[str]
    summary: str | None
    status: str
    error: str | None
    created_at: datetime


class DecisionIn(ORM):
    title: str = Field(min_length=2)
    rationale: str | None = None
    approved_by: str | None = None
    decided_on: date | None = None
    project_id: str | None = None
    status: Literal["active", "proposed", "superseded", "revoked"] = "active"


class DecisionPatch(ORM):
    title: str | None = None
    rationale: str | None = None
    approved_by: str | None = None
    decided_on: date | None = None
    project_id: str | None = None
    status: Literal["active", "proposed", "superseded", "revoked"] | None = None
    superseded_by_id: str | None = None
    confirm: bool | None = None


class DecisionOut(ORM):
    id: str
    project_id: str | None
    meeting_id: str | None
    title: str
    rationale: str | None
    approved_by: str | None
    decided_on: date | None
    status: str
    superseded_by_id: str | None
    source_quote: str | None
    last_confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    meeting_title: str | None = None


class ActionIn(ORM):
    title: str = Field(min_length=2)
    owner_name: str | None = None
    owner_user_id: str | None = None
    due_on: date | None = None
    project_id: str | None = None


class ActionPatch(ORM):
    title: str | None = None
    owner_name: str | None = None
    owner_user_id: str | None = None
    due_on: date | None = None
    status: Literal["open", "in_progress", "done"] | None = None
    project_id: str | None = None


class ActionOut(ORM):
    id: str
    project_id: str | None
    meeting_id: str | None
    title: str
    owner_name: str | None
    owner_user_id: str | None
    due_on: date | None
    status: str
    source_quote: str | None
    completed_at: datetime | None
    created_at: datetime
    overdue: bool = False
    meeting_title: str | None = None


class QuestionOut(ORM):
    id: str
    project_id: str | None
    meeting_id: str | None
    question: str
    source: str
    times_asked: int
    status: str
    answer: str | None
    created_at: datetime


class QuestionPatch(ORM):
    status: Literal["open", "answered", "dismissed"]
    answer: str | None = None
    save_as_document: bool = False


class MeetingDetail(MeetingOut):
    decisions: list[DecisionOut]
    action_items: list[ActionOut]
    open_questions: list[QuestionOut]


class ConflictOut(ORM):
    id: str
    kind: str
    a_ref: str
    b_ref: str
    a_label: str
    b_label: str
    a_text: str
    b_text: str
    explanation: str
    status: str
    created_at: datetime


class OutdatedOut(ORM):
    document: DocumentOut
    reason: str


class GapsOut(ORM):
    questions: list[QuestionOut]
    outdated: list[OutdatedOut]
    conflicts: list[ConflictOut]


class StatusPatch(ORM):
    status: Literal["open", "resolved", "dismissed"]


class OverviewOut(ORM):
    documents: int
    meetings: int
    decisions_active: int
    actions_open: int
    actions_overdue: int
    actions_unassigned: int
    open_questions: int
    conflicts: int
    recent_decisions: list[DecisionOut]
    upcoming_actions: list[ActionOut]
    recent_documents: list[DocumentOut]
