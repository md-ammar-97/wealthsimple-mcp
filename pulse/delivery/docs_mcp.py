"""Delivery step — append weekly pulse note to a Google Doc via google-mcp-server."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from pulse.utils.logging import log


def append_doc_section(
    note_text: str,
    run_data: dict[str, Any],
    config: Any,
    run_id: str = "dry-run",
    force: bool = False,
) -> None:
    """
    Append the pulse note to a Google Doc via the running google-mcp-server.

    Silently skips when:
    - docs_mcp.enabled is false in config
    - doc_id is not configured
    - Operator rejects the action in the server terminal (403 returned)

    Raises RuntimeError if the server is not reachable (misconfiguration — operator
    must start google-mcp-server before enabling this delivery mode).
    """
    docs_cfg: dict = getattr(config, "docs_mcp", {}) or {}
    if not docs_cfg.get("enabled", False):
        return

    doc_id: str = docs_cfg.get("doc_id", "").strip()
    if not doc_id:
        log(run_id, "delivery", "docs_mcp_skip", reason="doc_id not set in config/delivery.yaml")
        return

    period_key: str = run_data.get("period_key", "unknown-period")

    # Idempotency — skip if already delivered this period (unless --force)
    if not force and run_data.get("delivery", {}).get("doc_url"):
        log(run_id, "delivery", "docs_mcp_skip", reason="already delivered", period_key=period_key)
        return

    content = f"## {period_key}\n\n{note_text}"
    server_url: str = getattr(config, "mcp_server_url", "http://localhost:8000").rstrip("/")
    payload = json.dumps({"doc_id": doc_id, "content": content}).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = os.getenv("MCP_API_KEY", "").strip()
    if api_key:
        headers["X-Api-Key"] = api_key

    log(run_id, "delivery", "docs_mcp_start", doc_id=doc_id, period_key=period_key)
    req = urllib.request.Request(
        f"{server_url}/append_to_doc",
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        # Long timeout — server blocks while operator approves in the terminal
        with urllib.request.urlopen(req, timeout=300) as resp:
            result: dict = json.loads(resp.read())

        run_data.setdefault("delivery", {})["doc_url"] = (
            f"https://docs.google.com/document/d/{doc_id}"
        )
        log(run_id, "delivery", "docs_mcp_done",
            doc_id=doc_id, chars_added=result.get("chars_added"))

    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            log(run_id, "delivery", "docs_mcp_rejected",
                reason="operator declined in server terminal")
        else:
            body = exc.read().decode(errors="replace")
            log(run_id, "delivery", "docs_mcp_error", status=exc.code, detail=body)
            raise

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"google-mcp-server not reachable at {server_url}.\n"
            "Start it first:  cd google-mcp-server && python -m uvicorn server:app --port 8000"
        ) from exc
