from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pulse.utils.llm import call_llm_text
from pulse.utils.logging import log
from pulse.utils.word_count import count_words

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"

# Markdown control characters that must be escaped inside quote strings (EC-32).
_MD_CTRL = re.compile(r"([*_`\[\]#\\])")


class MissingUpstreamFieldError(Exception):
    pass


def _load_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _escape_markdown_in_quotes(text: str) -> str:
    """
    Escape Markdown control characters inside quoted strings on bullet lines (EC-32).
    Only touches content between the opening and closing double-quote on lines like:
        - "some **bold** text"
    """
    def _escape_inner(m: re.Match) -> str:
        prefix = m.group(1)
        inner = _MD_CTRL.sub(r"\\\1", m.group(2))
        suffix = m.group(3)
        return prefix + inner + suffix

    return re.sub(
        r'(?m)(^- ")([^"]+)(")',
        _escape_inner,
        text,
    )


def _truncate_at_word_limit(body: str, max_words: int) -> tuple[str, bool]:
    """
    Truncate *body* to at most *max_words* (EC-31).
    Prefers line boundaries; falls back to sentence boundaries for single-line bodies.
    Lines starting with '- "' (quote lines) are included whole or not at all.
    Always strips trailing blank lines.
    Returns (truncated_body, was_truncated).
    """
    # Always strip trailing blank lines
    body = body.rstrip("\n")

    if count_words(body) <= max_words:
        return body, False

    lines = body.splitlines()
    result: list[str] = []
    total = 0

    for line in lines:
        lw = len(line.split())
        if total + lw > max_words and result:
            break
        result.append(line)
        total += lw

    # Strip trailing blank lines added during accumulation
    while result and not result[-1].strip():
        result.pop()

    truncated = "\n".join(result)

    # Fallback for bodies that are a single long line: truncate at last sentence boundary
    if count_words(truncated) > max_words:
        words = truncated.split()
        candidate = " ".join(words[:max_words])
        for punct in (". ", "! ", "? "):
            idx = candidate.rfind(punct)
            if idx > 10:
                candidate = candidate[:idx + 1]
                break
        truncated = candidate

    return truncated, True


def _assemble_draft(
    ranked_themes: list[dict],
    quote_records: list[dict],
    action_records: list[dict],
    redacted_reviews: list[dict],
    config: Any,
    low_data_warning: bool,
) -> tuple[str, str, str, int]:
    """
    Build the unpolished note body.
    Returns (draft_text, period_start_str, period_end_str, review_count).
    """
    product = getattr(config, "product", "Wealthsimple Canada")
    note_themes = getattr(config, "note_themes", 3)
    top = ranked_themes[:note_themes]

    # Derive period from review dates
    if redacted_reviews:
        dates = [r["date"] for r in redacted_reviews if r.get("date")]
        if dates:
            period_start = min(dates)
            period_end = max(dates)
        else:
            today = datetime.now(timezone.utc).date()
            period_start = period_end = today
    else:
        today = datetime.now(timezone.utc).date()
        period_start = period_end = today

    start_str = str(period_start)[:10]
    end_str = str(period_end)[:10]
    review_count = len(redacted_reviews)

    # Build quote lookup
    quote_by_theme: dict[str, str] = {qr["theme"]: qr.get("quote", "") for qr in quote_records}

    lines: list[str] = []

    if low_data_warning:
        lines.append(
            "> ⚠️  Low data warning: fewer than the minimum number of reviews survived "
            "filtering. Results may not be representative.\n"
        )

    lines.append(f"# {product} — Weekly Review Pulse")
    lines.append(f"**Period:** {start_str} to {end_str} | **Reviews analysed:** {review_count}")
    lines.append("")
    lines.append("## Top Themes")
    for i, ts in enumerate(top, 1):
        theme = ts["theme"]
        count = ts.get("review_count", 0)
        avg = ts.get("avg_rating", 0.0)
        lines.append(f"{i}. **{theme}** — {count} reviews, avg {avg:.1f} stars")

    lines.append("")
    lines.append("## Real User Quotes")
    for ts in top:
        quote = quote_by_theme.get(ts["theme"], "")
        if quote:
            lines.append(f'- "{quote}"')

    lines.append("")
    lines.append("## Action Ideas")
    for i, ar in enumerate(action_records, 1):
        lines.append(f"{i}. {ar['action']}")

    return "\n".join(lines), start_str, end_str, review_count


def generate_pulse_note(
    ranked_themes: list[dict],
    quote_records: list[dict],
    action_records: list[dict],
    redacted_reviews: list[dict],
    config: Any,
    run_id: str = "dry-run",
    low_data_warning: bool = False,
) -> dict:
    """
    Assemble and polish the weekly pulse note.

    Raises MissingUpstreamFieldError (EC-33) if critical upstream data is absent.
    Returns a PulseNote dict; writing to disk is the caller's responsibility (EC-44).
    """
    # EC-33: verify required upstream data exists
    if not action_records:
        raise MissingUpstreamFieldError(
            "action_records is empty — action generation must have failed upstream."
        )
    if not ranked_themes:
        raise MissingUpstreamFieldError(
            "ranked_themes is empty — theme classification must have failed upstream."
        )

    product = getattr(config, "product", "Wealthsimple Canada")
    max_words = getattr(config, "max_note_words", 250)
    note_themes = getattr(config, "note_themes", 3)

    # Step 1: assemble unpolished draft
    draft, period_start, period_end, review_count = _assemble_draft(
        ranked_themes, quote_records, action_records, redacted_reviews, config, low_data_warning
    )

    # Step 2: LLM polish pass (text mode — not JSON)
    try:
        system_prompt = _load_prompt("generate_note.txt")
        polished_body = call_llm_text(draft, system_prompt, config)
        log(run_id, "pulse_note", "note_polished", word_count=count_words(polished_body))
    except Exception as exc:
        log(run_id, "pulse_note", "polish_failed_using_draft", error=str(exc))
        polished_body = draft

    # Step 3: word-count enforcement (EC-31)
    truncated_body, was_truncated = _truncate_at_word_limit(polished_body, max_words)
    if was_truncated:
        log(
            run_id,
            "pulse_note",
            "note_truncated",
            original_words=count_words(polished_body),
            max_words=max_words,
        )

    # Step 4: escape Markdown control chars inside quoted strings (EC-32)
    truncated_body = _escape_markdown_in_quotes(truncated_body)

    # Step 5: append footer (excluded from word count)
    generated_at = datetime.now(timezone.utc)
    word_count = count_words(truncated_body)
    footer = (
        f"\n\n---\n"
        f"*Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')} | Word count: {word_count}*"
    )
    note_text = truncated_body + footer

    log(
        run_id,
        "pulse_note",
        "note_complete",
        word_count=word_count,
        note_truncated=was_truncated,
        low_data_warning=low_data_warning,
    )

    return {
        "product_name": product,
        "period_start": period_start,
        "period_end": period_end,
        "review_count": review_count,
        "themes": [ts["theme"] for ts in ranked_themes[:note_themes]],
        "quotes": [qr["quote"] for qr in quote_records],
        "actions": [ar["action"] for ar in action_records],
        "note_text": note_text,
        "word_count": word_count,
        "generated_at": generated_at.isoformat(),
        "note_truncated": was_truncated,
        "low_data_warning": low_data_warning,
    }
