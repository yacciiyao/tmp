# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC AI enrichment (module/report ai_summary) based on outputs + evidence.

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from domains.llm_request_domain import LlmRequest, LlmMessage, LlmRole
from infrastructures.llm.executor import llm_executor
from infrastructures.llm.routing.model_router import ModelRouter
from infrastructures.llm.config_cache import llm_config_cache
from infrastructures.vconfig import get_vconfig
from infrastructures.db.repository.voc_repository import VocRepository


def _now_ts() -> int:
    return int(time.time())


def _safe_json(obj: Any, *, max_list: int = 30, max_str: int = 600, depth: int = 0, max_depth: int = 6) -> Any:
    """Shrink large payloads to keep prompts bounded.

    - trims long strings
    - truncates long lists
    - limits recursion depth
    """

    if depth >= max_depth:
        return "..."

    if obj is None:
        return None
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, str):
        s = obj
        return s if len(s) <= max_str else (s[: max_str - 3] + "...")
    if isinstance(obj, list):
        out = [_safe_json(x, max_list=max_list, max_str=max_str, depth=depth + 1, max_depth=max_depth) for x in obj[:max_list]]
        if len(obj) > max_list:
            out.append(f"...({len(obj) - max_list} more)")
        return out
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in list(obj.items())[:200]:
            out[str(k)] = _safe_json(v, max_list=max_list, max_str=max_str, depth=depth + 1, max_depth=max_depth)
        if len(obj) > 200:
            out["__truncated__"] = f"...({len(obj) - 200} more keys)"
        return out
    # fallback
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"


class VocAiService:
    """Generate ai_summary for VOC modules and report.

    Principles:
    - AI MUST only use stg_voc_outputs + stg_voc_evidence as inputs (reproducible)
    - AI failure must NOT fail the VOC job (best-effort enrichment)
    - Output is stored back into payload_json.ai_summary (string) and payload_json.meta.ai
    """

    FLOW_MODULE_SUMMARY = "voc.module_summary"
    FLOW_REPORT_SUMMARY = "voc.report_summary"
    PROMPT_VERSION = "voc_ai_v1"

    def __init__(self, *, max_evidence: int = 30):
        self.max_evidence = int(max_evidence)

    async def _candidate_profile_ids(self, db: AsyncSession, *, flow_code: str, explicit_profile_id: Optional[str] = None) -> List[str]:
        """Return ordered candidate profile ids.

        This is **per-request fallback** ("降级") order:
          1) explicit (if provided)
          2) flow policy (fallback_chain -> default -> allowed)
          3) vconfig.default_llm
          4) first enabled profile

        Note: capability filtering is applied via ModelRouter for (2). Runtime errors are handled by retrying next.
        """

        snap = await llm_config_cache.ensure_loaded(db)
        ordered: List[str] = []

        def _add(pid: Optional[str]) -> None:
            if not pid:
                return
            pid2 = str(pid)
            if pid2 in ordered:
                return
            prof = snap.profiles.get(pid2)
            if prof is None or not prof.is_enabled:
                return
            ordered.append(pid2)

        # (1)
        _add(explicit_profile_id)

        # (2)
        rr = await ModelRouter.route(db, flow_code=str(flow_code), need_stream=False)
        if rr.candidates:
            for pid in rr.candidates:
                _add(pid)
        if rr.ok and rr.profile_id:
            _add(rr.profile_id)

        # (3)
        cfg = get_vconfig()
        _add(cfg.default_llm or None)

        # (4)
        for pid, prof in snap.profiles.items():
            if prof.is_enabled:
                _add(pid)
                break

        return ordered

    @staticmethod
    def _build_module_prompt(*, module_code: str, output_payload: Dict[str, Any], evidence: List[Dict[str, Any]]) -> str:
        ctx = {
            "module_code": module_code,
            "output": _safe_json(output_payload, max_list=40, max_str=800),
            "evidence": _safe_json(evidence, max_list=30, max_str=500),
        }

        return (
            "你是电商VOC分析师。只能使用我提供的结构化数据(output)与证据(evidence)，不要编造不存在的信息。\n"
            "请输出一段中文Markdown，总结该模块的关键发现、问题点与可执行建议。\n"
            "要求：\n"
            "- 必须引用数据点（如评分/占比/数量等），并在适当处引用 evidence_id 或 source_id 作为证据索引。\n"
            "- 若数据不足，请明确写出限制。\n"
            "- 不要输出多余的免责声明。\n\n"
            "输入如下（JSON）：\n"
            f"{json.dumps(ctx, ensure_ascii=False)}\n"
        )

    @staticmethod
    def _build_report_prompt(*, report_payload: Dict[str, Any]) -> str:
        ctx = {
            "report": _safe_json(report_payload, max_list=30, max_str=800),
        }
        return (
            "你是电商VOC分析师。只能使用我提供的report JSON（它来自多个模块的输出与证据统计），不要编造。\n"
            "请输出中文Markdown，给出：\n"
            "1) 管理层摘要（3-5条）\n"
            "2) 主要风险/痛点（带数据或模块引用）\n"
            "3) Top 5 可执行行动建议（按优先级排序，说明预期影响）\n"
            "4) 数据限制\n\n"
            "输入如下（JSON）：\n"
            f"{json.dumps(ctx, ensure_ascii=False)}\n"
        )

    async def summarize_module(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        module_code: str,
        flow_code: Optional[str] = None,
        model_profile_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Return (ok, summary_text). Writes back to output if ok or failed (meta only)."""

        cfg = get_vconfig()
        if not cfg.enable_llm:
            return False, None

        out = await VocRepository.get_output(db, job_id=int(job_id), module_code=str(module_code))
        if out is None:
            return False, None

        payload = dict(out.payload_json or {})

        ev_rows = await VocRepository.list_evidence(db, job_id=int(job_id), module_code=str(module_code), limit=self.max_evidence, offset=0)
        evidence = []
        for r in ev_rows:
            evidence.append(
                {
                    "evidence_id": int(r.evidence_id),
                    "source_type": str(r.source_type),
                    "source_id": int(r.source_id),
                    "kind": str(r.kind) if r.kind is not None else None,
                    "snippet": str(r.snippet),
                    "meta": dict(r.meta_json or {}),
                }
            )

        flow = str(flow_code or self.FLOW_MODULE_SUMMARY)
        candidates = await self._candidate_profile_ids(db, flow_code=flow, explicit_profile_id=model_profile_id)
        ai_meta_base = {
            "enabled": True,
            "flow_code": flow,
            "prompt_version": self.PROMPT_VERSION,
            "generated_at": _now_ts(),
            "candidates": candidates,
        }

        if not candidates:
            # No available model config
            payload.setdefault("meta", {})
            if isinstance(payload["meta"], dict):
                payload["meta"]["ai"] = {**ai_meta_base, "status": "skipped", "reason": "no_model_profile"}
            await VocRepository.upsert_output(db, job_id=int(job_id), module_code=str(module_code), payload_json=payload, schema_version=int(out.schema_version))
            return False, None

        prompt = self._build_module_prompt(module_code=str(module_code), output_payload=payload, evidence=evidence)

        errors: List[str] = []
        for idx, pid in enumerate(candidates):
            try:
                req = LlmRequest(
                    use_case="voc.module_summary",
                    model_profile_id=str(pid),
                    stream=False,
                    messages=[LlmMessage(role=LlmRole.user, content=prompt)],
                    extra={"flow_code": flow, "job_id": int(job_id), "module_code": str(module_code), "fallback_index": idx},
                )
                resp = await llm_executor.generate(db=db, req=req)
                summary = (resp.text or "").strip() or None

                payload["ai_summary"] = summary
                payload.setdefault("meta", {})
                if isinstance(payload["meta"], dict):
                    payload["meta"]["ai"] = {
                        **ai_meta_base,
                        "status": "ok" if summary else "empty",
                        "profile_id": str(pid),
                        "fallback_index": idx,
                        "provider": resp.provider,
                        "model": resp.model,
                        "usage": resp.usage,
                    }

                await VocRepository.upsert_output(
                    db,
                    job_id=int(job_id),
                    module_code=str(module_code),
                    payload_json=payload,
                    schema_version=int(out.schema_version),
                )
                return bool(summary), summary
            except Exception as e:
                errors.append(str(e))
                continue

        # All candidates failed (best-effort)
        payload.setdefault("meta", {})
        if isinstance(payload["meta"], dict):
            payload["meta"]["ai"] = {**ai_meta_base, "status": "failed", "errors": errors[-3:]}
        await VocRepository.upsert_output(db, job_id=int(job_id), module_code=str(module_code), payload_json=payload, schema_version=int(out.schema_version))
        return False, None

    async def summarize_modules(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        module_codes: List[str],
        model_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Summarize a list of modules. Returns stats."""

        ok = 0
        failed = 0
        skipped = 0

        for mc in module_codes:
            success, _ = await self.summarize_module(db, job_id=int(job_id), module_code=str(mc), model_profile_id=model_profile_id)
            if success:
                ok += 1
            else:
                # can be failed or skipped; distinguish by meta in payload (optional)
                out = await VocRepository.get_output(db, job_id=int(job_id), module_code=str(mc))
                meta = (out.payload_json or {}).get("meta") if out else None
                ai = meta.get("ai") if isinstance(meta, dict) else None
                if isinstance(ai, dict) and ai.get("status") == "skipped":
                    skipped += 1
                else:
                    failed += 1

        return {"ok": ok, "failed": failed, "skipped": skipped}

    async def summarize_report(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        model_profile_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:

        cfg = get_vconfig()
        if not cfg.enable_llm:
            return False, None

        out = await VocRepository.get_output(db, job_id=int(job_id), module_code="report.v1")
        if out is None:
            return False, None

        payload = dict(out.payload_json or {})
        candidates = await self._candidate_profile_ids(db, flow_code=self.FLOW_REPORT_SUMMARY, explicit_profile_id=model_profile_id)
        ai_meta_base = {
            "enabled": True,
            "flow_code": self.FLOW_REPORT_SUMMARY,
            "prompt_version": self.PROMPT_VERSION,
            "generated_at": _now_ts(),
            "candidates": candidates,
        }

        if not candidates:
            payload.setdefault("meta", {})
            if isinstance(payload["meta"], dict):
                payload["meta"]["ai"] = {**ai_meta_base, "status": "skipped", "reason": "no_model_profile"}
            await VocRepository.upsert_output(db, job_id=int(job_id), module_code="report.v1", payload_json=payload, schema_version=int(out.schema_version))
            return False, None

        prompt = self._build_report_prompt(report_payload=payload)

        errors: List[str] = []
        for idx, pid in enumerate(candidates):
            try:
                req = LlmRequest(
                    use_case="voc.report_summary",
                    model_profile_id=str(pid),
                    stream=False,
                    messages=[LlmMessage(role=LlmRole.user, content=prompt)],
                    extra={"flow_code": self.FLOW_REPORT_SUMMARY, "job_id": int(job_id), "module_code": "report.v1", "fallback_index": idx},
                )
                resp = await llm_executor.generate(db=db, req=req)
                summary = (resp.text or "").strip() or None
                payload["ai_summary"] = summary
                payload.setdefault("meta", {})
                if isinstance(payload["meta"], dict):
                    payload["meta"]["ai"] = {
                        **ai_meta_base,
                        "status": "ok" if summary else "empty",
                        "profile_id": str(pid),
                        "fallback_index": idx,
                        "provider": resp.provider,
                        "model": resp.model,
                        "usage": resp.usage,
                    }
                await VocRepository.upsert_output(db, job_id=int(job_id), module_code="report.v1", payload_json=payload, schema_version=int(out.schema_version))
                return bool(summary), summary
            except Exception as e:
                errors.append(str(e))
                continue

        payload.setdefault("meta", {})
        if isinstance(payload["meta"], dict):
            payload["meta"]["ai"] = {**ai_meta_base, "status": "failed", "errors": errors[-3:]}
        await VocRepository.upsert_output(db, job_id=int(job_id), module_code="report.v1", payload_json=payload, schema_version=int(out.schema_version))
        return False, None
