"""Deliver an email through google-mcp-server in draft or send mode."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from pulse.ledger.run_ledger import check_delivery_guard
from pulse.utils.logging import log


def deliver_gmail_email(
    email_text: str,
    run_data: dict[str, Any],
    config: Any,
    run_id: str = "dry-run",
    force: bool = False,
) -> None:
    """Create a Gmail draft or send a message via google-mcp-server."""
    gmail_cfg: dict = getattr(config, "gmail_mcp", {}) or {}
    if not gmail_cfg.get("enabled", False):
        return

    email_mode = str(gmail_cfg.get("email_mode", "draft")).strip().lower()
    if email_mode not in {"draft", "send"}:
        raise ValueError(
            f"Unsupported gmail_mcp.email_mode {email_mode!r}; expected 'draft' or 'send'."
        )

    to: str = getattr(config, "email_recipient", "").strip()
    if not to:
        log(
            run_id,
            "delivery",
            "gmail_mcp_skip",
            reason="email_recipient not set in config/delivery.yaml",
        )
        return

    period_key: str = run_data.get("period_key", "unknown-period")
    delivery_key: str = run_data.get(
        "delivery_key",
        f"{period_key}-email-{email_mode}",
    )
    if not force and check_delivery_guard(period_key, delivery_key):
        log(
            run_id,
            "delivery",
            "gmail_mcp_skip",
            reason="already delivered",
            period_key=period_key,
            email_mode=email_mode,
        )
        return

    product: str = run_data.get("product", "Wealthsimple Canada")
    subject = f"Weekly Review Pulse - {product} - {period_key}"

    server_url: str = getattr(
        config,
        "mcp_server_url",
        "http://localhost:8000",
    ).rstrip("/")
    payload = json.dumps({"to": to, "subject": subject, "body": email_text}).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = os.getenv("MCP_API_KEY", "").strip()
    if api_key:
        headers["X-Api-Key"] = api_key

    endpoint = "send_email" if email_mode == "send" else "create_email_draft"
    log(
        run_id,
        "delivery",
        "gmail_mcp_start",
        to=to,
        period_key=period_key,
        email_mode=email_mode,
    )
    req = urllib.request.Request(
        f"{server_url}/{endpoint}",
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result: dict = json.loads(resp.read())

        delivery = run_data.setdefault("delivery", {})
        delivery["email_mode"] = email_mode
        if email_mode == "send":
            message_id = str(result.get("message_id", ""))
            delivery["message_id"] = message_id
            thread_id = str(result.get("thread_id", ""))
            if thread_id:
                delivery["thread_id"] = thread_id
            log(run_id, "delivery", "gmail_mcp_done", message_id=message_id)
        else:
            draft_id = str(result.get("draft_id", ""))
            delivery["draft_id"] = draft_id
            log(run_id, "delivery", "gmail_mcp_done", draft_id=draft_id)

    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            log(
                run_id,
                "delivery",
                "gmail_mcp_rejected",
                reason="operator declined in server terminal",
            )
        else:
            body = exc.read().decode(errors="replace")
            log(
                run_id,
                "delivery",
                "gmail_mcp_error",
                status=exc.code,
                detail=body,
            )
            raise

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"google-mcp-server not reachable at {server_url}.\n"
            "Start it first: cd google-mcp-server && "
            "python -m uvicorn server:app --port 8000"
        ) from exc
