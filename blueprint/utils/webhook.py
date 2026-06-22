"""Webhook notification — send events to external services."""
import hashlib
import hmac
import ipaddress
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

import httpx

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/32"),
    ipaddress.ip_network("::1/128"),
]


def _validate_webhook_url(url: str) -> None:
    """Reject URLs targeting private/internal IPs to prevent SSRF."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme must be http or https, got: {parsed.scheme}")
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "[::1]"):
        raise ValueError(f"Webhook URL targets localhost: {url}")
    try:
        ip = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(f"Webhook URL targets private network {network}: {url}")
    except ValueError as e:
        if "private network" in str(e) or "targets" in str(e):
            raise
        # hostname is a domain name, not an IP — allow it
        pass


class WebhookManager:
    def __init__(self):
        self.webhooks: list[dict] = []

    async def notify(self, event: str, payload: dict[str, Any]):
        """Send webhook notification to all subscribed endpoints."""
        body = {
            "event": event,
            "timestamp": time.time(),
            "data": payload,
        }
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

        async with httpx.AsyncClient(timeout=10) as client:
            for webhook in self.webhooks:
                events = webhook.get("events", ["*"])
                if "*" not in events and event not in events:
                    continue

                headers = {"Content-Type": "application/json"}

                secret = webhook.get("secret")
                if secret:
                    sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
                    headers["X-Webhook-Signature"] = f"sha256={sig}"

                try:
                    await client.post(webhook["url"], content=body_bytes, headers=headers)
                except Exception as e:
                    logger.warning("Webhook delivery failed for %s: %s", webhook.get("url"), e, exc_info=True)

    def add_webhook(self, url: str, events: list[str] = None, secret: str = None) -> dict:
        """Add a webhook subscription."""
        _validate_webhook_url(url)
        webhook = {
            "url": url,
            "events": events or ["*"],
            "secret": secret,
            "created_at": time.time(),
        }
        self.webhooks.append(webhook)
        return webhook

    def remove_webhook(self, url: str) -> bool:
        """Remove a webhook subscription."""
        before = len(self.webhooks)
        self.webhooks = [w for w in self.webhooks if w["url"] != url]
        return len(self.webhooks) < before

    def list_webhooks(self) -> list[dict]:
        """List all webhooks (secret masked)."""
        return [
            {**w, "secret": "***" if w.get("secret") else None}
            for w in self.webhooks
        ]
