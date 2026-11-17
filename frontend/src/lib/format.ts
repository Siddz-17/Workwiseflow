export function formatDate(iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = {}) {
  if (!iso) return "—";
  const d = iso.length === 10 ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", ...opts });
}

export function relativeTime(iso: string, now: Date = new Date()) {
  const s = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d}d ago`;
  return formatDate(iso);
}

/** Days until a YYYY-MM-DD date (negative = overdue). */
export function daysUntil(isoDate: string, today: Date = new Date()) {
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const [y, mo, d] = isoDate.split("-").map(Number);
  return Math.round((new Date(y, mo - 1, d).getTime() - t.getTime()) / 86_400_000);
}

export function dueLabel(isoDate: string | null, today?: Date) {
  if (!isoDate) return "No deadline";
  const n = daysUntil(isoDate, today);
  if (n < 0) return `${-n}d overdue`;
  if (n === 0) return "Due today";
  if (n === 1) return "Due tomorrow";
  return `Due in ${n}d`;
}

export function bytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export type AnswerSegment = { type: "text"; text: string } | { type: "cite"; n: number };

/** Split an answer into text and [n] citation markers so markers can render as links. */
export function splitCitations(text: string): AnswerSegment[] {
  const out: AnswerSegment[] = [];
  const re = /\[(\d{1,2})\]/g;
  let last = 0;
  for (const m of text.matchAll(re)) {
    if (m.index! > last) out.push({ type: "text", text: text.slice(last, m.index) });
    out.push({ type: "cite", n: Number(m[1]) });
    last = m.index! + m[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  return out;
}

/** Minimal block parser for answers: paragraphs and "- " bullet lists. */
export function answerBlocks(text: string): ({ type: "p"; text: string } | { type: "ul"; items: string[] })[] {
  const blocks: ({ type: "p"; text: string } | { type: "ul"; items: string[] })[] = [];
  for (const raw of text.split(/\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const bullet = /^([-*•]|\d+[.)])\s+(.*)$/.exec(line);
    if (bullet) {
      const prev = blocks[blocks.length - 1];
      if (prev && prev.type === "ul") prev.items.push(bullet[2]);
      else blocks.push({ type: "ul", items: [bullet[2]] });
    } else blocks.push({ type: "p", text: line.replace(/\*\*(.+?)\*\*/g, "$1") });
  }
  return blocks;
}

export function initials(nameOrEmail: string) {
  const base = nameOrEmail.split("@")[0];
  const parts = base.split(/[\s._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}
