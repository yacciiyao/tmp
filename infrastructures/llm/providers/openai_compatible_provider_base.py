# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Shared base for OpenAI-compatible providers.

from __future__ import annotations

import base64
import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional

from domains.llm_request_domain import (
    AudioPart,
    FilePart,
    ImagePart,
    InputPartType,
    LlmMessage,
    LlmOutputFormat,
    LlmRequest,
    LlmResponse,
    LlmUsage,
    StreamEvent,
    StreamEventType,
    TextPart,
)
from infrastructures.llm.clients.openai_compatible_client import OpenAICompatibleClient
from infrastructures.llm.errors import LlmUnsupportedModalityError
from infrastructures.llm.providers.provider_base import LlmProviderBase


def _extract_model_name(profile_id: str) -> str:
    """Derive `model` parameter from `model_profile_id`.

    Convention: profile_id is `<provider>:<model_name>`.
    """

    if not profile_id:
        return ""
    if ":" in profile_id:
        return profile_id.split(":", 1)[1]
    return profile_id


def _load_local_bytes(storage_uri: str) -> bytes:
    if storage_uri.startswith("local:"):
        path = storage_uri[len("local:") :]
    else:
        # Best-effort: treat as path
        path = storage_uri

    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "rb") as f:
        return f.read()


def _to_data_url(*, storage_uri: str, mime_type: str) -> str:
    b = _load_local_bytes(storage_uri)
    enc = base64.b64encode(b).decode("utf-8")
    mt = mime_type or "application/octet-stream"
    return f"data:{mt};base64,{enc}"


class OpenAICompatibleProviderBase(LlmProviderBase):
    """Provider base using OpenAI-compatible `/v1/chat/completions`.

    The concrete provider class only needs to pass correct client configuration.
    """

    def __init__(self, *, provider_name: str, client: OpenAICompatibleClient) -> None:
        self.provider_name = provider_name
        self._client = client

    async def aclose(self) -> None:
        # Close underlying HTTP connection pool if present.
        try:
            await self._client.aclose()
        except Exception:
            # Best-effort: shutdown should not crash the process.
            return None

    # -----------------------------
    # Payload builders
    # -----------------------------

    def _build_messages(self, req: LlmRequest) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = []

        if req.system_prompt:
            msgs.append({"role": "system", "content": str(req.system_prompt)})

        for m in req.messages:
            msgs.append({"role": str(m.role.value), "content": str(m.content or "")})

        if req.input_parts:
            has_non_text = any(getattr(p, "type", None) != InputPartType.text for p in req.input_parts)
            if not has_non_text:
                text = "\n".join([str(getattr(p, "text", "")).strip() for p in req.input_parts if getattr(p, "text", "")])
                if text.strip():
                    msgs.append({"role": "user", "content": text.strip()})
            else:
                parts: List[Dict[str, Any]] = []
                for p in req.input_parts:
                    if isinstance(p, TextPart):
                        t = (p.text or "").strip()
                        if t:
                            parts.append({"type": "text", "text": t})
                        continue

                    if isinstance(p, ImagePart):
                        url = _to_data_url(storage_uri=p.asset_uri, mime_type=p.mime_type)
                        parts.append({"type": "image_url", "image_url": {"url": url}})
                        continue

                    if isinstance(p, (AudioPart, FilePart)):
                        raise LlmUnsupportedModalityError(
                            "OpenAI-compatible chat/completions does not accept audio/file parts directly; please parse to text before calling provider.",
                            provider=self.provider_name,
                            details={"part_type": str(getattr(p, "type", "")), "asset_uri": getattr(p, "asset_uri", None)},
                        )

                if parts:
                    msgs.append({"role": "user", "content": parts})

        return msgs

    def _build_response_format(self, req: LlmRequest) -> Optional[Dict[str, Any]]:
        # Conservative: widely supported json_object mode.
        if req.output_contract and req.output_contract.format == LlmOutputFormat.json:
            return {"type": "json_object"}
        return None

    def _build_payload(self, req: LlmRequest) -> Dict[str, Any]:
        model = _extract_model_name(req.model_profile_id)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(req),
        }

        rf = self._build_response_format(req)
        if rf is not None:
            payload["response_format"] = rf

        # Allow tuning via req.extra without hardcoding business rules.
        if isinstance(req.extra, dict):
            if "temperature" in req.extra:
                payload["temperature"] = req.extra["temperature"]
            if "max_tokens" in req.extra:
                payload["max_tokens"] = req.extra["max_tokens"]
            if "top_p" in req.extra:
                payload["top_p"] = req.extra["top_p"]

        # Observability hint for some gateways.
        if req.trace_id:
            payload["user"] = str(req.trace_id)

        return payload

    # -----------------------------
    # Response mapping
    # -----------------------------

    def _parse_usage(self, raw: Dict[str, Any]) -> LlmUsage:
        u = raw.get("usage") or {}
        try:
            inp = int(u.get("prompt_tokens") or 0)
        except Exception:
            inp = 0
        try:
            out = int(u.get("completion_tokens") or 0)
        except Exception:
            out = 0
        try:
            tot = int(u.get("total_tokens") or (inp + out))
        except Exception:
            tot = inp + out
        return LlmUsage(input_tokens=inp, output_tokens=out, total_tokens=tot)

    def _parse_text(self, raw: Dict[str, Any]) -> str:
        choices = raw.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0] or {}).get("message") or {}
        return str(msg.get("content") or "")

    async def generate(self, req: LlmRequest) -> LlmResponse:
        payload = self._build_payload(req)
        resp = await self._client.chat_completions(payload=payload, timeout_seconds=req.timeout_seconds)

        model = str(resp.raw.get("model") or _extract_model_name(req.model_profile_id))
        txt = self._parse_text(resp.raw)

        out_json = None
        out_text = txt

        if req.output_contract and req.output_contract.format == LlmOutputFormat.json:
            # Best effort parse. Validation/repair belongs to higher layers.
            try:
                out_json = json.loads(txt) if txt else None
                out_text = None
            except Exception:
                out_json = None

        return LlmResponse(
            provider=self.provider_name,
            model=model,
            latency_ms=int(resp.latency_ms),
            text=out_text,
            json=out_json,
            usage=self._parse_usage(resp.raw),
            raw=resp.raw,
        )

    async def stream(self, req: LlmRequest) -> AsyncIterator[StreamEvent]:
        payload = self._build_payload(req)
        async for chunk in self._client.chat_completions_stream(payload=payload, timeout_seconds=req.timeout_seconds):
            # Standard OpenAI chunk format
            try:
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                c0 = choices[0] or {}
                delta = (c0.get("delta") or {}).get("content")
                finish = c0.get("finish_reason")

                if delta:
                    yield StreamEvent(type=StreamEventType.delta_text, delta=str(delta), raw=chunk)
                if finish:
                    yield StreamEvent(type=StreamEventType.completed, raw=chunk)
                    return
            except Exception:
                continue
