"""Load configuration from env and optional YAML."""
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _load_yaml() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            out = yaml.safe_load(f)
            return out if isinstance(out, dict) else {}
    except Exception:
        return {}


_config = _load_yaml()


def get_groq_model() -> str:
    """Prefer MODEL_NAME then GROQ_MODEL from env, then config.yaml, then default. Never empty."""
    out = (
        (os.environ.get("MODEL_NAME") or "").strip()
        or (os.environ.get("GROQ_MODEL") or "").strip()
        or (_config.get("groq") or {}).get("model") or "llama-3.3-70b-versatile"
    )
    return str(out).strip() if out else "llama-3.3-70b-versatile"


def get_guards_config() -> dict[str, Any]:
    g = _config.get("guards")
    return g if isinstance(g, dict) else {}


def is_guard_enabled(guard_name: str) -> bool:
    if not guard_name or not isinstance(guard_name, str):
        return False
    guards = get_guards_config()
    return bool((guards.get(guard_name) or {}).get("enabled", False))


def get_guard_model(guard_name: str) -> str:
    if not guard_name or not isinstance(guard_name, str):
        return "phi3"
    guards = get_guards_config()
    out = (guards.get(guard_name) or {}).get("model") or "phi3"
    return str(out).strip() if out else "phi3"


def get_guard_timeout_seconds() -> int:
    """Per-guard timeout in seconds. Default 45."""
    try:
        v = _config.get("guard_timeout_seconds", 45)
        return max(10, min(300, int(v)))
    except (TypeError, ValueError):
        return 45


def get_on_safety_timeout() -> str:
    """When safety guard times out: 'flag' = show response and mark unverified (default); 'block' = do not show."""
    v = (_config.get("on_safety_timeout") or "flag").strip().lower()
    return "block" if v == "block" else "flag"
