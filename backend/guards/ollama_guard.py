"""Shared Ollama call and verdict parsing for guards. Safe against empty/ambiguous output."""
import json
import logging
import re
import time
import ollama
from backend.guards.base import GuardResult

logger = logging.getLogger("guardrails.guards")

# When parsing fails or is ambiguous, default to flag (not block) so the app never blocks incorrectly.
DEFAULT_VERDICT = "flag"
DEFAULT_REASON = "Unclear response"


def _safe_str(s: str | None) -> str:
    """Normalize to a safe string for parsing."""
    if s is None:
        return ""
    try:
        return str(s).strip() if isinstance(s, str) else ""
    except Exception:
        return ""


def _parse_verdict(text: str) -> tuple[str, str]:
    """
    Parse SLM output for verdict (pass/flag/block) and reason. Never raises; returns (DEFAULT_VERDICT, reason) on failure.
    """
    raw = _safe_str(text)
    reason = ""

    # First line only word: pass, flag, or block
    lines = raw.split("\n")
    first_line = _safe_str(lines[0] if lines else "").lower()
    if first_line in ("pass", "flag", "block"):
        rest = "\n".join(lines[1:]).strip()
        reason = rest[:200] if rest else ""
        return first_line, reason

    # JSON-like: {"verdict": "pass", ...}
    try:
        start = raw.find("{")
        if start != -1:
            end = raw.rfind("}") + 1
            if end > start:
                obj = json.loads(raw[start:end])
                v = _safe_str(obj.get("verdict") or obj.get("result") or "").lower()
                if v in ("pass", "flag", "block"):
                    r = obj.get("reason") or obj.get("explanation") or ""
                    return v, _safe_str(str(r))[:200]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Fallback: first occurrence in text; prefer pass when only "pass" appears to avoid false block
    raw_lower = raw.lower()
    if "block" in raw_lower:
        verdict = "block"
    elif "flag" in raw_lower:
        verdict = "flag"
    else:
        verdict = "pass"
    for line in lines:
        line = _safe_str(line)
        if line and not re.match(r"^(pass|flag|block)\s*:?\s*$", line, re.I):
            reason = line[:200]
            break
    if not reason and raw:
        reason = raw[:200]
    return verdict, reason


def call_ollama_guard(
    guard_name: str,
    system_prompt: str,
    user_content: str,
    model: str,
) -> GuardResult:
    """
    Call Ollama with system + user message; parse response for verdict. Never raises; returns flag on any failure.
    """
    t0 = time.perf_counter()
    guard_name = _safe_str(guard_name) or "guard"
    model = _safe_str(model) or "phi3"
    system_prompt = _safe_str(system_prompt) or "Classify as pass, flag, or block."
    user_content = _safe_str(user_content) or "(no content)"
    logger.info("Guard %s starting (model=%s)", guard_name, model)
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        msg = getattr(response, "message", None)
        if msg is None and isinstance(response, dict):
            msg = response.get("message")
        text = (getattr(msg, "content", None) if msg is not None else None) or (msg.get("content") if isinstance(msg, dict) else None) or ""
        text = _safe_str(text)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.warning("Guard %s failed after %.2fs: %s", guard_name, elapsed, e)
        return GuardResult(name=guard_name, verdict=DEFAULT_VERDICT, reason=f"Ollama error: {e}")

    try:
        verdict, reason = _parse_verdict(text)
        if verdict not in ("pass", "flag", "block"):
            verdict, reason = DEFAULT_VERDICT, reason or DEFAULT_REASON
    except Exception as e:
        logger.warning("Guard %s parse failed: %s", guard_name, e)
        verdict, reason = DEFAULT_VERDICT, DEFAULT_REASON
    elapsed = time.perf_counter() - t0
    logger.info("Guard %s done in %.2fs: %s", guard_name, elapsed, verdict)
    return GuardResult(name=guard_name, verdict=verdict, reason=reason or "")
