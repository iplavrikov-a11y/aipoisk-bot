"""Bridge TenderLex outreach to the shared bot-suite suppression registry."""

from __future__ import annotations

import importlib.util
import os
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType


DEFAULT_BOTS_ROOT = Path("/root/projects/bots_tenderlex")
DEFAULT_SHARED_DB = DEFAULT_BOTS_ROOT / "data" / "global_outreach.db"


def shared_outreach_db_path() -> Path:
    """Return the configured shared registry without touching it."""
    return Path(os.getenv("GLOBAL_OUTREACH_DB", str(DEFAULT_SHARED_DB)))


def _load_shared_module(filename: str, module_name: str) -> ModuleType:
    bots_root = Path(os.getenv("TENDERLEX_BOTS_ROOT", str(DEFAULT_BOTS_ROOT)))
    root_text = str(bots_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    module_path = bots_root / "shared" / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Shared module is unavailable: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _shared_suppression_module() -> ModuleType:
    return _load_shared_module("suppression.py", "tenderlex_shared_suppression")


@lru_cache(maxsize=1)
def _shared_unsubscribe_module() -> ModuleType:
    return _load_shared_module("unsubscribe.py", "tenderlex_shared_unsubscribe")


def get_shared_suppression_reason(email: str) -> str | None:
    """Read the cross-bot suppression reason, raising if it cannot be checked."""
    module = _shared_suppression_module()
    return module.get_suppression_reason(shared_outreach_db_path(), email, require_registry=True)


def record_shared_suppression(email: str, reason: str, source: str) -> None:
    """Persist a permanent suppression to the cross-bot registry."""
    module = _shared_suppression_module()
    module.record_suppression(shared_outreach_db_path(), email, reason, source)


def verify_unsubscribe_token(email: str, token: str) -> bool:
    """Verify a signed public marketing-unsubscribe request without writing state."""
    return bool(_shared_unsubscribe_module().verify_unsubscribe_token(email, token))


def build_unsubscribe_url(email: str) -> str:
    """Return a signed unsubscribe URL, with the shared mailto fallback on key errors."""
    try:
        return str(_shared_unsubscribe_module().build_unsubscribe_url(email))
    except Exception:
        return "mailto:info@tenderlex.ru?subject=Unsubscribe"
