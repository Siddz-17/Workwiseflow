"""Resolve informal deadlines ("by Friday", "next week", "Dec 3") relative to a meeting date."""

import calendar
import re
from datetime import date, timedelta

WEEKDAYS = {d.lower(): i for i, d in enumerate(calendar.day_name)}
WEEKDAYS.update({d.lower(): i for i, d in enumerate(calendar.day_abbr)})
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9

_MONTH = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\.?"


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _roll_forward(d: date | None, ref: date) -> date | None:
    """A month/day with no year means the next occurrence on or after the reference date."""
    if d and d < ref - timedelta(days=30):
        return _safe(d.year + 1, d.month, d.day)
    return d


def resolve_due(text: str, ref: date) -> date | None:
    t = text.lower()

    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        return _safe(int(m[1]), int(m[2]), int(m[3]))

    m = re.search(rf"\b{_MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?", t)
    if m:
        mon = MONTHS[m[1]]
        d = _safe(int(m[3]) if m[3] else ref.year, mon, int(m[2]))
        return d if m[3] else _roll_forward(d, ref)

    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}(?:\s+(\d{{4}}))?", t)
    if m:
        mon = MONTHS[m[2]]
        d = _safe(int(m[3]) if m[3] else ref.year, mon, int(m[1]))
        return d if m[3] else _roll_forward(d, ref)

    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        y = int(m[3]) if m[3] else ref.year
        y = y + 2000 if y < 100 else y
        d = _safe(y, int(m[1]), int(m[2]))
        return d if m[3] else _roll_forward(d, ref)

    if re.search(r"\b(today|eod|end of day|tonight)\b", t):
        return ref
    if "tomorrow" in t:
        return ref + timedelta(days=1)
    m = re.search(r"\bin\s+(\d+|a|one|two|three)\s+(day|week)s?\b", t)
    if m:
        n = {"a": 1, "one": 1, "two": 2, "three": 3}.get(m[1]) or int(m[1])
        return ref + timedelta(days=n * (7 if m[2] == "week" else 1))
    if re.search(r"\b(end of (the )?week|eow)\b", t):
        return ref + timedelta(days=(4 - ref.weekday()) % 7)
    if re.search(r"\b(end of (the )?month|eom)\b", t):
        return date(ref.year, ref.month, calendar.monthrange(ref.year, ref.month)[1])
    if "next week" in t:
        return ref + timedelta(days=7 - ref.weekday())  # following Monday
    m = re.search(r"\b(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri)\b", t)
    if m and re.search(r"\b(by|on|before|until|due|next|this)\s+" + m[2], t):
        ahead = (WEEKDAYS[m[2]] - ref.weekday()) % 7 or 7
        if m[1]:
            ahead += 7 if ahead < 7 else 0
        return ref + timedelta(days=ahead)
    return None
