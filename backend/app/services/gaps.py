"""Knowledge gap detection: unanswered questions, outdated documents and conflicting information."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Chunk, Conflict, Decision, Document, OpenQuestion
from .embeddings import get_embedder
from .llm import get_provider
from .textutil import clip, cosine

MAX_JUDGEMENTS_PER_SCAN = 25


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def embed_decisions(db: Session, decisions: list[Decision]) -> None:
    todo = [d for d in decisions if d.embedding is None]
    if not todo:
        return
    vecs = get_embedder().embed([f"{d.title}. {d.rationale or ''}" for d in todo], task="document")
    for d, v in zip(todo, vecs):
        d.embedding = v
    db.flush()


def _threshold() -> float:
    # Semantic embeddings put same-topic statements far closer together than hashed bag-of-words vectors do.
    return 0.80 if get_settings().use_gemini_embeddings else 0.35


def _ordered(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def scan_conflicts(db: Session, workspace_id: str, only_decision_ids: set[str] | None = None) -> int:
    """Find candidate pairs by embedding similarity, then ask the provider whether they truly contradict.

    Every judged pair is stored (also non-conflicts, with is_conflict=False) so it is never re-judged.
    """
    provider = get_provider()
    known = {
        (c.a_ref, c.b_ref) for c in db.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id))
    }
    threshold = _threshold()
    candidates: list[tuple[float, str, object, object]] = []

    decisions = list(
        db.scalars(select(Decision).where(Decision.workspace_id == workspace_id, Decision.status.in_(("active", "proposed"))))
    )
    embed_decisions(db, decisions)
    for i, a in enumerate(decisions):
        for b in decisions[i + 1 :]:
            if only_decision_ids and a.id not in only_decision_ids and b.id not in only_decision_ids:
                continue
            if a.project_id and b.project_id and a.project_id != b.project_id:
                continue
            if _ordered(a.id, b.id) in known:
                continue
            sim = cosine(a.embedding or [], b.embedding or [])
            if sim >= threshold:
                candidates.append((sim, "decision", a, b))

    if only_decision_ids is None:
        rows = db.execute(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(
                Chunk.workspace_id == workspace_id,
                Document.status == "ready",
                Document.superseded_by_id.is_(None),
                Document.kind != "meeting",
            )
            .limit(1500)
        ).all()
        # Passages mix several statements, which dilutes similarity; the judge then checks them sentence by sentence.
        doc_thr = 0.75 if get_settings().use_gemini_embeddings else 0.25
        for i, (ca, da) in enumerate(rows):
            for cb, db_ in rows[i + 1 :]:
                if ca.document_id == cb.document_id or _ordered(ca.id, cb.id) in known:
                    continue
                if da.project_id and db_.project_id and da.project_id != db_.project_id:
                    continue
                sim = cosine(ca.embedding or [], cb.embedding or [])
                if sim >= doc_thr:
                    candidates.append((sim, "document", (ca, da), (cb, db_)))

    candidates.sort(key=lambda c: c[0], reverse=True)
    found = 0
    for _, kind, a, b in candidates[:MAX_JUDGEMENTS_PER_SCAN]:
        if kind == "decision":
            a_ref, b_ref = _ordered(a.id, b.id)
            first, second = (a, b) if a.id == a_ref else (b, a)
            a_text, b_text = f"{first.title}. {first.rationale or ''}".strip(), f"{second.title}. {second.rationale or ''}".strip()
            a_label = f"Decision · {first.decided_on or ''}".strip(" ·")
            b_label = f"Decision · {second.decided_on or ''}".strip(" ·")
        else:
            (ca, da), (cb, dbb) = a, b
            a_ref, b_ref = _ordered(ca.id, cb.id)
            (c1, d1), (c2, d2) = ((ca, da), (cb, dbb)) if ca.id == a_ref else ((cb, dbb), (ca, da))
            a_text, b_text = clip(c1.content, 900), clip(c2.content, 900)
            a_label = f"{d1.title}" + (f" · p.{c1.page}" if c1.page else "")
            b_label = f"{d2.title}" + (f" · p.{c2.page}" if c2.page else "")
        verdict = provider.judge_conflict(a_text, b_text)
        db.add(
            Conflict(
                workspace_id=workspace_id,
                kind=kind,
                a_ref=a_ref,
                b_ref=b_ref,
                a_label=a_label,
                b_label=b_label,
                a_text=a_text,
                b_text=b_text,
                explanation=verdict.explanation,
                is_conflict=verdict.conflict,
                status="open" if verdict.conflict else "dismissed",
            )
        )
        known.add((a_ref, b_ref))
        found += int(verdict.conflict)
    db.flush()
    return found


def gap_report(db: Session, workspace_id: str, project_id: str | None = None) -> dict:
    s = get_settings()
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(days=s.stale_after_days)

    qq = select(OpenQuestion).where(OpenQuestion.workspace_id == workspace_id, OpenQuestion.status == "open")
    dq = select(Document).where(Document.workspace_id == workspace_id, Document.status == "ready")
    if project_id:
        qq = qq.where(OpenQuestion.project_id == project_id)
        dq = dq.where(Document.project_id == project_id)
    questions = list(db.scalars(qq.order_by(OpenQuestion.times_asked.desc(), OpenQuestion.created_at.desc())))

    outdated = []
    titles = {d.id: d.title for d in db.scalars(select(Document).where(Document.workspace_id == workspace_id))}
    for d in db.scalars(dq):
        if d.superseded_by_id:
            outdated.append({"document": d, "reason": f"Superseded by a newer version: {titles.get(d.superseded_by_id, '')}"})
            continue
        last = max(filter(None, [as_utc(d.updated_at), as_utc(d.last_verified_at)]))
        if last < stale_before:
            outdated.append({"document": d, "reason": f"Not updated or verified in {(now - last).days} days"})

    conflicts = list(
        db.scalars(
            select(Conflict)
            .where(Conflict.workspace_id == workspace_id, Conflict.status == "open", Conflict.is_conflict.is_(True))
            .order_by(Conflict.created_at.desc())
        )
    )
    return {"questions": questions, "outdated": outdated, "conflicts": conflicts}
