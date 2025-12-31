# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Ollama provider adapter (native API by default).

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List

from domains.llm_request_domain import (
    AudioPart,
    FilePart,
    ImagePart,
    InputPartType,
    LlmOutputFormat,
    LlmRequest,
    LlmResponse,
    LlmUsage,
    StreamEvent,
    StreamEventType,
    TextPart,
)
from infrastructures.llm.clients.ollama_native_client import OllamaNativeClient
from infrastructures.llm.errors import LlmUnsupportedModalityError
from infrastructures.llm.providers.provider_base import LlmProviderBase
from infrastructures.vconfig import vconfig


def _extract_model_name(profile_id: str) -> str:
    if not profile_id:
        return ""
    if ":" in profile_id:
        return profile_id.split(":", 1)[1]
    return profile_id


class OllamaProvider(LlmProviderBase):
    provider_name = "ollama"

    def __init__(self) -> None:
        self._client = OllamaNativeClient(
            base_url=str(vconfig.ollama_base_url),
            timeout_seconds=int(vconfig.ollama_timeout_seconds),
            provider_tag="ollama",
        )

    def _build_messages(self, req: LlmRequest) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = []
        if req.system_prompt:
            msgs.append({"role": "system", "content": str(req.system_prompt)})
        for m in req.messages:
            msgs.append({"role": str(m.role.value), "content": str(m.content or "")})

        if req.input_parts:
            has_non_text = any(getattr(p, "type", None) != InputPartType.text for p in req.input_parts)
            if has_non_text:
                # Native Ollama /api/chat does not accept multimodal parts.
                # Use ASSIST policy (OCR/ASR/file parsing) before reaching provider.
                for p in req.input_parts:
                    if isinstance(p, (ImagePart, AudioPart, FilePart)):
                        raise LlmUnsupportedModalityError(
                            "Ollama native chat does not accept image/audio/file parts directly; parse to text first.",
                            provider=self.provider_name,
                            details={"part_type": str(getattr(p, "type", "")), "asset_uri": getattr(p, "asset_uri", None)},
                        )
            text = "\n".join([str(getattr(p, "text", "")).strip() for p in req.input_parts if isinstance(p, TextPart)])
            if text.strip():
                msgs.append({"role": "user", "content": text.strip()})

        return msgs

    def _build_payload(self, req: LlmRequest) -> Dict[str, Any]:
        model = _extract_model_name(req.model_profile_id) or (vconfig.ollama_default_model or "")
        payload: Dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(req),
        }

        # Allow tuning via req.extra
        if isinstance(req.extra, dict) and "temperature" in req.extra:
            payload.setdefault("options", {})
            payload["options"]["temperature"] = req.extra["temperature"]
        if isinstance(req.extra, dict) and "num_predict" in req.extra:
            payload.setdefault("options", {})
            payload["options"]["num_predict"] = req.extra["num_predict"]

        return payload

    @staticmethod
    def _parse_usage(raw: Dict[str, Any]) -> LlmUsage:
        # Ollama fields: prompt_eval_count, eval_count
        try:
            inp = int(raw.get("prompt_eval_count") or 0)
        except Exception:
            inp = 0
        try:
            out = int(raw.get("eval_count") or 0)
        except Exception:
            out = 0
        return LlmUsage(input_tokens=inp, output_tokens=out, total_tokens=inp + out)

    async def generate(self, req: LlmRequest) -> LlmResponse:
        payload = self._build_payload(req)
        resp = await self._client.chat(payload=payload, timeout_seconds=req.timeout_seconds)
        raw = resp.raw
        msg = raw.get("message") or {}
        txt = str(msg.get("content") or "")

        out_json = None
        out_text = txt
        if req.output_contract and req.output_contract.format == LlmOutputFormat.json:
            try:
                out_json = json.loads(txt) if txt else None
                out_text = None
            except Exception:
                out_json = None

        return LlmResponse(
            provider=self.provider_name,
            model=str(raw.get("model") or _extract_model_name(req.model_profile_id)),
            latency_ms=int(resp.latency_ms),
            text=out_text,
            json=out_json,
            usage=self._parse_usage(raw),
            raw=raw,
        )

    async def stream(self, req: LlmRequest) -> AsyncIterator[StreamEvent]:
        payload = self._build_payload(req)
        async for line in self._client.chat_stream(payload=payload, timeout_seconds=req.timeout_seconds):
            try:
                msg = line.get("message") or {}
                delta = msg.get("content")
                done = bool(line.get("done"))
                if delta:
                    yield StreamEvent(type=StreamEventType.delta_text, delta=str(delta), raw=line)
                if done:
                    yield StreamEvent(type=StreamEventType.completed, raw=line)
                    return
            except Exception:
                continue
