"""
AION Copilot — LLM Client
============================
Unified interface for Claude 3 and GPT-4 via LangChain.
"""

import logging
from typing import AsyncGenerator, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger("aion-copilot.llm")


class LLMClient:
    """Unified LLM client supporting Claude 3 and GPT-4."""

    def __init__(self):
        self._claude = None
        self._openai = None

    def _get_claude(self):
        if self._claude is None:
            from langchain_anthropic import ChatAnthropic
            self._claude = ChatAnthropic(
                model=settings.claude_model,
                anthropic_api_key=settings.anthropic_api_key,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                default_request_timeout=60,
            )
        return self._claude

    def _get_openai(self):
        if self._openai is None:
            from langchain_openai import ChatOpenAI
            self._openai = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        return self._openai

    def _resolve_model(self, preference: Optional[str] = None):
        """Pick the right model based on preference and availability."""
        pref = preference or settings.default_llm

        if pref == "claude" and settings.anthropic_api_key:
            return self._get_claude(), "claude"
        elif pref == "openai" and settings.openai_api_key:
            return self._get_openai(), "openai"
        elif settings.anthropic_api_key:
            return self._get_claude(), "claude"
        elif settings.openai_api_key:
            return self._get_openai(), "openai"
        else:
            raise ValueError("No LLM API keys configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

    async def generate(
        self,
        prompt: str,
        system: str = None,
        model_preference: str = None,
    ) -> str:
        """Generate a single response."""
        model, model_name = self._resolve_model(model_preference)

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        response = await model.ainvoke(messages)
        return response.content

    async def generate_with_usage(
        self,
        prompt: str,
        system: str = None,
        model_preference: str = None,
    ) -> Tuple[str, int]:
        """Generate response and return (text, total_tokens)."""
        model, model_name = self._resolve_model(model_preference)

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        response = await model.ainvoke(messages)

        # Extract token usage
        tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata.get("total_tokens", 0)
        elif hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("usage", {})
            tokens = usage.get("total_tokens", 0)

        return response.content, tokens

    async def generate_stream(
        self,
        prompt: str,
        system: str = None,
        model_preference: str = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response token by token."""
        model, model_name = self._resolve_model(model_preference)

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        async for chunk in model.astream(messages):
            if chunk.content:
                yield chunk.content
