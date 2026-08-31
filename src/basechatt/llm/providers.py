"""Concrete LLM provider implementations.

Default and preferred deployment is Groq (fast, free-tier, OpenAI-compatible
API). OpenAI and Anthropic are supported through the same interface. A Mock
provider is used in tests so the whole system can run without any API key.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import AsyncOpenAI

from basechatt.config.settings import Settings, settings
from basechatt.llm.base import LLMProvider, LLMResponse
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.llm")


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self._client: AsyncOpenAI | None = None

    def _client_or_raise(self) -> AsyncOpenAI:
        if self._client is None:
            key = self.cfg.groq_api_key or os.getenv("GROQ_API_KEY")
            if not key:
                raise RuntimeError(
                    "Groq API key is not configured. Set BASECHATT_GROQ_API_KEY "
                    "or GROQ_API_KEY, or configure a different LLM provider."
                )
            self._client = AsyncOpenAI(
                api_key=key,
                base_url=self.cfg.groq_base_url,
            )
        return self._client

    async def chat(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._client_or_raise()
        kwargs: dict[str, Any] = {
            "model": self.cfg.groq_chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature if temperature is not None else self.cfg.llm_temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        elif json_mode:
            kwargs["max_tokens"] = 4096
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
            "total_tokens": getattr(resp.usage, "total_tokens", 0),
        }
        return LLMResponse(text=text, usage=usage, model=self.cfg.groq_chat_model)

    async def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        temperature: float | None = None,
    ) -> LLMResponse:
        client = self._client_or_raise()
        msgs = [{"role": "system", "content": system}] + messages
        resp = await client.chat.completions.create(
            model=self.cfg.groq_chat_model,
            messages=msgs,
            tools=tools or None,
            temperature=temperature if temperature is not None else self.cfg.llm_temperature,
        )
        choice = resp.choices[0]
        message = choice.message
        text = message.content or ""
        return LLMResponse(text=text, usage={}, model=self.cfg.groq_chat_model)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self._client = AsyncOpenAI(api_key=self.cfg.openai_api_key)

    async def chat(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.cfg.openai_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature if temperature is not None else self.cfg.llm_temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        resp = await self._client.chat.completions.create(**kwargs)
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            model=self.cfg.openai_model,
        )

    async def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        temperature: float | None = None,
    ) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self.cfg.openai_model,
            messages=[{"role": "system", "content": system}] + messages,
            tools=tools or None,
            temperature=temperature if temperature is not None else self.cfg.llm_temperature,
        )
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            model=self.cfg.openai_model,
        )


class MockProvider(LLMProvider):
    """Deterministic provider for tests and offline operation.

    Returns canned, predictable responses. Never used when real answers matter;
    it exists so the full pipeline is testable without any API key.
    """

    name = "mock"

    async def chat(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        return LLMResponse(text=f"mock answer for: {user[:120]}", usage={}, model="mock")

    async def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        temperature: float | None = None,
    ) -> LLMResponse:
        return LLMResponse(text="mock tool answer", usage={}, model="mock")


def _json_dumps(data) -> str:
    return json.dumps(data, default=str)
