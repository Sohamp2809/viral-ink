"""
LLM abstraction layer — unified interface for Anthropic, OpenAI, and Ollama.

Usage:
    from src.utils.llm import get_llm, get_cheap_llm

    llm = get_llm()                          # primary model (Sonnet — for writing)
    cheap = get_cheap_llm()                   # cheap model (Haiku — for analysis)

    response = await llm.generate("Write a LinkedIn post about AI trends")
    response = await llm.generate(prompt, system="You are a tech writer.")
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from src.utils.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def parse_json(self) -> dict | list:
        """Attempt to parse response text as JSON."""
        cleaned = self.text.strip()
        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        return json.loads(cleaned)


class BaseLLM(ABC):
    """Abstract base for all LLM providers."""

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        ...

    async def generate_json(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
    ) -> dict | list:
        """Generate and parse as JSON. Adds JSON instruction to system prompt."""
        json_system = system + (
            "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "No markdown, no backticks, no explanation — just the JSON object."
        )
        response = await self.generate(prompt, system=json_system, max_tokens=max_tokens)
        return response.parse_json()


# ── Anthropic ─────────────────────────────────────────

class AnthropicLLM(BaseLLM):
    def __init__(self, model: str, api_key: str):
        super().__init__(model)
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        logger.debug(f"Anthropic call: model={self.model}, prompt_len={len(prompt)}")
        response = await self.client.messages.create(**kwargs)

        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


# ── OpenAI ────────────────────────────────────────────

class OpenAILLM(BaseLLM):
    def __init__(self, model: str, api_key: str):
        super().__init__(model)
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import openai
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"OpenAI call: model={self.model}, prompt_len={len(prompt)}")
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            text=choice.message.content or "",
            model=self.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


# ── Ollama (local) ────────────────────────────────────

class OllamaLLM(BaseLLM):
    def __init__(self, model: str, base_url: str):
        super().__init__(model)
        self.base_url = base_url.rstrip("/")

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        logger.debug(f"Ollama call: model={self.model}, prompt_len={len(prompt)}")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            text=data.get("response", ""),
            model=self.model,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )


# ── Factory Functions ─────────────────────────────────

def _build_llm(provider: str, model: str) -> BaseLLM:
    """Create an LLM instance from provider name and model string."""
    settings = get_settings()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using Anthropic provider")
        return AnthropicLLM(model=model, api_key=settings.anthropic_api_key)

    elif provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        return OpenAILLM(model=model, api_key=settings.openai_api_key)

    elif provider == "ollama":
        return OllamaLLM(model=model, base_url=settings.ollama_base_url)

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'anthropic', 'openai', or 'ollama'")


def get_llm() -> BaseLLM:
    """Get the primary LLM (for writing — higher quality, higher cost)."""
    s = get_settings()
    model = {
        "anthropic": s.anthropic_model,
        "openai": s.openai_model,
        "ollama": s.ollama_model,
    }.get(s.llm_provider, s.anthropic_model)
    return _build_llm(s.llm_provider, model)


def get_cheap_llm() -> BaseLLM:
    """Get the cheap LLM (for summaries, critic, scoring — fast, low cost)."""
    s = get_settings()
    return _build_llm(s.llm_cheap_provider, s.llm_cheap_model)
