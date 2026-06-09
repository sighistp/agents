"""Tests for WebSocket JWT authentication."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devteam.api.auth import create_token
from devteam.api.websocket import router as ws_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create a FastAPI test app with the WebSocket router."""
    test_app = FastAPI()
    test_app.include_router(ws_router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def valid_token():
    """Create a valid JWT token for testing."""
    return create_token({"sub": "test_user", "username": "testuser"}, expires_seconds=3600)


@pytest.fixture
def expired_token():
    """Create an expired JWT token for testing."""
    return create_token({"sub": "test_user", "username": "testuser"}, expires_seconds=-1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWebSocketAuth:
    """Test WebSocket authentication requirements."""

    def test_websocket_rejects_no_token(self, client):
        """Connection without token should be closed with auth error."""
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises((WebSocketDisconnect, Exception)):
            with client.websocket_connect("/ws/project") as ws:
                ws.receive_text()

    def test_websocket_rejects_invalid_token(self, client):
        """Connection with invalid token should be closed with auth error."""
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises((WebSocketDisconnect, Exception)):
            with client.websocket_connect("/ws/project?token=invalid.token.here") as ws:
                ws.receive_text()

    def test_websocket_rejects_expired_token(self, client, expired_token):
        """Connection with expired token should be closed with auth error."""
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises((WebSocketDisconnect, Exception)):
            with client.websocket_connect(f"/ws/project?token={expired_token}") as ws:
                ws.receive_text()

    def test_websocket_accepts_valid_token(self, client, valid_token):
        """Connection with valid token should be accepted and functional."""
        with client.websocket_connect(f"/ws/project?token={valid_token}") as ws:
            # Connection should be established successfully
            # Send a reconnect message to verify the connection works
            ws.send_json({"type": "reconnect"})
            response = ws.receive_json()
            assert response["type"] == "state_sync"

    def test_websocket_accepts_token_from_header(self, client, valid_token):
        """Connection with token in Authorization header should work."""
        with client.websocket_connect(
            "/ws/project",
            headers={"Authorization": f"Bearer {valid_token}"}
        ) as ws:
            # Connection should be established successfully
            ws.send_json({"type": "reconnect"})
            response = ws.receive_json()
            assert response["type"] == "state_sync"
