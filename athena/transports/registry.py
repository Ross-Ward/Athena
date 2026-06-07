"""Transport factory — pick a backend from the environment.

Order of preference: explicit offline flag → Anthropic → OpenAI-compatible →
offline-deterministic fallback. The result always satisfies ``ModelTransport``,
so the orchestrator never has to special-case "no key".
"""
from __future__ import annotations

import os

from .anthropic import AnthropicTransport
from .base import ModelTransport
from .offline import OfflineTransport
from .openai_compat import OpenAICompatTransport


def _truthy(val: str | None) -> bool:
    return bool(val) and val.strip().lower() not in {"", "0", "false", "no"}


def select_transport(force_offline: bool | None = None) -> ModelTransport:
    """Return the best available transport.

    ``force_offline`` overrides everything; if None, honours ``ATHENA_OFFLINE``.
    """
    offline = force_offline
    if offline is None:
        offline = _truthy(os.getenv("ATHENA_OFFLINE"))
    if offline:
        return OfflineTransport()

    anth = AnthropicTransport()
    if anth.available:
        return anth

    oai = OpenAICompatTransport()
    if oai.available:
        return oai

    return OfflineTransport()
