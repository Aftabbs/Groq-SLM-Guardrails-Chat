"""Groq API client for chat completion."""
import logging
import os
import time
from groq import Groq

from backend.config import get_groq_model

logger = logging.getLogger("guardrails.groq")

_client: Groq | None = None

# Default system prompt for the assistant
DEFAULT_SYSTEM = (
    "You are a helpful assistant. Answer the user's question clearly and concisely."
)


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        _client = Groq(api_key=api_key)
    return _client


def chat_completion(
    user_message: str,
    system_prompt: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    """
    Get chat completion from Groq. Supports multi-turn via history.
    history: list of {"role": "user"|"assistant", "content": "..."}
    """
    client = get_groq_client()
    model = get_groq_model()
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        for h in history:
            role = h.get("role", "user")
            if role not in ("user", "assistant", "system"):
                continue
            content = h.get("content") or ""
            if content:
                messages.append({"role": role, "content": content})
    user_message = (user_message or "").strip()
    messages.append({"role": "user", "content": user_message or "(empty)"})
    logger.info("Groq chat.completions.create model=%s messages=%d", model, len(messages))
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    elapsed = time.perf_counter() - t0
    try:
        choices = getattr(response, "choices", None) or []
        first = choices[0] if choices else None
        msg = getattr(first, "message", None) if first else None
        content = getattr(msg, "content", None) if msg else None
        text = (content or "").strip()
    except (IndexError, TypeError, AttributeError):
        text = ""
    logger.info("Groq response in %.2fs len=%d", elapsed, len(text))
    return text if isinstance(text, str) else ""
