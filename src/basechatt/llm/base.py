"""Base interfaces for the LLM and embedding providers.

All BaseChatt LLM interaction flows through ``LLMProvider`` so external
providers (Groq, OpenAI, Anthropic) can be swapped without touching the
retrieval, agent, or verification layers. Retrieved evidence is ALWAYS passed
as data (separated from instructions) — providers are never asked to treat
retrieved documents as instructions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    usage: dict = field(default_factory=dict)
    model: str = ""


class LLMProvider(ABC):
    """Interface for chat-style LLM backends."""

    @abstractmethod
    async def chat(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Complete a single chat turn. ``user`` may include evidence blocks.

        Providers MUST treat ``system`` as the authoritative instruction set and
        ``user`` as untrusted data + the actual question.
        """

    @abstractmethod
    async def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        temperature: float | None = None,
    ) -> LLMResponse:
        """Conversation with tool/function definitions available to the model."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...
