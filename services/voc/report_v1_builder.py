# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Report builder (v1) - aggregate module outputs into a single payload

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.voc_output_domain import VocModuleOutput
from infrastructures.db.repository.voc_repository import VocRepository


class ReportV1Builder:
    """Aggregate module outputs/evidence into a report payload.

    Contract: report MUST read from stg_voc_outputs / stg_voc_evidence only.
    """

    MODULE_CODE = "report.v1"
    SCHEMA_VERSION = 1

    @staticmethod
    async def build(db: AsyncSession, *, job_id: int) -> VocModuleOutput:
        outs = await VocRepository.list_outputs(db, job_id=int(job_id), limit=500, offset=0)

        modules: Dict[str, Any] = {}
        order: List[str] = []
        for o in outs:
            mc = str(o.module_code)
            if mc == ReportV1Builder.MODULE_CODE:
                continue
            order.append(mc)
            modules[mc] = dict(o.payload_json or {})

        # evidence counts per module (lightweight, no heavy payload)
        # NOTE: list_evidence returns full rows; for now we just count in-memory.
        ev_rows = await VocRepository.list_evidence(db, job_id=int(job_id), module_code=None)
        ev_count: Dict[str, int] = {}
        for r in ev_rows:
            ev_count[str(r.module_code)] = ev_count.get(str(r.module_code), 0) + 1

        available = len(modules) > 0

        # best-effort meta: take site_code/asins from any module meta
        merged_meta: Dict[str, Any] = {}
        for mc in order:
            payload = modules.get(mc) or {}
            meta = payload.get("meta") if isinstance(payload, dict) else None
            if isinstance(meta, dict):
                # do not overwrite once set
                for k, v in meta.items():
                    if k not in merged_meta:
                        merged_meta[k] = v

        return VocModuleOutput(
            available=available,
            module_code=ReportV1Builder.MODULE_CODE,
            schema_version=ReportV1Builder.SCHEMA_VERSION,
            data={
                "module_order": order,
                "modules": modules,
                "evidence_counts": ev_count,
            },
            meta=merged_meta,
            ai_summary=None,
        )
