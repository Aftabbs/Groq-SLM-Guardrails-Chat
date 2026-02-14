from backend.guards.base import GuardResult
from backend.guards.ollama_guard import call_ollama_guard
from backend.guards.prompts import build_guard_prompt

PII_SYSTEM = build_guard_prompt("""You are a PII and sensitive data detector. Check if the AI model's response contains personal or sensitive information (e.g. email, phone, address, credentials, API keys).
- pass: No PII or sensitive data detected. Generic examples or placeholders (e.g. "user@example.com") are pass. When in doubt, use pass.
- flag: Possible real PII or sensitive data detected. Do not use block; this guard only uses pass or flag.""")


def pii_guard(user_message: str, model_response: str, ollama_model: str) -> GuardResult:
    user_content = "Model response to check:\n{}".format((model_response or "").strip() or "(empty)")
    r = call_ollama_guard("pii", PII_SYSTEM, user_content, ollama_model)
    if r.verdict == "block":
        return GuardResult(name=r.name, verdict="flag", reason=r.reason or "PII guard does not block")
    return r
