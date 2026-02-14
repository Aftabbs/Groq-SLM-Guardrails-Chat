"""Safety / toxicity guard using a local SLM via Ollama."""
from backend.guards.base import GuardResult
from backend.guards.ollama_guard import call_ollama_guard
from backend.guards.prompts import build_guard_prompt

SAFETY_SYSTEM = build_guard_prompt("""You are a content safety classifier. Given the user message and the AI model's response, classify the response:
- pass: Safe, helpful, not harmful or toxic. When in doubt, use pass.
- flag: Borderline (e.g. sensitive topic but handled carefully).
- block: Only if the response clearly contains harmful, toxic, unsafe, or clearly inappropriate content. If ambiguous, use flag instead of block.""")


def safety_guard(user_message: str, model_response: str, ollama_model: str) -> GuardResult:
    user_content = "User message:\n{}\n\nModel response:\n{}".format(
        (user_message or "").strip() or "(empty)",
        (model_response or "").strip() or "(empty)",
    )
    return call_ollama_guard("safety", SAFETY_SYSTEM, user_content, ollama_model)
