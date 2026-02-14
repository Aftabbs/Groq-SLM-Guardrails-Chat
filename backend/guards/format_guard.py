"""Format / structure guard using a local SLM via Ollama."""
from backend.guards.base import GuardResult
from backend.guards.ollama_guard import call_ollama_guard
from backend.guards.prompts import build_guard_prompt

FORMAT_SYSTEM = build_guard_prompt("""You are a response format checker. Classify the AI response:
- pass: Reasonable length and structure (readable paragraphs or clear sentences). Short replies (e.g. greetings) are fine. When in doubt, use pass.
- flag: Clearly too long, too fragmented, or odd formatting. Do not use block; this guard only uses pass or flag.""")


def format_guard(user_message: str, model_response: str, ollama_model: str) -> GuardResult:
    user_content = "Model response to check:\n{}".format((model_response or "").strip() or "(empty)")
    r = call_ollama_guard("format", FORMAT_SYSTEM, user_content, ollama_model)
    if r.verdict == "block":
        return GuardResult(name=r.name, verdict="flag", reason=r.reason or "Format guard does not block")
    return r
