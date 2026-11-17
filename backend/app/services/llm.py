"""LLM provider abstraction.

Every AI task goes through `AIProvider`. `GeminiProvider` calls Gemini Flash; `LocalProvider` implements the same
tasks with deterministic heuristics so the product works (in a reduced form) with no API key, in tests and offline.
If Gemini fails at runtime the call falls back to the local implementation instead of failing the request.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

import httpx

from ..config import get_settings
from .dates import resolve_due
from .textutil import clip, content_terms, sentences, stem, term_overlap, tokens

log = logging.getLogger(__name__)
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
NOT_FOUND = "NOT_FOUND"


@dataclass
class Source:
    n: int
    title: str
    content: str


@dataclass
class Extraction:
    summary: str = ""
    attendees: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)  # title, rationale, approved_by, quote
    action_items: list[dict] = field(default_factory=list)  # task, owner, due_date, quote
    open_questions: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    conflict: bool
    explanation: str


# --------------------------------------------------------------------------------------------- local


DECISION_RE = re.compile(
    r"^(?:decision|decided|agreed|resolution)\s*[:\-–]\s*|"
    r"\b(we|team|they|i)\s+(have\s+)?(decided|agreed|chose|will go with|are going with)\b|"
    r"\b(let'?s go with|final call|approved)\b",
    re.I,
)
ACTION_PREFIX_RE = re.compile(r"^(?:action(?:\s+item)?|todo|to-do|ai|task|next step|follow[- ]up)\s*[:\-–]\s*", re.I)
QUESTION_PREFIX_RE = re.compile(r"^(?:q|question|open question|unresolved|tbd)\s*[:\-–]\s*", re.I)
SPEAKER_RE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?([A-Z][a-zA-Z.'\-]+(?:\s[A-Z][a-zA-Z.'\-]+)?)\s*:\s+(.*)$")
BULLET_RE = re.compile(r"^\s*(?:[-*•▪]|\d+[.)]|\[[ xX]?\])\s*")
HEADING_RE = re.compile(r"^\s*#*\s*([A-Za-z][A-Za-z /&]{2,40}?)\s*:?\s*$")
OWNER_PATTERNS = [
    re.compile(r"@([A-Za-z][\w.\-]+)"),
    re.compile(r"\b(?:owner|assignee|assigned to|owned by)\s*[:\-]?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"),
    re.compile(r"^([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:will|to|should|needs to|is going to|owns)\b"),
    re.compile(r"\(([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\)"),
]
NON_NAMES = {"We", "Team", "Everyone", "All", "They", "I", "You", "The", "This", "That", "It", "Let", "Next", "Action"}
SECTION_KINDS = {
    "decision": ("decision", "decisions", "decisions made", "agreed", "outcomes", "resolutions"),
    "action": ("action items", "actions", "next steps", "todo", "to do", "to-do", "follow ups", "follow-ups", "tasks"),
    "question": ("open questions", "questions", "parking lot", "unresolved", "open issues", "risks and questions"),
    "other": ("agenda", "notes", "discussion", "summary", "attendees", "context", "updates"),
}
NEGATIONS = {"not", "no", "never", "don't", "won't", "shouldn't", "cannot", "can't", "without", "stop", "drop", "avoid"}


def _section_kind(heading: str) -> str | None:
    h = heading.strip().lower().rstrip(":")
    for kind, names in SECTION_KINDS.items():
        if h in names:
            return kind
    return None


def _owner(text: str, speaker: str | None) -> str | None:
    for pat in OWNER_PATTERNS:
        m = pat.search(text)
        if m and m[1] not in NON_NAMES:
            return m[1].strip()
    if speaker and re.match(r"^(i'?ll|i will|i can|i'm going to)\b", text, re.I):
        return speaker
    return None


def _clean(text: str) -> str:
    text = BULLET_RE.sub("", text)
    text = ACTION_PREFIX_RE.sub("", text)
    text = QUESTION_PREFIX_RE.sub("", text)
    text = re.sub(r"^(?:decision|decided|agreed|resolution)\s*[:\-–]\s*", "", text, flags=re.I)
    return text.strip().rstrip(".").strip()


def _looks_like_action(text: str) -> bool:
    return bool(
        ACTION_PREFIX_RE.match(text)
        or re.match(r"^@\w+", text)
        or re.match(r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\s+(?:will|to|needs to|is going to)\s+\w+", text)
        or re.match(r"^(?:i'?ll|i will)\s+\w+", text, re.I)
    )


class LocalProvider:
    name = "local"

    def answer(self, question: str, sources: list[Source], history: list[tuple[str, str]]) -> str:
        scored: list[tuple[float, int, str]] = []
        for src in sources:
            for i, sent in enumerate(sentences(src.content)):
                ov = term_overlap(question, sent)
                if ov > 0:
                    scored.append((ov - i * 0.001 - src.n * 0.01, src.n, sent))
        scored.sort(reverse=True)
        picked, seen = [], set()
        for score, n, sent in scored:
            if score < 0.25 or sent in seen:
                continue
            seen.add(sent)
            picked.append(f"{clip(sent, 320)} [{n}]")
            if len(picked) == 3:
                break
        if not picked:
            return f"{NOT_FOUND}: The workspace sources don't cover this yet."
        return "From your workspace:\n\n" + "\n\n".join(f"- {p}" for p in picked)

    def summarize(self, text: str, title: str) -> str:
        sents = [s for s in sentences(text) if len(s) > 30]
        return clip(" ".join(sents[:2]) if sents else text, 400)

    def extract_meeting(self, text: str, held_on: date, members: list[str]) -> Extraction:
        ex = Extraction()
        section: str | None = None
        speakers: list[str] = []
        lines = [l.rstrip() for l in text.splitlines()]
        prose: list[str] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            am = re.match(r"^(?:attendees|participants|present)\s*[:\-]\s*(.+)$", line, re.I)
            if am:
                ex.attendees = [a.strip() for a in re.split(r",|;| and ", am[1]) if a.strip()]
                continue
            hm = HEADING_RE.match(line)
            if hm and not BULLET_RE.match(raw) and (kind := _section_kind(hm[1])):
                section = kind
                continue
            if re.match(r"^\s*#+\s", raw):
                section = _section_kind(line.lstrip("# ")) or None
                continue
            speaker = None
            body = line
            sm = SPEAKER_RE.match(line)
            if sm and sm[1] not in NON_NAMES and not ACTION_PREFIX_RE.match(line) and not QUESTION_PREFIX_RE.match(line) and not re.match(r"^(decision|owner|due)\b", sm[1], re.I):
                speaker, body = sm[1], sm[2]
                if speaker not in speakers:
                    speakers.append(speaker)
            stripped = BULLET_RE.sub("", body).strip()
            for sent in sentences(stripped) if speaker else [stripped]:
                self._classify(ex, sent, section, speaker, held_on)
            prose.append(stripped)
        if not ex.attendees:
            ex.attendees = speakers
        ex.summary = self._meeting_summary(ex, prose)
        return ex

    def _classify(self, ex: Extraction, text: str, section: str | None, speaker: str | None, held_on: date) -> None:
        if len(text) < 4:
            return
        cleaned = _clean(text)
        if not cleaned:
            return
        if QUESTION_PREFIX_RE.match(text) or section == "question" or (
            text.endswith("?") and re.search(r"\b(still|unclear|open|unknown|who owns|tbd|not sure|need to figure)\b", text, re.I)
        ):
            ex.open_questions.append(cleaned if cleaned.endswith("?") else cleaned)
            return
        if section == "action" or _looks_like_action(text):
            due = resolve_due(text, held_on)
            owner = _owner(BULLET_RE.sub("", ACTION_PREFIX_RE.sub("", text)), speaker)
            task = re.sub(r"^@?[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\s+(?:will|to|needs to|is going to)\s+", "", cleaned)
            task = re.sub(r"^(?:i'?ll|i will)\s+", "", task, flags=re.I)
            task = re.sub(r"\s*\((?:owner|due)[^)]*\)|\s*[-–]\s*(?:owner|due)\s*:.*$", "", task, flags=re.I)
            task = re.sub(r"^@[\w.\-]+\s+(?:to\s+|will\s+)?", "", task)
            if due:
                task = re.sub(r"\s+\b(?:by|due|before)\s+[\w ,/\-]+$", "", task, flags=re.I)
                task = re.sub(
                    r"\s+(?:next week|tomorrow|today|eod|(?:by )?end of (?:the )?(?:week|month)|(?:this|next) \w+day)$",
                    "",
                    task,
                    flags=re.I,
                )
            ex.action_items.append(
                {
                    "task": task[:1].upper() + task[1:],
                    "owner": owner,
                    "due_date": due.isoformat() if due else None,
                    "quote": clip(text, 300),
                }
            )
            return
        if section == "decision" or DECISION_RE.search(text):
            title = re.sub(r"^(?:we|the team|team)\s+(?:have\s+)?(?:decided|agreed)\s+(?:to|that|on)?\s*", "", cleaned, flags=re.I)
            rationale = None
            rm = re.search(r"\b(because|since|so that|due to|as)\b\s+(.*)$", title, re.I)
            if rm and len(rm[2]) > 8:
                rationale = rm[2].strip()
                title = title[: rm.start()].rstrip(" ,;-")
            ab = re.search(r"approved by\s+([A-Z][\w ]+?)(?:[.,;]|$)", text)
            title = re.sub(r",?\s*approved by\s+[A-Z][\w ]+?$", "", title).strip()
            ex.decisions.append(
                {
                    "title": title[:1].upper() + title[1:],
                    "rationale": rationale,
                    "approved_by": ab[1].strip() if ab else speaker,
                    "quote": clip(text, 300),
                }
            )

    def _meeting_summary(self, ex: Extraction, prose: list[str]) -> str:
        bits = []
        if ex.decisions:
            bits.append(f"{len(ex.decisions)} decision(s): " + "; ".join(d["title"] for d in ex.decisions[:3]))
        if ex.action_items:
            bits.append(f"{len(ex.action_items)} action item(s)")
        if ex.open_questions:
            bits.append(f"{len(ex.open_questions)} open question(s)")
        if not bits:
            return clip(" ".join(prose[:3]), 300)
        return clip(". ".join(bits) + ".", 500)

    @staticmethod
    def _judge_pair(a: str, b: str) -> str | None:
        ta, tb = {stem(t) for t in content_terms(a)}, {stem(t) for t in content_terms(b)}
        shared = ta & tb
        # Require the two statements to be about the same thing, not merely share a word or two.
        if len(shared) < 2 or len(shared) / max(1, min(len(ta), len(tb))) < 0.5:
            return None
        if any(t in NEGATIONS for t in tokens(a)) != any(t in NEGATIONS for t in tokens(b)):
            return "One statement negates the other on the same topic."
        nums_a, nums_b = set(re.findall(r"\d+(?:\.\d+)?", a)), set(re.findall(r"\d+(?:\.\d+)?", b))
        if nums_a and nums_b and nums_a != nums_b:
            return f"Same topic, different figures ({', '.join(sorted(nums_a))} vs {', '.join(sorted(nums_b))})."
        return None

    def judge_conflict(self, a: str, b: str) -> Verdict:
        if (why := self._judge_pair(a, b)) is not None:
            return Verdict(True, why)
        # Long passages: look for a contradicting sentence pair inside them.
        for sa in sentences(a)[:40]:
            for sb in sentences(b)[:40]:
                if (why := self._judge_pair(sa, sb)) is not None:
                    return Verdict(True, f"{why} “{clip(sa, 120)}” vs “{clip(sb, 120)}”")
        return Verdict(False, "No contradiction detected.")


# -------------------------------------------------------------------------------------------- gemini


ANSWER_SYSTEM = """You are WorkflowWise, a team's institutional memory. Answer ONLY from the numbered sources.
Rules:
- Cite every factual claim with the source number in square brackets, e.g. [2] or [1][3].
- Be concise and direct; use short bullet lists for multiple items.
- If sources disagree, say so and cite both. Prefer the most recent source when they conflict.
- If the sources do not contain the answer, reply with exactly: NOT_FOUND: <one sentence on what is missing>"""

EXTRACT_SYSTEM = """You extract structured records from meeting transcripts and notes. Return JSON only, matching:
{"summary": str (2-4 sentences),
 "attendees": [str],
 "decisions": [{"title": str (the decision as a short imperative statement), "rationale": str|null, "approved_by": str|null, "quote": str (verbatim supporting line)}],
 "action_items": [{"task": str, "owner": str|null (person's name as written; null if nobody was assigned), "due_date": "YYYY-MM-DD"|null, "quote": str}],
 "open_questions": [str]}
Only include decisions that were actually made (not proposals). Resolve relative dates ("Friday", "next week") against the meeting date.
Open questions are questions raised but not answered in the meeting. Never invent owners or dates."""

CONFLICT_SYSTEM = """Decide whether two statements from the same team's records contradict each other (they cannot both be true or followed at once).
Return JSON only: {"conflict": bool, "explanation": str (one sentence)}. Different but compatible details are NOT a conflict."""


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model
        self.local = LocalProvider()

    def _generate(self, system: str, prompt: str, json_mode: bool = False, temperature: float = 0.2) -> str:
        cfg: dict = {"temperature": temperature}
        if json_mode:
            cfg["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": cfg,
        }
        r = httpx.post(
            f"{GEMINI_BASE}/models/{self.model}:generateContent",
            json=body,
            headers={"x-goog-api-key": self.api_key},
            timeout=90,
        )
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()

    @staticmethod
    def _json(text: str) -> dict:
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        return json.loads(text)

    def answer(self, question: str, sources: list[Source], history: list[tuple[str, str]]) -> str:
        src = "\n\n".join(f"[{s.n}] {s.title}\n{s.content}" for s in sources)
        hist = "\n".join(f"{r.upper()}: {clip(c, 600)}" for r, c in history[-6:])
        prompt = f"Conversation so far:\n{hist or '(none)'}\n\nSources:\n{src}\n\nQuestion: {question}"
        try:
            return self._generate(ANSWER_SYSTEM, prompt)
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini answer failed, using local fallback: %s", e)
            return self.local.answer(question, sources, history)

    def summarize(self, text: str, title: str) -> str:
        try:
            return self._generate(
                "Summarize the document in 2-3 plain sentences for a teammate deciding whether to read it.",
                f"Title: {title}\n\n{text[:24000]}",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini summarize failed: %s", e)
            return self.local.summarize(text, title)

    def extract_meeting(self, text: str, held_on: date, members: list[str]) -> Extraction:
        prompt = (
            f"Meeting date: {held_on.isoformat()} ({held_on.strftime('%A')})\n"
            f"Known team members: {', '.join(members) or 'unknown'}\n\nTranscript/notes:\n{text[:120000]}"
        )
        try:
            data = self._json(self._generate(EXTRACT_SYSTEM, prompt, json_mode=True, temperature=0.1))
            return Extraction(
                summary=data.get("summary") or "",
                attendees=[str(a) for a in data.get("attendees") or []],
                decisions=[d for d in data.get("decisions") or [] if d.get("title")],
                action_items=[a for a in data.get("action_items") or [] if a.get("task")],
                open_questions=[str(q) for q in data.get("open_questions") or [] if q],
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini extraction failed, using local fallback: %s", e)
            return self.local.extract_meeting(text, held_on, members)

    def judge_conflict(self, a: str, b: str) -> Verdict:
        try:
            data = self._json(
                self._generate(CONFLICT_SYSTEM, f"Statement A:\n{a}\n\nStatement B:\n{b}", json_mode=True, temperature=0)
            )
            return Verdict(bool(data.get("conflict")), str(data.get("explanation") or ""))
        except Exception as e:  # noqa: BLE001
            log.warning("Gemini conflict check failed: %s", e)
            return self.local.judge_conflict(a, b)


AIProvider = LocalProvider | GeminiProvider


@lru_cache
def get_provider() -> AIProvider:
    s = get_settings()
    if s.use_gemini_llm:
        if not s.gemini_api_key:
            raise RuntimeError("LLM_PROVIDER=gemini requires GEMINI_API_KEY")
        return GeminiProvider(s.gemini_api_key, s.gemini_model)
    return LocalProvider()
