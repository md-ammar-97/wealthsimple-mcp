from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pulse.utils.llm import call_llm, JSONParseError
from pulse.utils.logging import log
from pulse.analysis.classify import THEME_LABELS

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _trim_at_sentence_boundary(text: str, max_chars: int) -> str:
    """Trim text to max_chars at the last sentence boundary (EC-30)."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    for end_char in (". ", "! ", "? "):
        idx = truncated.rfind(end_char)
        if idx > 10:  # ensure something meaningful remains
            return truncated[:idx + 1].strip()
    # Fall back to last word boundary
    last_space = truncated.rfind(" ")
    return truncated[:last_space].strip() if last_space > 0 else truncated.strip()


def generate_actions(
    top_themes: list[str],
    quote_records: list[dict],
    config: Any,
    run_id: str = "dry-run",
) -> list[dict]:
    """
    Generate 3 distinct action ideas linked to the top themes.
    Returns list of ActionRecord dicts.
    """
    max_action_chars = getattr(config, "max_action_chars", 200)
    expected_count = min(3, len(top_themes))

    # Build {theme: quote} map for the prompt
    quote_by_theme: dict[str, str] = {}
    for qr in quote_records:
        quote_by_theme[qr["theme"]] = qr.get("quote", "")

    theme_lines = []
    for theme in top_themes[:3]:
        quote = quote_by_theme.get(theme, "(no quote available)")
        theme_lines.append(f'Theme: "{theme}"\nUser quote: "{quote}"')

    system_prompt = _load_prompt("generate_actions.txt")
    prompt = "\n\n".join(theme_lines)

    result = None
    for attempt in range(getattr(config, "max_retries", 3)):
        try:
            raw = call_llm(prompt, system_prompt, config)
            if isinstance(raw, dict):
                raw = [raw]
            result = raw
            break
        except (JSONParseError, Exception) as exc:
            log(run_id, "action_gen", "llm_error", attempt=attempt, error=str(exc))

    if result is None:
        log(run_id, "action_gen", "action_gen_failed_no_result")
        return []

    actions: list[dict] = []
    for entry in result:
        action_text = str(entry.get("action", "")).strip()
        linked_theme = str(entry.get("linked_theme", "")).strip()

        if not action_text:
            continue

        # EC-30: trim at sentence boundary if over max_action_chars
        if len(action_text) > max_action_chars:
            trimmed = _trim_at_sentence_boundary(action_text, max_action_chars)
            log(run_id, "action_gen", "action_trimmed",
                original_len=len(action_text), trimmed_len=len(trimmed))
            action_text = trimmed

        # Validate linked_theme is in enum and in top 3
        if linked_theme not in THEME_LABELS:
            # Try to match to a top theme by position
            if len(actions) < len(top_themes):
                linked_theme = top_themes[len(actions)]
                log(run_id, "action_gen", "linked_theme_fallback",
                    original=entry.get("linked_theme"), fallback=linked_theme)
            else:
                continue

        if linked_theme not in top_themes:
            # Re-link to the closest top theme
            idx = len(actions) % len(top_themes)
            linked_theme = top_themes[idx]

        actions.append({"action": action_text, "linked_theme": linked_theme})

        if len(actions) >= expected_count:
            break

    log(run_id, "action_gen", "action_gen_complete",
        expected=expected_count, produced=len(actions))

    return actions
