"""Small text helpers shared by the local (offline) providers."""

import math
import re

STOPWORDS = set(
    """a an and are as at be been but by can could did do does for from had has have how i if in into is it its
    me my of on or our so that the their them then there these they this to was we were what when where which who
    why will with would you your about should any all also just than too very not no yes us more most some such
    tell know need want please""".split()
)

WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-\.']*[a-z0-9]|[a-z0-9]")
SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n+")


def tokens(text: str) -> list[str]:
    return [t.strip(".'") for t in WORD_RE.findall(text.lower())]


def content_terms(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 1]


def stem(t: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_RE.split(text) if len(s.strip()) > 2]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def term_overlap(query: str, text: str) -> float:
    q = {stem(t) for t in content_terms(query)}
    if not q:
        return 0.0
    t = {stem(x) for x in content_terms(text)}
    return len(q & t) / len(q)


def clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"
