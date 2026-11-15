"""
LLM provider abstraction.

The rest of the app only knows `LLMClient.complete(system, user)`. Two real providers are
implemented over plain HTTPS with httpx (OpenAI-compatible chat completions, and Anthropic
messages), so there is no vendor SDK to keep in step and tests can swap the transport.

When no provider/key is configured `get_llm_client()` returns None and the chat endpoint says
so honestly; there is deliberately no "mock" model that pretends to answer.
"""

from typing import Optional, Protocol

import httpx

from app.core.config import settings

class LLMError(Exception):
    """A failed model call. `kind` lets callers choose a sensible user message."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


class LLMClient(Protocol):
    async def complete(self, system: str, user: str, *, max_tokens: Optional[int] = None) -> str: ...


def _classify_http_error(status: int, body: str) -> LLMError:
    low = body.lower()
    if status in (401, 403):
        return LLMError("auth", "The AI provider rejected the configured API key.")
    if status == 429:
        return LLMError("rate_limit", "The AI provider is rate-limiting requests right now.")
    if status in (400, 413) and any(k in low for k in ("context", "token", "too long", "maximum")):
        return LLMError("token_limit", "The request was too large for the model's context window.")
    if status >= 500:
        return LLMError("unavailable", "The AI provider is temporarily unavailable.")
    if status in (400, 404):
        return LLMError("configuration", "The provider rejected the configured model, destination or request settings.")
    return LLMError("bad_response", f"The AI provider returned HTTP {status}.")


class _HttpLLM:
    """One HTTP attempt per completion."""

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._transport = transport

    async def _post(self, url: str, headers: dict, payload: dict) -> dict:
        # A failed POST can already have run (and been billed). Never replay it.
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS, transport=self._transport) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise LLMError("timeout", "The provider request timed out.") from None
        except (httpx.InvalidURL, httpx.UnsupportedProtocol, ValueError):
            raise LLMError("configuration", "The provider URL or request settings are invalid.") from None
        except httpx.RequestError:
            raise LLMError("unavailable", "Could not reach the AI provider.") from None
        if resp.status_code != 200:
            raise _classify_http_error(resp.status_code, resp.text[:500])
        try:
            return resp.json()
        except ValueError:
            raise LLMError("bad_response", "The AI provider returned a non-JSON response.") from None


class OpenAICompatibleClient(_HttpLLM):
    async def complete(self, system: str, user: str, *, max_tokens: Optional[int] = None) -> str:
        base = (settings.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        data = await self._post(
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
            {
                "model": settings.LLM_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": settings.LLM_TEMPERATURE,
                "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            },
        )
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMError("bad_response", "The AI provider's response had an unexpected shape.")
        if choice.get("finish_reason") == "length":
            raise LLMError("token_limit", "The model ran out of output tokens before finishing.")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("bad_response", "The AI provider did not return text.")
        return text


class AnthropicClient(_HttpLLM):
    async def complete(self, system: str, user: str, *, max_tokens: Optional[int] = None) -> str:
        base = (settings.LLM_BASE_URL or "https://api.anthropic.com").rstrip("/")
        data = await self._post(
            f"{base}/v1/messages",
            {"x-api-key": settings.LLM_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            {
                "model": settings.LLM_MODEL,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "temperature": settings.LLM_TEMPERATURE,
                "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            },
        )
        try:
            text = "".join(block.get("text", "") for block in data["content"] if block.get("type") == "text")
        except (AttributeError, KeyError, TypeError):
            raise LLMError("bad_response", "The AI provider's response had an unexpected shape.")
        if data.get("stop_reason") == "max_tokens":
            raise LLMError("token_limit", "The model ran out of output tokens before finishing.")
        if not text.strip():
            raise LLMError("bad_response", "The AI provider did not return text.")
        return text


# Tests (and embedders) can install a client here to exercise the whole chat flow offline.
_override: Optional[LLMClient] = None


def set_llm_client_override(client: Optional[LLMClient]) -> None:
    global _override
    _override = client


def get_llm_client() -> Optional[LLMClient]:
    """Returns the configured client, or None when AI is not configured."""
    if _override is not None:
        return _override
    if not settings.ai_configured:
        return None
    return AnthropicClient() if settings.LLM_PROVIDER.lower() == "anthropic" else OpenAICompatibleClient()


def ai_status() -> dict:
    """The only LLM facts the API exposes: whether it is on and which provider. Never the key."""
    on = _override is not None or settings.ai_configured
    return {
        "configured": on,
        "provider": settings.LLM_PROVIDER if on else None,
        "message": None
        if on
        else "AI chat is disabled. An administrator can check the server's provider configuration.",
    }
