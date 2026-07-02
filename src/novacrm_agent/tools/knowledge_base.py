"""lookup_knowledge_base — RAG side of the agent.

The KB is nested JSON (data/knowledge_base/novacrm_kb.json). We flatten it once into
flat (title, text) chunks and do simple keyword-overlap retrieval. Deliberately not a
vector store: Project 3's memory depth excludes embeddings, and keyword search keeps the
RAG path inspectable. Pricing lives here (not the system prompt) so pricing answers are
*retrieved* facts — sharpening the RAG-vs-memory demonstration.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_KB_PATH = Path(__file__).resolve().parents[3] / "data" / "knowledge_base" / "novacrm_kb.json"
_STOP = {"the", "a", "an", "is", "are", "do", "i", "my", "to", "of", "for", "on", "how", "what", "can", "you", "and"}


@lru_cache(maxsize=1)
def _chunks() -> tuple[tuple[str, str], ...]:
    kb = json.loads(_KB_PATH.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []

    for tier in kb["pricing"]["tiers"]:
        feats = "; ".join(tier["features"])
        out.append((
            f"Pricing: {tier['name']} plan",
            f"{tier['name']} plan — ${tier['price_monthly']}/{tier['per']} "
            f"(${tier['price_annual_monthly']} {tier['per']} billed annually). Includes: {feats}.",
        ))
    out.append(("Pricing: annual discount", f"Annual billing discount: {kb['pricing']['annual_discount']}."))

    for name, text in kb["policies"].items():
        out.append((f"Policy: {name}", text))

    for name, issue in kb["common_issues"].items():
        out.append((f"Common issue: {name}", f"{issue['description']}. {issue['resolution']}"))

    for team, scope in kb["escalation_teams"].items():
        out.append((f"Escalation team: {team}", f"The {team} team handles: {scope}"))

    return tuple(out)


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 1}


def lookup_knowledge_base(query: str, top_k: int = 5) -> str:
    """Search EggCRM product documentation; returns the top matching KB entries as text."""
    q = _tokens(query)
    if not q:
        return "No query provided."
    scored = []
    for title, text in _chunks():
        overlap = len(q & _tokens(f"{title} {text}"))
        if overlap:
            scored.append((overlap, title, text))
    if not scored:
        return "No matching knowledge base entries found."
    scored.sort(key=lambda x: x[0], reverse=True)
    return "\n\n".join(f"[{title}] {text}" for _, title, text in scored[:top_k])
