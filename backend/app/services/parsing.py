"""Turn uploaded files into text sections (with page numbers where the format has them) and chunks."""

import io
import re
from dataclasses import dataclass

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".markdown", ".vtt", ".srt", ".csv", ".json", ".html", ".htm"}


class UnsupportedFile(ValueError):
    pass


@dataclass
class Section:
    text: str
    page: int | None = None


def ext_of(filename: str) -> str:
    m = re.search(r"(\.[A-Za-z0-9]+)$", filename or "")
    return m[1].lower() if m else ""


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _strip_captions(text: str) -> str:
    """WebVTT/SRT → plain `Speaker: line` text."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s == "WEBVTT" or s.isdigit() or "-->" in s or s.startswith(("NOTE", "STYLE")):
            continue
        s = re.sub(r"<v\s+([^>]+)>", r"\1: ", s)
        s = re.sub(r"</?[^>]+>", "", s)
        out.append(s)
    return "\n".join(out)


def parse_file(filename: str, data: bytes) -> list[Section]:
    ext = ext_of(filename)
    if ext == ".pdf":
        import pymupdf as fitz

        with fitz.open(stream=data, filetype="pdf") as doc:
            return [Section(page.get_text("text"), i + 1) for i, page in enumerate(doc) if page.get_text("text").strip()]
    if ext == ".docx":
        import docx

        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return [Section("\n".join(parts))]
    if ext in (".vtt", ".srt"):
        return [Section(_strip_captions(_decode(data)))]
    if ext in (".html", ".htm"):
        html = _decode(data)
        html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
        html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", html)
        return [Section(re.sub(r"<[^>]+>", " ", html))]
    if ext in SUPPORTED or ext == "":
        return [Section(_decode(data))]
    raise UnsupportedFile(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED))}")


def chunk_sections(sections: list[Section], size: int = 1200, overlap: int = 200) -> list[Section]:
    """Paragraph-aware chunking. Chunks never span pages so citations can point at a page."""
    chunks: list[Section] = []
    for sec in sections:
        text = re.sub(r"[ \t]+", " ", sec.text)
        paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[-*•#]|\d+[.)])", text) if p.strip()]
        buf = ""
        for p in paras:
            while len(p) > size:  # hard-split giant paragraphs on sentence boundaries
                cut = p.rfind(". ", 0, size)
                cut = cut + 1 if cut > size // 2 else size
                if buf:
                    chunks.append(Section(buf, sec.page))
                    buf = ""
                chunks.append(Section(p[:cut].strip(), sec.page))
                p = p[max(cut - overlap, 0):].strip()
            if len(buf) + len(p) + 2 > size and buf:
                chunks.append(Section(buf, sec.page))
                tail = buf[-overlap:]
                buf = tail[tail.find(" ") + 1:] + "\n\n" + p if overlap else p
            else:
                buf = f"{buf}\n\n{p}" if buf else p
        if buf.strip():
            chunks.append(Section(buf.strip(), sec.page))
    return [c for c in chunks if len(c.text) > 20 or len(chunks) == 1]
