"""Base types and orchestration for guards."""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Callable, List

from backend.config import get_guard_model, get_guard_timeout_seconds, get_on_safety_timeout, is_guard_enabled

logger = logging.getLogger("guardrails.guards")

# Safety guard name for timeout policy
SAFETY_GUARD_NAME = "safety"


@dataclass
class GuardResult:
    """Result from a single guard."""
    name: str
    verdict: str  # "pass" | "flag" | "block"
    reason: str = ""
    model: str = ""  # Ollama model that ran this guard (e.g. phi3, llama3.2)


def run_guards(
    user_message: str,
    model_response: str,
    guard_fns: List[tuple[str, Callable[[str, str, str], GuardResult]]],
) -> List[GuardResult]:
    """
    Run enabled guards in parallel with a per-guard timeout.
    Order of results follows guard_fns order.
    """
    user_message = (user_message or "").strip() if user_message is not None else ""
    model_response = (model_response or "").strip() if model_response is not None else ""
    tasks = []
    for name, fn in guard_fns:
        if not is_guard_enabled(name):
            continue
        model = get_guard_model(name)
        tasks.append((name, fn, model))

    if not tasks:
        return []

    timeout_sec = get_guard_timeout_seconds()
    on_safety_timeout = get_on_safety_timeout()
    logger.info("Running %d guards in parallel (timeout=%ss each, on_safety_timeout=%s): %s", len(tasks), timeout_sec, on_safety_timeout, [t[0] for t in tasks])
    results: List[GuardResult] = [None] * len(tasks)  # placeholder to keep order

    def run_one(name: str, fn: Callable, model: str) -> GuardResult:
        try:
            r = fn(user_message, model_response, model)
            return GuardResult(name=r.name, verdict=r.verdict, reason=r.reason, model=model)
        except Exception as e:
            logger.warning("Guard %s exception: %s", name, e)
            return GuardResult(name=name, verdict="flag", reason=f"Guard error: {e}", model=model)

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(run_one, name, fn, model): (name, i, model)
            for (name, fn, model), i in zip(tasks, range(len(tasks)))
        }
        for future in futures:
            name, idx, model = futures[future]
            try:
                result = future.result(timeout=timeout_sec)
                results[idx] = result
            except FuturesTimeoutError:
                logger.warning("Guard %s timed out after %ss", name, timeout_sec)
                if name == SAFETY_GUARD_NAME and on_safety_timeout == "block":
                    results[idx] = GuardResult(
                        name=name,
                        verdict="block",
                        reason="Safety check timed out; response not verified.",
                        model=model,
                    )
                else:
                    results[idx] = GuardResult(name=name, verdict="flag", reason="Timeout", model=model)
            except Exception as e:
                logger.warning("Guard %s failed: %s", name, e)
                results[idx] = GuardResult(name=name, verdict="flag", reason=str(e), model=model)

    return [r for r in results if r is not None]


def any_block(results: List[GuardResult]) -> bool:
    return any(r.verdict == "block" for r in results)


def get_blocking_guard(results: List[GuardResult]) -> GuardResult | None:
    for r in results:
        if r.verdict == "block":
            return r
    return None
