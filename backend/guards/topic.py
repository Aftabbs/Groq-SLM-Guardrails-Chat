"""Topic relevance guard using a local SLM via Ollama."""
from backend.guards.base import GuardResult
from backend.guards.ollama_guard import call_ollama_guard
from backend.guards.prompts import build_guard_prompt

TOPIC_SYSTEM = build_guard_prompt("""You are a topic relevance classifier. Given the user message and the AI model's response, decide if the response is appropriate.
- pass: The response is appropriate. Includes: answering the question; replying to greetings ("Hi", "Hey", "Hello") with a friendly greeting or offer to help; acknowledging the user; staying on subject. Greetings and small talk deserve a friendly reply — that is on-topic.
- flag: Somewhat relevant but goes off on a tangent or adds a lot of unrelated content.
- block: Only if the response clearly ignores the user (e.g. user asked about X and the model talks only about unrelated Y with no acknowledgment). Do NOT block polite responses to greetings or open-ended messages. When in doubt, use pass or flag.""")


def topic_guard(user_message: str, model_response: str, ollama_model: str) -> GuardResult:
    user_content = "User message:\n{}\n\nModel response:\n{}".format(
        (user_message or "").strip() or "(empty)",
        (model_response or "").strip() or "(empty)",
    )
    return call_ollama_guard("topic", TOPIC_SYSTEM, user_content, ollama_model)
