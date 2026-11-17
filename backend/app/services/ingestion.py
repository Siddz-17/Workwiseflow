"""Document ingestion pipeline: parse → chunk → embed → store; meetings additionally get structured extraction.

`process_document` is the unit of background work. It opens its own DB session so it can run in-process
(FastAPI BackgroundTasks) or on an RQ worker with identical behavior.
"""

import logging
import re
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db import session_factory
from ..models import ActionItem, Chunk, Decision, Document, Meeting, Membership, OpenQuestion, User
from .embeddings import get_embedder
from .llm import get_provider
from .parsing import chunk_sections, parse_file
from .storage import get_storage

log = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    t = re.sub(r"\.[a-z0-9]{2,5}$", "", title.lower())
    t = re.sub(r"\b(v\d+(\.\d+)*|final|draft|latest|copy|updated|rev\s*\d+)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def link_versions(db: Session, doc: Document) -> None:
    """A new upload with the same (normalized) title in the same project supersedes the previous version."""
    key = normalize_title(doc.title)
    if not key:
        return
    q = select(Document).where(
        Document.workspace_id == doc.workspace_id,
        Document.id != doc.id,
        Document.kind == doc.kind,
        Document.superseded_by_id.is_(None),
    )
    q = q.where(Document.project_id == doc.project_id) if doc.project_id else q.where(Document.project_id.is_(None))
    for prev in db.scalars(q):
        if normalize_title(prev.title) == key:
            prev.superseded_by_id = doc.id
            doc.version = max(doc.version, prev.version + 1)


def process_document(document_id: str) -> None:
    db = session_factory()()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        doc.status, doc.error = "processing", None
        db.commit()
        try:
            _ingest(db, doc)
            meeting = db.scalar(select(Meeting).where(Meeting.document_id == doc.id))
            if meeting:
                extract_meeting(db, meeting, doc)
            doc.status = "ready"
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            log.exception("Ingestion failed for %s", document_id)
            doc = db.get(Document, document_id)
            doc.status, doc.error = "failed", str(e)[:1000]
            meeting = db.scalar(select(Meeting).where(Meeting.document_id == document_id))
            if meeting:
                meeting.status, meeting.error = "failed", str(e)[:1000]
            db.commit()
    finally:
        db.close()


def _ingest(db: Session, doc: Document) -> None:
    data = get_storage().get(doc.storage_path)
    sections = parse_file(doc.filename or doc.title, data)
    full_text = "\n\n".join(s.text for s in sections).strip()
    if not full_text:
        raise ValueError("No extractable text found (scanned PDFs need OCR before upload).")
    chunks = chunk_sections(sections)
    vectors = get_embedder().embed([f"{doc.title}\n{c.text}" for c in chunks], task="document")

    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    for i, (c, v) in enumerate(zip(chunks, vectors)):
        db.add(
            Chunk(
                document_id=doc.id,
                workspace_id=doc.workspace_id,
                project_id=doc.project_id,
                ordinal=i,
                page=c.page,
                content=c.text,
                embedding=v,
            )
        )
    doc.char_count = len(full_text)
    doc.summary = get_provider().summarize(full_text, doc.title)
    db.flush()


def document_text(db: Session, document_id: str) -> str:
    return "\n\n".join(db.scalars(select(Chunk.content).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)))


def _match_member(db: Session, workspace_id: str, name: str | None) -> str | None:
    """Map a free-text owner ("Priya", "@priya", "priya@acme.com") to a workspace member."""
    if not name:
        return None
    n = name.lower().lstrip("@").strip()
    members = db.execute(
        select(User).join(Membership, Membership.user_id == User.id).where(Membership.workspace_id == workspace_id)
    ).scalars()
    for u in members:
        local = u.email.split("@")[0].lower()
        names = {u.email.lower(), local, *(u.name or "").lower().split(), (u.name or "").lower()}
        if n in names or n.split()[0] in names:
            return u.id
    return None


def extract_meeting(db: Session, meeting: Meeting, doc: Document) -> None:
    from .gaps import embed_decisions, scan_conflicts  # local import avoids a cycle

    meeting.status = "processing"
    raw = get_storage().get(doc.storage_path)
    text = "\n\n".join(s.text for s in parse_file(doc.filename or doc.title, raw))
    members = [
        u.name or u.email
        for u in db.scalars(
            select(User).join(Membership, Membership.user_id == User.id).where(Membership.workspace_id == meeting.workspace_id)
        )
    ]
    ex = get_provider().extract_meeting(text, meeting.held_on, members)

    # Re-processing replaces what this meeting produced before.
    for model in (Decision, ActionItem, OpenQuestion):
        db.execute(delete(model).where(model.meeting_id == meeting.id))

    meeting.summary = ex.summary
    meeting.attendees = ex.attendees
    new_decisions = []
    for d in ex.decisions:
        dec = Decision(
            workspace_id=meeting.workspace_id,
            project_id=meeting.project_id,
            meeting_id=meeting.id,
            title=str(d.get("title"))[:2000],
            rationale=d.get("rationale"),
            approved_by=d.get("approved_by"),
            decided_on=meeting.held_on,
            source_quote=d.get("quote"),
            created_by=meeting.created_by,
        )
        db.add(dec)
        new_decisions.append(dec)
    for a in ex.action_items:
        due = None
        if a.get("due_date"):
            try:
                due = date.fromisoformat(str(a["due_date"])[:10])
            except ValueError:
                due = None
        db.add(
            ActionItem(
                workspace_id=meeting.workspace_id,
                project_id=meeting.project_id,
                meeting_id=meeting.id,
                title=str(a.get("task"))[:2000],
                owner_name=a.get("owner"),
                owner_user_id=_match_member(db, meeting.workspace_id, a.get("owner")),
                due_on=due,
                source_quote=a.get("quote"),
            )
        )
    for q in ex.open_questions:
        db.add(
            OpenQuestion(
                workspace_id=meeting.workspace_id,
                project_id=meeting.project_id,
                meeting_id=meeting.id,
                question=q,
                source="meeting",
            )
        )
    meeting.status = "ready"
    db.flush()
    embed_decisions(db, new_decisions)
    scan_conflicts(db, meeting.workspace_id, only_decision_ids={d.id for d in new_decisions})


def count_chunks(db: Session, document_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)) or 0
