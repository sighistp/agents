"""JWT authentication and password hashing for Blueprint.

Adapted from RAGv3 auth system.
"""

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Security
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# JWT Configuration (lazy initialization, persisted to file)
# ---------------------------------------------------------------------------
_JWT_SECRET: str | None = None
_JWT_ALGORITHM: str = "HS256"
_SECRET_FILE = Path(__file__).parent.parent / ".blueprint_secret"


def _get_jwt_secret() -> str:
    """Get JWT secret, initializing if needed. Persists to file across restarts."""
    global _JWT_SECRET
    if _JWT_SECRET is None:
        _JWT_SECRET = os.environ.get("BLUEPRINT_JWT_SECRET", "")
        if not _JWT_SECRET:
            # Try to load persisted secret
            if _SECRET_FILE.exists():
                _JWT_SECRET = _SECRET_FILE.read_text().strip()
            if not _JWT_SECRET:
                # Generate new secret and persist it
                _JWT_SECRET = secrets.token_hex(32)
                _SECRET_FILE.write_text(_JWT_SECRET)
                try:
                    import stat as _stat
                    os.chmod(str(_SECRET_FILE), _stat.S_IRUSR | _stat.S_IWUSR)
                except OSError:
                    pass  # Windows doesn't support full chmod
                try:
                    import stat as _stat
                    os.chmod(str(_SECRET_FILE), _stat.S_IRUSR | _stat.S_IWUSR)
                except OSError:
                    pass  # Windows
                try:
                    import stat as _stat
                    os.chmod(str(_SECRET_FILE), _stat.S_IRUSR | _stat.S_IWUSR)
                except OSError:
                    pass  # Windows doesn't support full chmod
                try:
                    import stat as _stat
                    os.chmod(str(_SECRET_FILE), _stat.S_IRUSR | _stat.S_IWUSR)
                except OSError:
                    pass  # Windows
    return _JWT_SECRET


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256 with random salt)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash *password* with a random 16-byte salt.

    Returns ``salt_hex$hash_hex``.
    """
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations=260_000)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Return True if *password* matches the ``salt$hash`` in *stored*."""
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations=260_000)
    return hmac.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_token(payload: dict, expires_seconds: int = 86400) -> str:
    """Create a JWT token with *payload* and a default 24-hour expiry."""
    to_encode = payload.copy()
    to_encode["exp"] = datetime.now(UTC).timestamp() + expires_seconds
    to_encode.setdefault("iat", datetime.now(UTC).timestamp())
    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode a JWT token. Returns the payload dict, or None if invalid/expired."""
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Validate API key and return user_id. Returns 'anonymous' when auth is disabled."""
    from blueprint.config import settings

    if not settings.auth_enabled:
        return "anonymous"
    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API Key (X-API-Key header)")
    try:
        keys = __import__("json").loads(settings.auth_keys)
    except Exception:
        raise HTTPException(status_code=500, detail="Auth config error")
    for user_id, key in keys.items():
        if hmac.compare_digest(api_key, key):
            return user_id
    raise HTTPException(status_code=403, detail="Invalid API Key")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    username: str


class UserResponse(BaseModel):
    id: int
    username: str


# ---------------------------------------------------------------------------
# Auth router endpoints
# ---------------------------------------------------------------------------

def _get_user_db():
    """Get or create the global UserDB instance."""
    from blueprint.api.user_db import get_user_db
    return get_user_db()


@router.post("/register", response_model=UserResponse)
def register(req: RegisterRequest):
    """Register a new user."""
    db = _get_user_db()
    try:
        uid = db.register_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return UserResponse(id=uid, username=req.username)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """Authenticate and return a JWT token."""
    db = _get_user_db()
    user = db.login_user(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token({"sub": str(user["id"]), "username": user["username"]})
    return TokenResponse(token=token, username=user["username"])
