# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Ollama native HTTP client (/api/chat).

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
class OllamaResponse:
    raw: Dict[str, Any]
    latency_ms: int


class OllamaNativeClient:
    """Ollama native client using /api/chat.

    Ollama's streaming returns newline-delimited JSON objects.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 60,
        provider_tag: str = "ollama",
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.provider_tag = provider_tag
        self.default_headers = default_headers or {}

    def _headers(self) -> Dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        h.update(self.default_headers)
        return h

    def _url(self, path: str) -> str:
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/{path}"

    async def chat(self, *, payload: Dict[str, Any], timeout_seconds: Optional[int] = None) -> OllamaResponse:
        t0 = _now_ms()
        timeout = httpx.Timeout(float(timeout_seconds or self.timeout_seconds))
        url = self._url("/api/chat")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
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
            raise LlmBadRequestError("bad request", provider=self.provider_tag, details={"text": resp.text[:5000]})
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

        return OllamaResponse(raw=j, latency_ms=int(latency))

    async def chat_stream(self, *, payload: Dict[str, Any], timeout_seconds: Optional[int] = None) -> AsyncIterator[Dict[str, Any]]:
        """Yield Ollama JSON lines from /api/chat with stream=true."""

        timeout = httpx.Timeout(float(timeout_seconds or self.timeout_seconds), read=None)
        url = self._url("/api/chat")
        payload = dict(payload)
        payload["stream"] = True

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=self._headers(), json=payload) as resp:
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

                    buf = ""
                    async for chunk in resp.aiter_text():
                        if not chunk:
                            continue
                        buf += chunk
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                yield json.loads(line)
                            except Exception:
                                continue
        except httpx.TimeoutException as e:
            raise LlmTimeoutError(provider=self.provider_tag) from e
        except Exception as e:
            raise LlmProviderError(str(e), provider=self.provider_tag, retryable=True) from e
