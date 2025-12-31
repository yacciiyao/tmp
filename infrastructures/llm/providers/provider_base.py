# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Provider interface contracts (no business logic).

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from domains.llm_request_domain import LlmRequest, LlmResponse, StreamEvent


class LlmProviderBase(ABC):
    """All providers implement a unified interface.

    Notes:
      - This is infrastructure-only. Routing, session rules, and persistence are implemented elsewhere.
      - Implementations should be pure I/O adapters for each vendor SDK/HTTP API.
    """

    provider_name: str

    @abstractmethod
    async def generate(self, req: LlmRequest) -> LlmResponse:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, req: LlmRequest) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    async def aclose(self) -> None:
        """Optional resource cleanup hook.

        Provider implementations may hold long-lived network clients/connection pools.
        The API service can call this on shutdown to close those resources.
        """

        return None
