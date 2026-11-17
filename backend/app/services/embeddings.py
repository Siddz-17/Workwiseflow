"""Embedding providers: Gemini embedding API, or a local hashing embedder that needs no network."""

import hashlib
import logging
import math
from functools import lru_cache
from typing import Literal, Protocol

import httpx

from ..config import get_settings
from .textutil import content_terms, stem

log = logging.getLogger(__name__)
Task = Literal["document", "query"]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str], task: Task = "document") -> list[list[float]]: ...


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


class LocalHashEmbedder:
    """Feature-hashed bag of stemmed unigrams + bigrams. Lexical, not semantic, but deterministic and free."""

    name = "local-hash"

    def __init__(self, dim: int):
        self.dim = dim

    def _bucket(self, feat: str) -> tuple[int, float]:
        h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % self.dim
        sign = 1.0 if h[4] & 1 else -1.0
        return idx, sign

    def embed(self, texts: list[str], task: Task = "document") -> list[list[float]]:
        out = []
        for text in texts:
            v = [0.0] * self.dim
            terms = [stem(t) for t in content_terms(text)]
            feats = terms + [f"{a}_{b}" for a, b in zip(terms, terms[1:])]
            for f in feats:
                i, s = self._bucket(f)
                v[i] += s * (0.5 if "_" in f else 1.0)
            out.append(_normalize(v))
        return out


class GeminiEmbedder:
    name = "gemini"

    def __init__(self, api_key: str, model: str, dim: int):
        self.api_key, self.model, self.dim = api_key, model, dim

    def embed(self, texts: list[str], task: Task = "document") -> list[list[float]]:
        task_type = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        out: list[list[float]] = []
        with httpx.Client(timeout=60) as client:
            for i in range(0, len(texts), 100):
                batch = texts[i : i + 100]
                body = {
                    "requests": [
                        {
                            "model": f"models/{self.model}",
                            "content": {"parts": [{"text": t[:8000]}]},
                            "taskType": task_type,
                            "outputDimensionality": self.dim,
                        }
                        for t in batch
                    ]
                }
                r = client.post(
                    f"{GEMINI_BASE}/models/{self.model}:batchEmbedContents",
                    json=body,
                    headers={"x-goog-api-key": self.api_key},
                )
                r.raise_for_status()
                out.extend(_normalize(e["values"]) for e in r.json()["embeddings"])
        return out


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.use_gemini_embeddings:
        if not s.gemini_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY")
        return GeminiEmbedder(s.gemini_api_key, s.gemini_embedding_model, s.embedding_dim)
    return LocalHashEmbedder(s.embedding_dim)
