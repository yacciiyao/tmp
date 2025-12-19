# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from infrastructures.embedding.dummy_embedder import DummyEmbedder
from infrastructures.embedding.sbert_embedder import SentenceTransformerEmbedder
from infrastructures.vconfig import config

log = logging.getLogger(__name__)

_embedder_instance = None


def create_embedder():
    global _embedder_instance
    if _embedder_instance is not None:
        return _embedder_instance

    backend = config.embedding_backend.strip().lower()
    log.info("init embedder backend=%s", backend)

    if backend == "sentence_transformer":
        _embedder_instance = SentenceTransformerEmbedder(
            model_name=config.embedding_model_name,
            dim=config.embedding_dim,
        )
        log.info("embedder=SentenceTransformer model=%s", config.embedding_model_name)
        return _embedder_instance

    _embedder_instance = DummyEmbedder(dim=config.embedding_dim)
    log.info("embedder=DummyEmbedder dim=%s", config.embedding_dim)
    return _embedder_instance
