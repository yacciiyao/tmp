# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC callback token utilities.

from __future__ import annotations

import base64
import hashlib
import hmac

from infrastructures.vconfig import vconfig


def build_callback_token(*, job_id: int) -> str:
    """Create a stable HMAC token for spider callbacks.

    We intentionally keep it deterministic (job_id -> token) so that we
    don't need extra DB state.
    """

    secret = str(vconfig.jwt_secret_key).encode("utf-8")
    msg = f"voc:{int(job_id)}".encode("utf-8")
    digest = hmac.new(secret, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def verify_callback_token(*, job_id: int, token: str | None) -> bool:
    if token is None:
        return False
    expect = build_callback_token(job_id=int(job_id))
    # constant-time compare
    return hmac.compare_digest(expect, str(token))
