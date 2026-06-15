"""Tests for webhook settings API endpoints."""
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from blueprint.main import app


def test_get_webhooks_empty(tmp_path):
    """GET /api/settings/webhooks should return empty list."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    # Clean any existing webhooks file
    wp = tmp_path.parent / "data" / "webhooks.json"
    if wp.exists():
        wp.unlink()
    try:
        client = TestClient(app)
        resp = client.get("/api/settings/webhooks")
        assert resp.status_code == 200
        assert resp.json()["webhooks"] == []
    finally:
        settings.project_dir = old_val


def test_add_webhook(tmp_path):
    """POST /api/settings/webhooks should add a webhook."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    wp = tmp_path.parent / "data" / "webhooks.json"
    if wp.exists():
        wp.unlink()
    try:
        client = TestClient(app)
        resp = client.post("/api/settings/webhooks", json={
            "url": "http://example.com/hook",
            "events": ["project.completed"],
            "secret": "my-secret"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "http://example.com/hook"
        assert data["secret"] == "***"

        resp2 = client.get("/api/settings/webhooks")
        assert len(resp2.json()["webhooks"]) == 1
    finally:
        settings.project_dir = old_val


def test_delete_webhook(tmp_path):
    """DELETE /api/settings/webhooks/{index} should remove a webhook."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    wp = tmp_path.parent / "data" / "webhooks.json"
    if wp.exists():
        wp.unlink()
    try:
        client = TestClient(app)
        client.post("/api/settings/webhooks", json={
            "url": "http://example.com/hook",
            "events": ["*"],
        })
        resp = client.delete("/api/settings/webhooks/0")
        assert resp.status_code == 200
        resp2 = client.get("/api/settings/webhooks")
        assert len(resp2.json()["webhooks"]) == 0
    finally:
        settings.project_dir = old_val


def test_webhook_persistence(tmp_path):
    """Webhooks should persist within same project_dir."""
    from blueprint.config import settings
    old_val = settings.project_dir
    settings.project_dir = str(tmp_path)
    wp = tmp_path.parent / "data" / "webhooks.json"
    if wp.exists():
        wp.unlink()
    try:
        client = TestClient(app)
        client.post("/api/settings/webhooks", json={
            "url": "http://a.com",
            "events": ["*"],
        })
        client.post("/api/settings/webhooks", json={
            "url": "http://b.com",
            "events": ["failed"],
        })
        resp = client.get("/api/settings/webhooks")
        data = resp.json()
        assert len(data["webhooks"]) == 2
        assert data["webhooks"][0]["url"] == "http://a.com"
        assert data["webhooks"][1]["url"] == "http://b.com"
    finally:
        settings.project_dir = old_val
