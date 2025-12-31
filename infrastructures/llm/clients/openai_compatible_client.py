# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: OpenAI-compatible HTTP client (Chat Completions).

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from infrastructures.llm.errors import (
    LlmAuthError,
    LlmBadRequestError,
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class OpenAICompatResponse:
    raw: Dict[str, Any]
    latency_ms: int


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible client for /v1/chat/completions.

    This is used for:
      - OpenAI
      - OpenAI-compatible gateways for DeepSeek/Qwen/Gemini, etc.

    Notes:
      - We do not assume vendor SDK availability; we use httpx directly.
      - Provider adapters decide how to map the unified domain request into OpenAI payload.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        provider_tag: str = "openai_compatible",
        timeout_seconds: int = 60,
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.provider_tag = provider_tag
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.default_headers = default_headers or {}
        # Lazily-created shared HTTP client for this provider instance.
        # Reusing the client enables connection pooling (keep-alive/TLS reuse),
        # which significantly reduces per-request overhead under concurrency.
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client

        # NOTE: Do not bake auth headers into the client; we still pass them per request
        # to keep behavior identical to the previous implementation.
        self._client = httpx.AsyncClient()
        return self._client

    async def aclose(self) -> None:
        """Close the underlying connection pool."""

        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None

    def _headers(self) -> Dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        h.update(self.default_headers)
        return h

    def _url(self, path: str) -> str:
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/{path}"

    async def chat_completions(self, *, payload: Dict[str, Any], timeout_seconds: Optional[int] = None) -> OpenAICompatResponse:
        t0 = _now_ms()
        timeout = httpx.Timeout(float(timeout_seconds or self.timeout_seconds))
        url = self._url("/v1/chat/completions")

        try:
            client = self._get_client()
            resp = await client.post(url, headers=self._headers(), json=payload, timeout=timeout)
        except httpx.TimeoutException as e:
            raise LlmTimeoutError(provider=self.provider_tag) from e
        except Exception as e:
            raise LlmProviderError(str(e), provider=self.provider_tag, retryable=True) from e

        latency = _now_ms() - t0
        if resp.status_code in (401, 403):
            raise LlmAuthError(provider=self.provider_tag)
        if resp.status_code == 429:
            raise LlmRateLimitError(provider=self.provider_tag)
        if 400 <= resp.status_code < 500:
            try:
                j = resp.json()
            except Exception:
                j = {"text": resp.text}
            raise LlmBadRequestError("bad request", provider=self.provider_tag, details=j)
        if resp.status_code >= 500:
            raise LlmProviderError(
                f"upstream error: {resp.status_code}",
                provider=self.provider_tag,
                retryable=True,
                http_status=502,
                details={"status_code": resp.status_code, "text": resp.text[:5000]},
            )

        try:
            j = resp.json()
        except Exception as e:
            raise LlmProviderError(
                "invalid json from upstream",
                provider=self.provider_tag,
                retryable=True,
                details={"text": resp.text[:5000]},
            ) from e

        return OpenAICompatResponse(raw=j, latency_ms=int(latency))

    async def chat_completions_stream(
        self,
        *,
        payload: Dict[str, Any],
        timeout_seconds: Optional[int] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Yield JSON chunks from OpenAI-compatible SSE stream.

        Each yielded element is the parsed JSON dict for a single SSE `data:` line.
        """

        timeout = httpx.Timeout(float(timeout_seconds or self.timeout_seconds), read=None)
        url = self._url("/v1/chat/completions")
        payload = dict(payload)
        payload["stream"] = True

        try:
            client = self._get_client()
            async with client.stream("POST", url, headers=self._headers(), json=payload, timeout=timeout) as resp:
                if resp.status_code in (401, 403):
                    raise LlmAuthError(provider=self.provider_tag)
                if resp.status_code == 429:
                    raise LlmRateLimitError(provider=self.provider_tag)
                if 400 <= resp.status_code < 500:
                    txt = (await resp.aread()).decode("utf-8", errors="ignore")
                    raise LlmBadRequestError("bad request", provider=self.provider_tag, details={"text": txt[:5000]})
                if resp.status_code >= 500:
                    txt = (await resp.aread()).decode("utf-8", errors="ignore")
                    raise LlmProviderError(
                        f"upstream error: {resp.status_code}",
                        provider=self.provider_tag,
                        retryable=True,
                        http_status=502,
                        details={"status_code": resp.status_code, "text": txt[:5000]},
                    )

                # SSE is line-based. We parse `data: ...` frames.
                buffer = ""
                async for chunk in resp.aiter_text():
                    if not chunk:
                        continue
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if not data:
                            continue
                        if data == "[DONE]":
                            return
                        try:
                            yield json.loads(data)
                        except Exception:
                            # Some gateways may send non-json or partial lines; ignore safely.
                            continue
        except httpx.TimeoutException as e:
            raise LlmTimeoutError(provider=self.provider_tag) from e
        except Exception as e:
            raise LlmProviderError(str(e), provider=self.provider_tag, retryable=True) from e
