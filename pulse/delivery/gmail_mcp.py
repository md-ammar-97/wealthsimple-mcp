"""Delivery step — create a Gmail draft via google-mcp-server."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from pulse.ledger.run_ledger import check_delivery_guard
from pulse.utils.logging import log

_DEFAULT_SUBJECT = "Weekly Review Pulse — Wealthsimple Canada"


def create_gmail_draft(
    email_text: str,
    run_data: dict[str, Any],
    config: Any,
    run_id: str = "dry-run",
    force: bool = False,
) -> None:
    """
    Create a Gmail draft via the running google-mcp-server.

    Silently skips when:
    - gmail_mcp.enabled is false in config
    - email_recipient is not configured
    - Idempotency guard: draft already created for this period (unless --force)
    - Operator rejects the action in the server terminal (403 returned)

    Raises RuntimeError if the server is not reachable.
    """
    gmail_cfg: dict = getattr(config, "gmail_mcp", {}) or {}
    if not gmail_cfg.get("enabled", False):
        return

    to: str = getattr(config, "email_recipient", "").strip()
    if not to:
        log(run_id, "delivery", "gmail_mcp_skip", reason="email_recipient not set in config/delivery.yaml")
        return

    period_key: str = run_data.get("period_key", "unknown-period")
    delivery_key: str = run_data.get("delivery_key", f"{period_key}-email")

    # Idempotency — skip if already sent this period (unless --force)
    if not force and check_delivery_guard(period_key, delivery_key):
        log(run_id, "delivery", "gmail_mcp_skip",
            reason="already delivered", period_key=period_key)
        return

    product: str = run_data.get("product", "Wealthsimple Canada")
    subject = f"Weekly Review Pulse — {product} — {period_key}"

    server_url: str = getattr(config, "mcp_server_url", "http://localhost:8000").rstrip("/")
    payload = json.dumps({"to": to, "subject": subject, "body": email_text}).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = os.getenv("MCP_API_KEY", "").strip()
    if api_key:
        headers["X-Api-Key"] = api_key

    log(run_id, "delivery", "gmail_mcp_start", to=to, period_key=period_key)
    req = urllib.request.Request(
        f"{server_url}/create_email_draft",
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result: dict = json.loads(resp.read())

        draft_id: str = result.get("draft_id", "")
        run_data.setdefault("delivery", {})["draft_id"] = draft_id
        log(run_id, "delivery", "gmail_mcp_done", draft_id=draft_id)

    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            log(run_id, "delivery", "gmail_mcp_rejected",
                reason="operator declined in server terminal")
        else:
            body = exc.read().decode(errors="replace")
            log(run_id, "delivery", "gmail_mcp_error", status=exc.code, detail=body)
            raise

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"google-mcp-server not reachable at {server_url}.\n"
            "Start it first:  cd google-mcp-server && python -m uvicorn server:app --port 8000"
        ) from exc
