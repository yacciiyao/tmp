# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from infrastructures.embedding.dummy_embedder import DummyEmbedder
from infrastructures.embedding.sbert_embedder import SentenceTransformerEmbedder
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger

_embedder_instance = None


def create_embedder():
    global _embedder_instance
    if _embedder_instance is not None:
        return _embedder_instance

    backend = vconfig.embedding_backend.strip().lower()
    vlogger.info("init embedder backend=%s", backend)

    if backend == "sentence_transformer":
        _embedder_instance = SentenceTransformerEmbedder(
            model_name=vconfig.embedding_model_name,
            dim=vconfig.embedding_dim,
        )
        vlogger.info("embedder=SentenceTransformer model=%s", vconfig.embedding_model_name)
        return _embedder_instance

    _embedder_instance = DummyEmbedder(dim=vconfig.embedding_dim)
    vlogger.info("embedder=DummyEmbedder dim=%s", vconfig.embedding_dim)
    return _embedder_instance
