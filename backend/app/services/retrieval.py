"""Hybrid retrieval: pgvector cosine search (or in-Python cosine on SQLite) re-ranked with keyword overlap."""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db import is_postgres
from ..models import Chunk, Document
from .embeddings import get_embedder
from .textutil import cosine, term_overlap


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    title: str
    kind: str
    page: int | None
    content: str
    score: float
    updated_at: str | None = None


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def search(
    db: Session,
    workspace_id: str,
    query: str,
    project_id: str | None = None,
    k: int = 6,
    include_superseded: bool = False,
) -> list[Hit]:
    qv = get_embedder().embed([query], task="query")[0]
    pool = k * 4
    rows: list[tuple[Chunk, Document, float]] = []

    if is_postgres(db):
        sql = """
            SELECT c.id, 1 - (c.embedding <=> CAST(:q AS vector)) AS score
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE c.workspace_id = :ws AND d.status = 'ready'
              AND (CAST(:project AS text) IS NULL OR c.project_id = CAST(:project AS text))
              AND (CAST(:sup AS boolean) OR d.superseded_by_id IS NULL)
            ORDER BY c.embedding <=> CAST(:q AS vector)
            LIMIT :pool
        """
        found = db.execute(
            text(sql),
            {"q": _vec_literal(qv), "ws": workspace_id, "project": project_id, "sup": include_superseded, "pool": pool},
        ).all()
        scores = {r[0]: float(r[1]) for r in found}
        if scores:
            q = select(Chunk, Document).join(Document, Document.id == Chunk.document_id).where(Chunk.id.in_(scores))
            rows = [(c, d, scores[c.id]) for c, d in db.execute(q).all()]
    else:
        q = (
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.workspace_id == workspace_id, Document.status == "ready")
        )
        if project_id:
            q = q.where(Chunk.project_id == project_id)
        if not include_superseded:
            q = q.where(Document.superseded_by_id.is_(None))
        rows = [(c, d, cosine(qv, c.embedding or [])) for c, d in db.execute(q).all()]
        rows.sort(key=lambda r: r[2], reverse=True)
        rows = rows[:pool]

    hits = []
    for c, d, vs in rows:
        # Blend semantic similarity with lexical overlap and the title match; keeps exact-term questions precise.
        score = 0.7 * vs + 0.25 * term_overlap(query, c.content) + 0.05 * term_overlap(query, d.title)
        hits.append(
            Hit(
                chunk_id=c.id,
                document_id=d.id,
                title=d.title,
                kind=d.kind,
                page=c.page,
                content=c.content,
                score=round(score, 4),
                updated_at=d.updated_at.isoformat() if d.updated_at else None,
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]
