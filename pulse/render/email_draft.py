from __future__ import annotations

import re
from typing import Any

from pulse.utils.logging import log


def _strip_markdown(text: str) -> str:
    """
    Convert Markdown syntax to plain text (EC-35).
    Handles: ## headers, **bold**, *italic*, - lists, --- dividers, `code`.
    """
    result = []
    for line in text.splitlines():
        # ## Header → Header (any number of leading #)
        line = re.sub(r"^#{1,6}\s+", "", line)
        # **text** → text
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        # *text* → text (single asterisk italic)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        # `code` → code
        line = re.sub(r"`(.+?)`", r"\1", line)
        # - item → • item (only at line start, after optional whitespace)
        line = re.sub(r"^(\s*)- ", r"\1• ", line)
        # --- (horizontal rule) → blank line
        if re.match(r"^-{3,}$", line.strip()):
            line = ""
        result.append(line)
    return "\n".join(result)


def render_email_draft(note_text: str, config: Any, run_id: str = "dry-run") -> str:
    """
    Render a plain-text email draft from the Markdown weekly note (EC-34, EC-35).

    Strips all Markdown formatting; fills the email template from config.
    If email_recipient is missing, uses a placeholder and logs a warning (EC-34).
    """
    product_name = getattr(config, "product", "Wealthsimple Canada")
    email_recipient = getattr(config, "email_recipient", None) or ""
    sender_name = getattr(config, "sender_name", "Pulse Pipeline")

    if not email_recipient:
        log(
            run_id,
            "email_draft",
            "missing_recipient_placeholder",
            warning="email_recipient not configured; using placeholder",
        )
        email_recipient = "team@example.com"

    plain_body = _strip_markdown(note_text)

    email_text = (
        f"To: {email_recipient}\n"
        f"Subject: Weekly Review Pulse — {product_name}\n"
        "\n"
        "Hi Team,\n"
        "\n"
        f"Here is this week’s review pulse for {product_name}.\n"
        "\n"
        "---\n"
        "\n"
        f"{plain_body}\n"
        "\n"
        "---\n"
        "\n"
        "Thanks,\n"
        f"{sender_name}\n"
    )

    log(run_id, "email_draft", "email_draft_rendered", recipient=email_recipient)
    return email_text
