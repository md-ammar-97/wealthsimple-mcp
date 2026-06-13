"""Tests for pulse.delivery.docs_mcp and pulse.delivery.gmail_mcp."""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pulse.delivery.docs_mcp import append_doc_section
from pulse.delivery.gmail_mcp import create_gmail_draft


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _run_data(period_key: str = "wealthsimple-2026-W23") -> dict:
    return {
        "period_key": period_key,
        "delivery_key": f"{period_key}-email",
        "product": "Wealthsimple Canada",
        "delivery": {"mode": "local"},
        "errors": [],
    }


def _config(docs_enabled: bool = True, gmail_enabled: bool = True,
            doc_id: str = "abc123", email_recipient: str = "test@example.com") -> SimpleNamespace:
    return SimpleNamespace(
        docs_mcp={"enabled": docs_enabled, "doc_id": doc_id},
        gmail_mcp={"enabled": gmail_enabled, "email_mode": "draft"},
        mcp_server_url="http://localhost:8000",
        email_recipient=email_recipient,
    )


def _mock_urlopen(status: int = 200, body: dict | None = None):
    """Return a context-manager mock for urllib.request.urlopen."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(body or {"status": "ok"}).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# docs_mcp tests
# ---------------------------------------------------------------------------

class TestAppendDocSection:
    def test_skips_when_disabled(self):
        run_data = _run_data()
        cfg = _config(docs_enabled=False)
        with patch("urllib.request.urlopen") as mock_open:
            append_doc_section("note", run_data, cfg, run_id="test")
        mock_open.assert_not_called()

    def test_skips_when_doc_id_empty(self):
        run_data = _run_data()
        cfg = _config(doc_id="")
        with patch("urllib.request.urlopen") as mock_open:
            append_doc_section("note", run_data, cfg, run_id="test")
        mock_open.assert_not_called()

    def test_skips_when_already_delivered(self):
        run_data = _run_data()
        run_data["delivery"]["doc_url"] = "https://docs.google.com/document/d/abc123"
        cfg = _config()
        with patch("urllib.request.urlopen") as mock_open:
            append_doc_section("note", run_data, cfg, run_id="test")
        mock_open.assert_not_called()

    def test_force_overrides_idempotency(self):
        run_data = _run_data()
        run_data["delivery"]["doc_url"] = "https://docs.google.com/document/d/abc123"
        cfg = _config()
        mock_resp = _mock_urlopen(body={"status": "ok", "chars_added": 50})
        with patch("urllib.request.urlopen", return_value=mock_resp):
            append_doc_section("note", run_data, cfg, run_id="test", force=True)
        # Should have been called because force=True
        assert "doc_url" in run_data["delivery"]

    def test_successful_delivery_updates_run_data(self):
        run_data = _run_data()
        cfg = _config()
        mock_resp = _mock_urlopen(body={"status": "ok", "chars_added": 120})
        with patch("urllib.request.urlopen", return_value=mock_resp):
            append_doc_section("My note text", run_data, cfg, run_id="test")
        assert run_data["delivery"]["doc_url"] == "https://docs.google.com/document/d/abc123"

    def test_payload_includes_period_heading(self):
        run_data = _run_data(period_key="wealthsimple-2026-W23")
        cfg = _config()
        mock_resp = _mock_urlopen(body={"status": "ok", "chars_added": 50})
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode())
            return mock_resp
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            append_doc_section("Body text", run_data, cfg, run_id="test")
        assert captured["body"]["doc_id"] == "abc123"
        assert "wealthsimple-2026-W23" in captured["body"]["content"]
        assert "Body text" in captured["body"]["content"]

    def test_403_does_not_raise(self):
        run_data = _run_data()
        cfg = _config()
        exc = urllib.error.HTTPError("url", 403, "Forbidden", {}, BytesIO(b'{"detail":"rejected"}'))
        with patch("urllib.request.urlopen", side_effect=exc):
            append_doc_section("note", run_data, cfg, run_id="test")  # must not raise
        assert "doc_url" not in run_data["delivery"]

    def test_server_unreachable_raises_runtime_error(self):
        run_data = _run_data()
        cfg = _config()
        exc = urllib.error.URLError("Connection refused")
        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError, match="google-mcp-server not reachable"):
                append_doc_section("note", run_data, cfg, run_id="test")


# ---------------------------------------------------------------------------
# gmail_mcp tests
# ---------------------------------------------------------------------------

class TestCreateGmailDraft:
    def test_skips_when_disabled(self):
        run_data = _run_data()
        cfg = _config(gmail_enabled=False)
        with patch("urllib.request.urlopen") as mock_open:
            create_gmail_draft("email body", run_data, cfg, run_id="test")
        mock_open.assert_not_called()

    def test_skips_when_no_recipient(self):
        run_data = _run_data()
        cfg = _config(email_recipient="")
        with patch("urllib.request.urlopen") as mock_open:
            create_gmail_draft("email body", run_data, cfg, run_id="test")
        mock_open.assert_not_called()

    def test_skips_when_already_delivered(self):
        run_data = _run_data()
        cfg = _config()
        with patch("pulse.delivery.gmail_mcp.check_delivery_guard", return_value=True):
            with patch("urllib.request.urlopen") as mock_open:
                create_gmail_draft("email body", run_data, cfg, run_id="test")
        mock_open.assert_not_called()

    def test_force_overrides_idempotency(self):
        run_data = _run_data()
        cfg = _config()
        mock_resp = _mock_urlopen(body={"status": "ok", "draft_id": "draft_xyz"})
        with patch("pulse.delivery.gmail_mcp.check_delivery_guard", return_value=True):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                create_gmail_draft("email body", run_data, cfg, run_id="test", force=True)
        assert run_data["delivery"]["draft_id"] == "draft_xyz"

    def test_successful_delivery_updates_run_data(self):
        run_data = _run_data()
        cfg = _config()
        mock_resp = _mock_urlopen(body={"status": "ok", "draft_id": "draft_abc"})
        with patch("pulse.delivery.gmail_mcp.check_delivery_guard", return_value=False):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                create_gmail_draft("email body", run_data, cfg, run_id="test")
        assert run_data["delivery"]["draft_id"] == "draft_abc"

    def test_payload_includes_correct_fields(self):
        run_data = _run_data(period_key="wealthsimple-2026-W23")
        cfg = _config()
        mock_resp = _mock_urlopen(body={"status": "ok", "draft_id": "d1"})
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode())
            return mock_resp
        with patch("pulse.delivery.gmail_mcp.check_delivery_guard", return_value=False):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                create_gmail_draft("Dear team...", run_data, cfg, run_id="test")
        assert captured["body"]["to"] == "test@example.com"
        assert "wealthsimple-2026-W23" in captured["body"]["subject"]
        assert captured["body"]["body"] == "Dear team..."

    def test_403_does_not_raise(self):
        run_data = _run_data()
        cfg = _config()
        exc = urllib.error.HTTPError("url", 403, "Forbidden", {}, BytesIO(b'{"detail":"rejected"}'))
        with patch("pulse.delivery.gmail_mcp.check_delivery_guard", return_value=False):
            with patch("urllib.request.urlopen", side_effect=exc):
                create_gmail_draft("email", run_data, cfg, run_id="test")  # must not raise
        assert "draft_id" not in run_data["delivery"]

    def test_server_unreachable_raises_runtime_error(self):
        run_data = _run_data()
        cfg = _config()
        exc = urllib.error.URLError("Connection refused")
        with patch("pulse.delivery.gmail_mcp.check_delivery_guard", return_value=False):
            with patch("urllib.request.urlopen", side_effect=exc):
                with pytest.raises(RuntimeError, match="google-mcp-server not reachable"):
                    create_gmail_draft("email", run_data, cfg, run_id="test")
