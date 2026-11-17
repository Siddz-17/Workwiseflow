"""Ask-your-workspace: retrieval-augmented answers with citations, persisted as chat threads."""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ChatMessage, ChatThread, OpenQuestion, User, utcnow
from .llm import NOT_FOUND, Source, get_provider
from .retrieval import search
from .textutil import clip, stem, content_terms

CITE_RE = re.compile(r"\[(\d{1,2})\]")


def _question_key(q: str) -> str:
    return " ".join(sorted({stem(t) for t in content_terms(q)}))


def record_unanswered(db: Session, workspace_id: str, project_id: str | None, question: str, user: User) -> None:
    key = _question_key(question)
    existing = db.scalars(
        select(OpenQuestion).where(
            OpenQuestion.workspace_id == workspace_id, OpenQuestion.source == "chat", OpenQuestion.status == "open"
        )
    )
    for q in existing:
        if _question_key(q.question) == key:
            q.times_asked += 1
            return
    db.add(
        OpenQuestion(workspace_id=workspace_id, project_id=project_id, question=question, source="chat", asked_by=user.id)
    )


def ask(
    db: Session,
    user: User,
    workspace_id: str,
    question: str,
    thread_id: str | None = None,
    project_id: str | None = None,
) -> tuple[ChatThread, ChatMessage, ChatMessage]:
    settings = get_settings()
    if thread_id:
        thread = db.get(ChatThread, thread_id)
        if thread is None or thread.workspace_id != workspace_id or thread.user_id != user.id:
            raise LookupError("thread not found")
        project_id = project_id if project_id is not None else thread.project_id
    else:
        thread = ChatThread(workspace_id=workspace_id, project_id=project_id, user_id=user.id, title=clip(question, 80))
        db.add(thread)
        db.flush()

    history = [
        (m.role, m.content)
        for m in db.scalars(
            select(ChatMessage).where(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
        )
    ]
    user_msg = ChatMessage(thread_id=thread.id, role="user", content=question)
    db.add(user_msg)

    # Follow-ups like "who approved it?" need the previous question for retrieval.
    retrieval_query = question
    if history and len(content_terms(question)) < 4:
        last_q = next((c for r, c in reversed(history) if r == "user"), "")
        retrieval_query = f"{last_q} {question}"

    hits = search(db, workspace_id, retrieval_query, project_id=project_id, k=6)
    top = hits[0].score if hits else 0.0
    sources = [Source(n=i + 1, title=h.title, content=h.content) for i, h in enumerate(hits)]

    if not hits or top < settings.answer_min_score:
        raw = f"{NOT_FOUND}: Nothing in this workspace answers that yet."
    else:
        raw = get_provider().answer(question, sources, history)

    answered = not raw.strip().upper().startswith(NOT_FOUND)
    if answered:
        content = raw.strip()
        cited = sorted({int(n) for n in CITE_RE.findall(content) if 0 < int(n) <= len(hits)})
        citations = [
            {
                "n": n,
                "document_id": hits[n - 1].document_id,
                "chunk_id": hits[n - 1].chunk_id,
                "title": hits[n - 1].title,
                "kind": hits[n - 1].kind,
                "page": hits[n - 1].page,
                "snippet": clip(hits[n - 1].content, 280),
                "score": hits[n - 1].score,
            }
            for n in cited
        ]
    else:
        note = raw.split(":", 1)[1].strip() if ":" in raw else ""
        content = (
            "I couldn't find this in the workspace. "
            + (note + " " if note else "")
            + "It's been logged as an unanswered question in Knowledge gaps so someone can fill it in."
        )
        citations = []
        record_unanswered(db, workspace_id, project_id, question, user)

    assistant = ChatMessage(
        thread_id=thread.id,
        role="assistant",
        content=content,
        citations=citations,
        confidence=round(top, 3),
        answered=answered,
    )
    db.add(assistant)
    thread.updated_at = utcnow()
    db.commit()
    return thread, user_msg, assistant


def thread_message_count(db: Session, thread_id: str) -> int:
    return db.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.thread_id == thread_id)) or 0
