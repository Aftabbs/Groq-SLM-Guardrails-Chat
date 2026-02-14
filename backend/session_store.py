"""In-memory chat history per session for multi-turn conversation."""
from collections import defaultdict
from typing import Any

# session_id -> list of {"role": "user"|"assistant", "content": "..."}
# Keep last N message pairs to avoid huge context
MAX_HISTORY_MESSAGES = 20

_sessions: dict[str, list[dict[str, str]]] = defaultdict(list)


def append_exchange(session_id: str, user_message: str, assistant_message: str) -> None:
    """Append one user/assistant exchange to the session."""
    messages = _sessions[session_id]
    messages.append({"role": "user", "content": user_message})
    messages.append({"role": "assistant", "content": assistant_message})
    # Keep only last N messages (trim from start)
    if len(messages) > MAX_HISTORY_MESSAGES:
        _sessions[session_id] = messages[-MAX_HISTORY_MESSAGES:]


def get_history(session_id: str) -> list[dict[str, str]]:
    """Return conversation history for the session (last N messages)."""
    return list(_sessions[session_id])
