"""FastAPI app: chat endpoint and guard pipeline."""
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import get_guards_config, get_groq_model, is_guard_enabled, get_guard_model
from backend.groq_client import chat_completion, DEFAULT_SYSTEM as GROQ_DEFAULT_SYSTEM
from backend.guards import (
    run_guards,
    safety_guard,
    topic_guard,
    format_guard,
    pii_guard,
)
from backend.guards.base import GuardResult, any_block, get_blocking_guard
from backend.session_store import get_history, append_exchange

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("guardrails")

app = FastAPI(title="Groq + SLM Guardrails Chat", version="1.0.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BLOCKED_MESSAGE = "This response was blocked by a safety check."
MAX_MESSAGE_LENGTH = 32_000  # Prevent abuse; Groq has its own limits

GUARD_FNS = [
    ("safety", safety_guard),
    ("topic", topic_guard),
    ("format", format_guard),
    ("pii", pii_guard),
]


class ChatRequest(BaseModel):
    message: str
    system_prompt: str | None = None
    session_id: str | None = None
    history: list[dict[str, str]] | None = None
    skip_guards: bool = False  # If True, return Groq response only (no Ollama guards)


class GuardResultOut(BaseModel):
    name: str
    verdict: str
    reason: str
    model: str = ""  # Ollama model that ran this guard (e.g. phi3, llama3.2)


class ChatResponse(BaseModel):
    response: str
    blocked: bool
    guard_results: list[GuardResultOut]
    session_id: str
    primary_model: str = ""  # Groq model that generated the response (e.g. llama-3.3-70b-versatile)


def _ollama_models() -> list[str]:
    """Return list of available Ollama model names. ollama.list() returns a ListResponse object, not a dict."""
    try:
        import ollama
        resp = ollama.list()
        # ListResponse has .models (sequence of Model objects); each has .model (str) or .name
        models = getattr(resp, "models", None) or []
        names = []
        for m in models:
            name = getattr(m, "model", None) or getattr(m, "name", None)
            if name:
                names.append(str(name))
        return names
    except Exception as e:
        logger.warning("Could not list Ollama models: %s", e)
        return []


@app.get("/")
def index() -> FileResponse:
    """Serve the chat web app."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Static files not found")
    return FileResponse(index_path)


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check: Groq key, Ollama, and which guard models are available."""
    groq_ok = bool(os.environ.get("GROQ_API_KEY"))
    ollama_ok = False
    ollama_models: list[str] = []
    guard_models_status: dict[str, bool] = {}
    try:
        import ollama
        ollama.list()
        ollama_ok = True
        ollama_models = _ollama_models()
        for name in ("safety", "topic", "format", "pii"):
            if is_guard_enabled(name):
                model = get_guard_model(name)
                # Match by base name (e.g. phi3 matches phi3:latest)
                guard_models_status[name] = any(
                    model in m or m.startswith(model.split(":")[0])
                    for m in ollama_models
                )
    except Exception as e:
        logger.warning("Ollama health check failed: %s", e)
    logger.info(
        "Health: groq=%s ollama=%s models=%s guard_ok=%s",
        groq_ok, ollama_ok, ollama_models, guard_models_status,
    )
    return {
        "status": "ok" if groq_ok and ollama_ok else "degraded",
        "groq_configured": groq_ok,
        "ollama_available": ollama_ok,
        "groq_model": get_groq_model(),
        "guards_config": get_guards_config(),
        "ollama_models": ollama_models,
        "guard_models_available": guard_models_status,
    }


@app.on_event("startup")
def startup():
    """Log config at startup."""
    logger.info("Starting Guardrails Chat")
    logger.info("Groq model: %s", get_groq_model())
    ollama_models = _ollama_models()
    logger.info("Ollama models available: %s", ollama_models or "(none)")
    for name in ("safety", "topic", "format", "pii"):
        if is_guard_enabled(name):
            logger.info("Guard %s enabled, model=%s", name, get_guard_model(name))


def _normalize_response(text: Any) -> str:
    """Ensure response is a non-None string so the app never breaks."""
    if text is None:
        return ""
    if isinstance(text, str):
        return text.strip()
    try:
        return str(text).strip()
    except Exception:
        return ""


def _normalize_guard_reason(reason: str) -> str:
    """Strip verdict prefix and 'Reason:' from guard reason for cleaner display. Truncate to 120 chars."""
    if not reason or not isinstance(reason, str):
        return ""
    s = reason.strip()
    prefixes = ("pass.", "pass:", "flag.", "flag:", "block.", "block:", "reason:", "reason.")
    while s:
        lowered = s.lower()
        found = False
        for p in prefixes:
            if lowered.startswith(p):
                s = s[len(p):].strip()
                found = True
                break
        if not found:
            break
    return s[:120] if len(s) > 120 else s


def _guard_results_out(results: List[GuardResult]) -> List[GuardResultOut]:
    """Convert guard results to API output; never raise."""
    out = []
    for r in results or []:
        try:
            raw_reason = (r.reason or "").strip()[:500]
            reason = _normalize_guard_reason(raw_reason)
            out.append(GuardResultOut(
                name=(r.name or "guard").strip(),
                verdict=(r.verdict or "flag").strip() or "flag",
                reason=reason,
                model=(getattr(r, "model", None) or "").strip()[:100],
            ))
        except Exception:
            out.append(GuardResultOut(name="guard", verdict="flag", reason="Error", model=""))
    return out


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Multi-turn chat: Groq generates, guards validate. Validates input; never raises uncaught."""
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail=f"message too long (max {MAX_MESSAGE_LENGTH} characters)")

    t0 = time.perf_counter()
    session_id = (req.session_id or str(uuid.uuid4())).strip() or str(uuid.uuid4())
    history = req.history if isinstance(req.history, list) else get_history(session_id)
    system = (req.system_prompt or GROQ_DEFAULT_SYSTEM or "").strip() or GROQ_DEFAULT_SYSTEM
    logger.info("Chat request: len(message)=%d skip_guards=%s history_len=%d", len(message), req.skip_guards, len(history))

    try:
        raw_response = chat_completion(message, system, history=history)
    except Exception as e:
        err_msg = str(e).lower()
        logger.exception("Groq call failed: %s", e)
        if "401" in err_msg or "invalid api key" in err_msg or "expired_api_key" in err_msg:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired Groq API key. Get a new key at https://console.groq.com/keys and set GROQ_API_KEY in your .env file, then restart the app.",
            ) from e
        raise HTTPException(status_code=502, detail=str(e)) from e

    raw_response = _normalize_response(raw_response)
    t_groq = time.perf_counter() - t0
    logger.info("Groq done in %.2fs, response len=%d", t_groq, len(raw_response))

    primary_model = get_groq_model()
    if req.skip_guards:
        append_exchange(session_id, message, raw_response)
        logger.info("Chat done (skip_guards) in %.2fs", time.perf_counter() - t0)
        return ChatResponse(
            response=raw_response,
            blocked=False,
            guard_results=[],
            session_id=session_id,
            primary_model=primary_model,
        )

    logger.info("Running guards (timeout=%ss each)...", 45)
    try:
        guard_results: list[GuardResult] = run_guards(message, raw_response, GUARD_FNS)
    except Exception as e:
        logger.exception("Guard pipeline failed: %s", e)
        guard_results = [GuardResult(name="pipeline", verdict="flag", reason=f"Guards error: {e}")]

    t_guards = time.perf_counter() - t0 - t_groq
    logger.info("Guards done in %.2fs: %s", t_guards, [(r.name, r.verdict) for r in guard_results])

    if any_block(guard_results):
        blocking = get_blocking_guard(guard_results)
        safe_msg = BLOCKED_MESSAGE
        if blocking and (blocking.reason or "").strip():
            safe_msg += f" ({blocking.name}: {blocking.reason})"
        return ChatResponse(
            response=safe_msg,
            blocked=True,
            guard_results=_guard_results_out(guard_results),
            session_id=session_id,
            primary_model=primary_model,
        )

    append_exchange(session_id, message, raw_response)
    logger.info("Chat done in %.2fs total", time.perf_counter() - t0)
    return ChatResponse(
        response=raw_response,
        blocked=False,
        guard_results=_guard_results_out(guard_results),
        session_id=session_id,
        primary_model=primary_model,
    )
