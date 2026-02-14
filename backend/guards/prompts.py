"""Shared prompt rules for all guards: unambiguous, error-friendly, prefer pass/flag when uncertain."""

# Appended to every guard system prompt so SLMs behave consistently and never break the app.
GUARD_OUTPUT_RULES = """
Output format: On the first line output exactly one word: pass, flag, or block (only when your instructions allow block).
When the situation is ambiguous or you are unsure, prefer pass or flag; use block only when clearly required by the rules above.
Do not output anything before the verdict word. Optionally on the next line add a very short reason."""


def build_guard_prompt(instructions: str) -> str:
    """Combine guard-specific instructions with shared output rules. Ensures consistent, parseable output."""
    return (instructions.strip() + "\n\n" + GUARD_OUTPUT_RULES.strip()).strip()
