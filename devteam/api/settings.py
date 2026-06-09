"""Settings API for DevTeam configuration.

Includes API preset management for saving and switching between LLM configs.
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["settings"])

# File paths
SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"
PRESETS_FILE = Path(__file__).parent.parent / "data" / "api_presets.json"


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


def _load_settings() -> dict:
    """Load settings from file, merged with defaults."""
    settings = _DEFAULTS.copy()
    if SETTINGS_FILE.exists():
        try:
            file_settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings.update(file_settings)
        except (json.JSONDecodeError, IOError):
            pass
    return settings


def _save_settings(settings: dict) -> None:
    """Save settings to file with atomic write."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
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
        current["api_key"] = req.api_key
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
