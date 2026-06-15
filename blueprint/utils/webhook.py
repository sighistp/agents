"""Webhook notification — send events to external services."""
import hashlib
import hmac
import json
import time
from typing import Any

import httpx


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
                except Exception:
                    pass  # Best-effort delivery

    def add_webhook(self, url: str, events: list[str] = None, secret: str = None) -> dict:
        """Add a webhook subscription."""
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
