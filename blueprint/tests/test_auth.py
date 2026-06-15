"""Tests for authentication and user database."""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from blueprint.api.auth import (
    create_token,
    decode_token,
    hash_password,
    router as auth_router,
    verify_password,
)
from blueprint.api.user_db import UserDB


# ---------------------------------------------------------------------------
# Password hashing tests
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "s3cur3P@ss!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Each call should produce a different salt, so hashes differ."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2
        # Both should still verify
        assert verify_password("same_password", h1) is True
        assert verify_password("same_password", h2) is True

    def test_malformed_stored_value(self):
        assert verify_password("pw", "not_a_valid_hash") is False
        assert verify_password("pw", "") is False


# ---------------------------------------------------------------------------
# JWT tests
# ---------------------------------------------------------------------------


class TestJWT:
    def test_create_and_decode_token(self):
        payload = {"sub": "user1", "role": "admin"}
        token = create_token(payload, expires_seconds=3600)
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user1"
        assert decoded["role"] == "admin"
        assert "exp" in decoded

    def test_expired_token_returns_none(self):
        payload = {"sub": "user1"}
        token = create_token(payload, expires_seconds=-1)
        assert decode_token(token) is None

    def test_invalid_token_returns_none(self):
        assert decode_token("not.a.jwt") is None
        assert decode_token("") is None


# ---------------------------------------------------------------------------
# UserDB tests
# ---------------------------------------------------------------------------


class TestUserDB:
    @pytest.fixture
    def db(self, tmp_path):
        db_path = str(tmp_path / "test_users.db")
        db = UserDB(db_path)
        yield db
        db.close()

    def test_register_user(self, db):
        uid = db.register_user("alice", "password123")
        assert isinstance(uid, int)
        assert uid > 0

    def test_register_duplicate_raises(self, db):
        db.register_user("bob", "password123")
        with pytest.raises(ValueError, match="already taken"):
            db.register_user("bob", "password456")

    def test_login_success(self, db):
        db.register_user("charlie", "mypassword")
        result = db.login_user("charlie", "mypassword")
        assert result is not None
        assert result["username"] == "charlie"

    def test_login_wrong_password(self, db):
        db.register_user("dave", "correct")
        result = db.login_user("dave", "incorrect")
        assert result is None

    def test_login_nonexistent_user(self, db):
        result = db.login_user("ghost", "password")
        assert result is None

    def test_get_user(self, db):
        uid = db.register_user("eve", "pass")
        user = db.get_user(uid)
        assert user is not None
        assert user["username"] == "eve"
        assert user["id"] == uid

    def test_get_nonexistent_user(self, db):
        assert db.get_user(9999) is None


# ---------------------------------------------------------------------------
# Auth router integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_app(tmp_path):
    """FastAPI app with auth router and a fresh UserDB."""
    os.environ["BLUEPRINT_AUTH_DB"] = str(tmp_path / "auth_test.db")
    app = FastAPI()
    app.include_router(auth_router)
    return app


class TestAuthAPI:
    def test_register_and_login(self, auth_app):
        client = TestClient(auth_app)

        # Register
        resp = client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert "id" in data

        # Login
        resp = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data

    def test_register_duplicate(self, auth_app):
        client = TestClient(auth_app)
        client.post("/api/auth/register", json={
            "username": "dupe",
            "password": "pass1",
        })
        resp = client.post("/api/auth/register", json={
            "username": "dupe",
            "password": "pass2",
        })
        assert resp.status_code == 400

    def test_login_wrong_password(self, auth_app):
        client = TestClient(auth_app)
        client.post("/api/auth/register", json={
            "username": "user2",
            "password": "right",
        })
        resp = client.post("/api/auth/login", json={
            "username": "user2",
            "password": "wrong",
        })
        assert resp.status_code == 401
