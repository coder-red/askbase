"""Research agent graph state.

The research agent is a bounded LangGraph pipeline. State flows:
START -> investigate (retrieve) -> analyze (LLM draft) -> verify (citations) -> END.

Retrieval evidence is carried separately from the final answer so verification
has explicit, structured facts (evidence items with chunk ids) it can check and
cite — never asking the model to free-hand references.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.retrieval.hybrid import HybridResponse


@dataclass
class Evidence:
    chunk_id: str
    document_id: str
    title: str
    source_code: str
    source_name: str
    authority_level: str
    text: str
    published_at: str | None = None
    source_url: str = ""
    score: float = 0.0
    causal_found: bool = False

    def to_citation(self) -> dict:
        return {
            "title": self.title,
            "source": self.source_code,
            "source_url": self.source_url,
            "chunk_id": self.chunk_id,
        }


@dataclass
class Answer:
    text: str
    is_satisfactory: bool
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.0
    citations: list[dict] = field(default_factory=list)
    follow_up_queries: list[str] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    uncertainty: str = ""
    elapsed_ms: float = 0.0


@dataclass
class ResearchState:
    query: str
    session: AsyncSession
    company_ticker: str | None = None
    source_code: str | None = None
    answer: Answer | None = None
    retrieval: HybridResponse | None = None
    effort: str = "balanced"
    metadata: dict = field(default_factory=dict)
