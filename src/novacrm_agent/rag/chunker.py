"""Semantic-by-heading chunker (P4-D4).

The corpus docs (data/knowledge_base/docs/*.md) are authored with YAML front-matter
(doc_title, doc_type) and `##` section headings. We split on those headings so each chunk
is one coherent section, and attach metadata {doc_title, doc_type, section, source} to every
chunk. That metadata is what enables the *second* retrieval defense in P4-D4 — filtering by
doc_type alongside vector similarity.

Deliberately hand-rolled (no markdown/frontmatter library): the format is ours and small, and
keeping the parse visible is the point of the framework-free pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_CORPUS_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge_base" / "docs"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit: a single `##` section of a doc, plus its metadata."""

    chunk_id: str          # stable id, e.g. "02-plans-and-pricing::plan-prices"
    text: str              # heading + body, what we embed and hand back to the agent
    doc_title: str
    doc_type: str
    section: str
    source: str            # filename, e.g. "02-plans-and-pricing.md"

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "doc_title": self.doc_title,
            "doc_type": self.doc_type,
            "section": self.section,
            "source": self.source,
        }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter dict, body). Frontmatter is flat `key: value` lines."""
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm, raw[m.end():]


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split a doc body into (section_heading, section_body) pairs on `## ` headings.

    The leading `# Title` H1 and any text before the first `##` are folded into an
    "Overview" section so no content is dropped.
    """
    lines = body.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Overview"
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            continue  # drop the H1 title line (already captured as doc_title)
        if line.startswith("## "):
            if current_lines and any(s.strip() for s in current_lines):
                sections.append((current_heading, current_lines))
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines and any(s.strip() for s in current_lines):
        sections.append((current_heading, current_lines))

    return [(h, "\n".join(b).strip()) for h, b in sections]


def chunk_document(path: Path) -> list[Chunk]:
    """Parse one markdown doc into heading-bounded chunks with metadata."""
    raw = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(raw)
    doc_title = fm.get("doc_title", path.stem)
    doc_type = fm.get("doc_type", "unknown")
    stem = path.stem

    chunks: list[Chunk] = []
    for heading, section_body in _split_sections(body):
        if not section_body:
            continue
        # Embed/return the heading with the body so the section is self-describing.
        text = f"{doc_title} — {heading}\n\n{section_body}"
        chunks.append(
            Chunk(
                chunk_id=f"{stem}::{_slug(heading)}",
                text=text,
                doc_title=doc_title,
                doc_type=doc_type,
                section=heading,
                source=path.name,
            )
        )
    return chunks


def load_corpus(corpus_dir: Path | None = None) -> list[Chunk]:
    """Chunk every doc in the corpus (excludes the README index)."""
    corpus_dir = corpus_dir or _CORPUS_DIR
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        chunks.extend(chunk_document(path))
    return chunks
