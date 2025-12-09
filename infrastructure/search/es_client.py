# -*- coding: utf-8 -*-
# @File: infrastructure/search/es_client.py
# @Author: yaccii
# @Description:
#   ESClient 当前实现为「可切换的简化版」：
#   - 默认：NO-OP 模式，不依赖任何 Elasticsearch 实例，不抛异常
#   - 将来要启用 BM25 / ES，只需要在本文件中补全 TODO 部分，无需改 RAG 其它代码

from __future__ import annotations

from typing import Any, Dict, List, Optional

from infrastructure import mlogger
from infrastructure.config import settings


class ESClient:
    """
    统一的 ES 访问封装。

    当前阶段：
    - 默认走 no-op 模式：不真正连 ES，只打日志，避免影响 RAG 主链路
    - 之后如需 BM25，可在本类中接入真正的 Elasticsearch / OpenSearch 客户端
    """

    def __init__(self) -> None:
        # 从配置里读一点“意向”，但即使配置了也暂时不真正调用 ES
        # 这里用 getattr 做兜底，不强制你现在就去改 config.py / .env
        self.enabled: bool = bool(getattr(settings, "es_enabled", False))
        self.base_url: Optional[str] = getattr(settings, "es_url", None)

        # 目前统一认为「功能关闭」，只保留日志开关
        if not self.enabled or not self.base_url:
            mlogger.info(
                "ESClient",
                "__init__",
                msg="ES disabled (no-op mode)，当前不会真正连接 Elasticsearch",
                es_enabled=self.enabled,
                es_url=self.base_url,
            )
            self._active = False
        else:
            # 预留将来启用 ES 的逻辑
            mlogger.info(
                "ESClient",
                "__init__",
                msg="ES configured，但当前实现仍为 no-op，需要在 ESClient 中补全实际调用逻辑",
                es_enabled=self.enabled,
                es_url=self.base_url,
            )
            self._active = False  # 先硬关闭，避免误连半残环境

    # ------------------------------------------------------------------
    # 索引管理
    # ------------------------------------------------------------------

    async def ensure_index(self, index: Optional[str], corpus_id: int) -> str:
        """
        确保索引存在：
        - 现在：no-op，只返回一个规范化索引名，不抛异常
        - 未来：这里再加真正的索引创建逻辑（mapping / analyzer 等）
        """
        # 规范化索引名：优先用传入 index，否则用前缀 + corpus_id
        es_index = index or f"vs_{corpus_id}"

        if not self._active:
            # 仅打 debug 级别日志，不再报异常
            mlogger.info(
                "ESClient",
                "ensure_index",
                msg="skip ensure_index (ES no-op mode)",
                index=es_index,
            )
            return es_index

        # TODO: 未来如果要接 ES，可以在这里实现：
        # try:
        #     # 1. 检查索引是否存在
        #     # 2. 不存在则创建（含 mapping / analyzer）
        # except Exception as e:
        #     mlogger.warning(
        #         "ESClient",
        #         "ensure_index",
        #         msg=f"ensure_index error: {e!r}",
        #         index=es_index,
        #     )
        #     raise

        return es_index

    # ------------------------------------------------------------------
    # 写入（索引 Chunk 文本，用于 BM25）
    # ------------------------------------------------------------------

    async def index_chunks(
        self,
        *,
        index: Optional[str],
        corpus_id: int,
        docs: List[Dict[str, Any]],
        refresh: bool = False,
    ) -> None:
        """
        批量写入 chunk 文本到 ES：
        - 现在：no-op，只打日志，什么都不写
        - 将来：在这里实现 bulk API 调用
        """
        es_index = await self.ensure_index(index, corpus_id)

        if not self._active:
            mlogger.info(
                "ESClient",
                "index_chunks",
                msg="skip index_chunks (ES no-op mode)",
                index=es_index,
                count=len(docs),
            )
            return

        # TODO: 未来启用 ES 时，在这里实现 bulk 写入：
        # try:
        #     actions = [...]
        #     self._client.bulk(...)
        #     if refresh:
        #         self._client.indices.refresh(index=es_index)
        # except Exception as e:
        #     mlogger.warning(
        #         "ESClient",
        #         "index_chunks",
        #         msg=f"index_chunks error: {e!r}",
        #         index=es_index,
        #         count=len(docs),
        #     )

    # ------------------------------------------------------------------
    # 检索（RAG 检索阶段的 BM25 分支）
    # ------------------------------------------------------------------

    async def search(
        self,
        *,
        index: Optional[str],
        corpus_id: int,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        BM25 检索：
        - 现在：no-op，直接返回空列表
        - 将来：在这里接 ES search + 打分逻辑
        """
        es_index = index or f"vs_{corpus_id}"

        if not self._active:
            mlogger.info(
                "ESClient",
                "search",
                msg="skip search (ES no-op mode)",
                index=es_index,
                query=query,
                top_k=top_k,
            )
            return []

        # TODO: 未来启用 ES 时，实现搜索逻辑：
        # try:
        #     body = {...}
        #     resp = self._client.search(index=es_index, body=body)
        #     return [...]
        # except Exception as e:
        #     mlogger.warning(
        #         "ESClient",
        #         "search",
        #         msg=f"search error: {e!r}",
        #         index=es_index,
        #     )
        #     return []

    # ------------------------------------------------------------------
    # 可选：删除索引（后台管理用）
    # ------------------------------------------------------------------

    async def delete_index(self, index: str) -> None:
        if not self._active:
            mlogger.info(
                "ESClient",
                "delete_index",
                msg="skip delete_index (ES no-op mode)",
                index=index,
            )
            return

        # TODO: 未来启用 ES 时实现：
        # try:
        #     self._client.indices.delete(index=index, ignore=[400, 404])
        # except Exception as e:
        #     mlogger.warning(
        #         "ESClient",
        #         "delete_index",
        #         msg=f"delete_index error: {e!r}",
        #         index=index,
        #     )
