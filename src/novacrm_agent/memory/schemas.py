"""Memory schemas (Phase 3) — DRAFT, pending human review of the extraction design.

MemoryEntry is what the extractor produces (forced via a tool call, P1 structured-output
pattern). StoredMemory is the persisted form — MemoryEntry plus consolidation metadata the
store adds (which session/when it was last seen). Topics are the six D5 categories.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MemoryTopic(str, Enum):
    # The six D5 topics. account_context is deliberately scoped to durable context the
    # account SYSTEM does not hold — NOT current tier/billing/storage (those stay
    # tool-authoritative and are re-fetched live; see D5 open item).
    CUSTOMER_IDENTITY = "customer_identity"
    ACCOUNT_CONTEXT = "account_context"
    COMMUNICATION_PREFERENCES = "communication_preferences"
    ISSUE_HISTORY = "issue_history"
    SENTIMENT_TRAJECTORY = "sentiment_trajectory"
    PRODUCT_USAGE_CONTEXT = "product_usage_context"


class MemoryEntry(BaseModel):
    """One atomic fact worth remembering across sessions."""
    topic: MemoryTopic
    fact: str = Field(description="One concise, self-contained fact about this customer.")
    confidence: float = Field(ge=0.0, le=1.0, description="How clearly the conversation supports it.")
    source_turn: int = Field(ge=1, description="Turn number where the fact is established.")


class ExtractionResult(BaseModel):
    """Wrapper for the extractor's output (possibly empty — empty is valid and common)."""
    memories: list[MemoryEntry] = Field(default_factory=list)


class StoredMemory(BaseModel):
    """Persisted form: an entry plus consolidation metadata added by the store."""
    topic: MemoryTopic
    fact: str
    confidence: float
    source_session: str
    source_turn: int
    first_seen: str
    last_updated: str
