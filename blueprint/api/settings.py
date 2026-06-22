"""Settings API for Blueprint configuration.

Includes API preset management for saving and switching between LLM configs.
API key is stored in a separate file with restricted permissions (0o600).
"""

import json
import os
import stat
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["settings"])

# File paths
SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"
PRESETS_FILE = Path(__file__).parent.parent / "data" / "api_presets.json"
API_KEY_FILE = Path(__file__).parent.parent / "data" / ".api_key"


class SettingsUpdate(BaseModel):
    """Settings update request."""
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    max_iterations: int | None = None
    agent_mode: str | None = None  # "max" | "mini"
    show_discussion: bool | None = None


class PresetSave(BaseModel):
    """Save current API config as a preset."""
    name: str


_DEFAULTS = {
    "api_key": "",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "max_iterations": 3,
    "agent_mode": "mini",
    "show_discussion": False,
}


def _load_api_key() -> str:
    """Load API key from secure file."""
    if API_KEY_FILE.exists():
        try:
            return API_KEY_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


def _save_api_key(key: str) -> None:
    """Save API key to secure file with restricted permissions."""
    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    API_KEY_FILE.write_text(key, encoding="utf-8")
    # Restrict file permissions (owner read/write only)
    try:
        os.chmod(str(API_KEY_FILE), stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass  # Windows doesn't support chmod


def _load_settings() -> dict:
    """Load settings from file, merged with defaults."""
    settings = _DEFAULTS.copy()
    if SETTINGS_FILE.exists():
        try:
            file_settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings.update(file_settings)
        except (json.JSONDecodeError, IOError):
            pass
    # Load API key from secure file (not from settings.json)
    settings["api_key"] = _load_api_key()
    return settings


def _save_settings(settings: dict) -> None:
    """Save settings to file with atomic write (excludes api_key)."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Don't save api_key to settings.json — it's in a separate secure file
    to_save = {k: v for k, v in settings.items() if k != "api_key"}
    tmp_path = SETTINGS_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_path), str(SETTINGS_FILE))


def _load_presets() -> dict:
    """Load API presets from file."""
    if PRESETS_FILE.exists():
        try:
            return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_presets(presets: dict) -> None:
    """Save API presets to file."""
    PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = PRESETS_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_path), str(PRESETS_FILE))


# ── Settings Endpoints ──────────────────────────────────────────────────

@router.get("/settings")
def get_settings():
    """Get current settings (API key masked)."""
    settings = _load_settings()
    if settings.get("api_key"):
        key = settings["api_key"]
        if len(key) > 8:
            settings["api_key"] = key[:4] + "***" + key[-4:]
    return settings


@router.put("/settings")
def update_settings(req: SettingsUpdate):
    """Update settings."""
    current = _load_settings()

    if req.api_key is not None:
        _save_api_key(req.api_key)  # Save to secure file
    if req.base_url is not None:
        current["base_url"] = req.base_url
    if req.model is not None:
        current["model"] = req.model
    if req.max_iterations is not None:
        current["max_iterations"] = req.max_iterations
    if req.agent_mode is not None:
        if req.agent_mode not in ("max", "mini"):
            raise HTTPException(status_code=400, detail="agent_mode must be 'max' or 'mini'")
        current["agent_mode"] = req.agent_mode
        if req.agent_mode == "mini":
            current["show_discussion"] = False
    if req.show_discussion is not None:
        if current.get("agent_mode") != "max" and req.show_discussion:
            raise HTTPException(status_code=400, detail="show_discussion requires agent_mode='max'")
        current["show_discussion"] = req.show_discussion

    _save_settings(current)
    return current


# ── API Presets Endpoints ───────────────────────────────────────────────

@router.get("/settings/presets")
def list_presets():
    """List all saved API presets."""
    presets = _load_presets()
    # Mask API keys
    result = {}
    for name, preset in presets.items():
        p = preset.copy()
        if p.get("api_key") and len(p["api_key"]) > 8:
            p["api_key"] = p["api_key"][:4] + "***" + p["api_key"][-4:]
        result[name] = p
    return result


@router.post("/settings/presets")
def save_preset(req: PresetSave):
    """Save current API config as a named preset."""
    current = _load_settings()
    preset = {
        "api_key": current.get("api_key", ""),
        "base_url": current.get("base_url", ""),
        "model": current.get("model", ""),
    }
    presets = _load_presets()
    presets[req.name] = preset
    _save_presets(presets)
    return {"message": f"Preset '{req.name}' saved", "preset": preset}


@router.post("/settings/presets/{name}/apply")
def apply_preset(name: str):
    """Apply a saved API preset."""
    presets = _load_presets()
    if name not in presets:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")

    preset = presets[name]
    current = _load_settings()
    current["api_key"] = preset["api_key"]
    current["base_url"] = preset["base_url"]
    current["model"] = preset["model"]
    _save_settings(current)

    return {"message": f"Preset '{name}' applied", "settings": {
        "model": current["model"],
        "base_url": current["base_url"],
    }}


@router.delete("/settings/presets/{name}")
def delete_preset(name: str):
    """Delete a saved API preset."""
    presets = _load_presets()
    if name not in presets:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    del presets[name]
    _save_presets(presets)
    return {"message": f"Preset '{name}' deleted"}


# ── Webhook Endpoints ───────────────────────────────────────────────────

WEBHOOKS_FILE_NAME = "webhooks.json"


def _get_webhooks_path() -> Path:
    from blueprint.config import settings
    base = Path(settings.project_dir if settings.project_dir else "projects").parent
    return base / "data" / WEBHOOKS_FILE_NAME


def _load_webhooks() -> dict:
    path = _get_webhooks_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"webhooks": []}


def _save_webhooks(data: dict) -> None:
    path = _get_webhooks_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = ["*"]
    secret: str | None = None


@router.get("/settings/webhooks")
def list_webhooks():
    """List all webhooks (secret masked)."""
    data = _load_webhooks()
    result = []
    for w in data.get("webhooks", []):
        item = w.copy()
        if item.get("secret"):
            item["secret"] = "***"
        result.append(item)
    return {"webhooks": result}


@router.post("/settings/webhooks")
def add_webhook(req: WebhookCreate):
    """Add a webhook."""
    data = _load_webhooks()
    webhook = {
        "url": req.url,
        "events": req.events,
        "secret": req.secret,
    }
    data.setdefault("webhooks", []).append(webhook)
    _save_webhooks(data)
    # Return with masked secret
    result = webhook.copy()
    if result.get("secret"):
        result["secret"] = "***"
    return result


@router.delete("/settings/webhooks/{index}")
def delete_webhook(index: int):
    """Delete a webhook by index."""
    data = _load_webhooks()
    webhooks = data.get("webhooks", [])
    if index < 0 or index >= len(webhooks):
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhooks.pop(index)
    _save_webhooks(data)
    return {"message": "Webhook deleted"}
