"""Tests for webhook notification module."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from blueprint.utils.webhook import WebhookManager


# --- P0.4: SSRF protection tests ---

class TestWebhookURLValidation:
    """P0.4: Webhook URL must reject internal/private IPs."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1:8080/evil",
        "http://localhost/evil",
        "http://[::1]/evil",
        "http://10.0.0.1/evil",
        "http://10.255.255.255/evil",
        "http://172.16.0.1/evil",
        "http://172.31.255.255/evil",
        "http://192.168.0.1/evil",
        "http://192.168.255.255/evil",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/evil",
    ])
    def test_rejects_private_urls(self, url):
        """Should reject URLs targeting private/internal IPs."""
        from blueprint.utils.webhook import WebhookManager
        wm = WebhookManager()
        with pytest.raises(ValueError, match="private|internal|blocked|not allowed|forbidden|localhost"):
            wm.add_webhook(url)

    def test_allows_public_url(self):
        """Should allow public URLs."""
        from blueprint.utils.webhook import WebhookManager
        wm = WebhookManager()
        result = wm.add_webhook("https://hooks.example.com/webhook")
        assert result["url"] == "https://hooks.example.com/webhook"

    def test_allows_http_public(self):
        """Should allow HTTP public URLs."""
        from blueprint.utils.webhook import WebhookManager
        wm = WebhookManager()
        result = wm.add_webhook("http://example.com:8080/hook")
        assert "example.com" in result["url"]


@pytest.mark.asyncio
async def test_webhook_manager_notify():
    """Should send webhook notification."""
    wm = WebhookManager()
    wm.webhooks = [{"url": "http://example.com/hook", "events": ["*"], "secret": None}]

    with patch("blueprint.utils.webhook.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

        await wm.notify("test.event", {"key": "value"})

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://example.com/hook"


@pytest.mark.asyncio
async def test_webhook_filters_events():
    """Should only send to webhooks subscribed to the event."""
    wm = WebhookManager()
    wm.webhooks = [
        {"url": "http://a.com", "events": ["completed"], "secret": None},
        {"url": "http://b.com", "events": ["failed"], "secret": None},
    ]

    with patch("blueprint.utils.webhook.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

        await wm.notify("completed", {})

        # Only http://a.com should be called
        assert mock_client.post.call_count == 1
        assert mock_client.post.call_args[0][0] == "http://a.com"


@pytest.mark.asyncio
async def test_webhook_signature():
    """Should include HMAC-SHA256 signature when secret is set."""
    wm = WebhookManager()
    wm.webhooks = [{"url": "http://example.com", "events": ["*"], "secret": "my-secret"}]

    with patch("blueprint.utils.webhook.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

        await wm.notify("test", {"data": 123})

        call_kwargs = mock_client.post.call_args[1]
        assert "X-Webhook-Signature" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-Webhook-Signature"].startswith("sha256=")


@pytest.mark.asyncio
async def test_webhook_empty_list():
    """Should not fail with empty webhook list."""
    wm = WebhookManager()
    wm.webhooks = []

    with patch("blueprint.utils.webhook.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

        await wm.notify("test", {})
        mock_client.post.assert_not_called()
