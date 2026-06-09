"""Project CRUD and file management API.

Endpoints:
- POST   /api/projects                                - Create a new project
- GET    /api/projects                                - List all projects
- GET    /api/projects/{project_id}                   - Get project details
- GET    /api/projects/{project_id}/files             - Get project files
- GET    /api/projects/{project_id}/files/{file_path} - Preview a file
- GET    /api/projects/{project_id}/download          - Download project as zip
- GET    /api/projects/{project_id}/download/{path}   - Download a single file
- POST   /api/resume                                  - Resume interrupt
- POST   /api/rethink                                 - Trigger rethink
- POST   /api/cancel                                  - Cancel project
"""

import io
import json
import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from devteam.utils.memory import ProjectMemory

router = APIRouter(prefix="/api", tags=["projects"])

# Module-level memory instance (lazy init to avoid import-time DB creation)
import threading
_memory: ProjectMemory | None = None
_memory_lock = threading.Lock()


def _get_memory() -> ProjectMemory:
    global _memory
    if _memory is None:
        with _memory_lock:
            # Double-check locking
            if _memory is None:
                _memory = ProjectMemory()
    return _memory

# ── Pydantic Models ─────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    requirement: str
    project_id: Optional[str] = None


class CancelRequest(BaseModel):
    project_id: str


class ResumeRequest(BaseModel):
    project_id: str
    decision: str = "approved"


class RethinkRequest(BaseModel):
    project_id: str
    feedback: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────


def _projects_dir() -> Path:
    """Return the projects root directory.

    Honours the DEVTEAM_PROJECT_DIR env-var so tests can override it.
    """
    import os

    return Path(os.environ.get(
        "DEVTEAM_PROJECT_DIR",
        str(Path(__file__).resolve().parent.parent / "projects"),
    ))


def _project_dir(project_id: str) -> Path:
    return _projects_dir() / project_id


def _validate_project_id(project_id: str) -> None:
    if not re.match(r"^[a-zA-Z0-9_-]+$", project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id")


def _validate_file_path(file_path: str) -> None:
    """Reject path traversal attempts."""
    # Normalize the path first to catch encoded attacks
    normalized = os.path.normpath(file_path)
    if ".." in normalized.split(os.sep) or os.path.isabs(normalized):
        raise HTTPException(status_code=400, detail="Invalid file path")


def _safe_resolve(base: Path, file_path: str) -> Path:
    """Resolve *file_path* under *base* and ensure it stays within *base*."""
    full_path = (base / file_path).resolve()
    base_resolved = base.resolve()
    # Use Path.is_relative_to() for correct containment check
    if not full_path.is_relative_to(base_resolved):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return full_path


_MEDIA_TYPES = {
    ".py": "text/x-python",
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".xml": "application/xml",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".ts": "text/typescript",
    ".tsx": "text/typescript",
    ".jsx": "text/javascript",
}


def _get_media_type(file_path: str) -> str:
    """Return a MIME type based on the file extension."""
    return _MEDIA_TYPES.get(Path(file_path).suffix.lower(), "text/plain")


def _read_meta(project_id: str) -> dict:
    """Read meta.json for a project, raising 404 if missing."""
    meta_path = _project_dir(project_id) / "meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        # Fallback: try GBK encoding (Windows Chinese)
        return json.loads(meta_path.read_text(encoding="gbk"))
    except json.JSONDecodeError:
        # Fallback: return empty dict if JSON is corrupted
        return {"requirement": "", "status": "unknown"}


def _write_meta(project_id: str, meta: dict) -> None:
    """Write meta.json for a project with atomic write."""
    meta_path = _project_dir(project_id) / "meta.json"
    # Atomic write: write to temp file then replace
    tmp_path = meta_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_path), str(meta_path))  # os.replace is atomic on both Unix and Windows


# ── Project CRUD ─────────────────────────────────────────────────────────


@router.post("/projects")
def create_project(req: ProjectCreate):
    """Create a new project with its initial meta.json."""
    project_id = req.project_id or str(uuid.uuid4())[:12]  # 12 chars for reasonable collision resistance
    _validate_project_id(project_id)

    pdir = _project_dir(project_id)
    if pdir.exists():
        raise HTTPException(status_code=409, detail=f"Project '{project_id}' already exists")

    pdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "project_id": project_id,
        "requirement": req.requirement,
        "user_stories": [],
        "features": [],
        "architecture": {},
        "iteration": 0,
        "status": "created",
    }
    _write_meta(project_id, meta)

    # Save to project memory
    _get_memory().save_project(
        project_id=project_id,
        requirement=req.requirement,
        status="created",
    )

    return {"project_id": project_id, "status": "created"}


@router.get("/projects")
def list_projects():
    """List all projects by reading their meta.json files."""
    projects_dir = _projects_dir()
    if not projects_dir.exists():
        return []

    results = []
    for entry in sorted(projects_dir.iterdir()):
        meta_path = entry / "meta.json"
        if entry.is_dir() and meta_path.exists():
            try:
                # UTF-8 优先，失败尝试 GBK（Windows 中文环境）
                try:
                    text = meta_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text = meta_path.read_text(encoding="gbk", errors="replace")
                meta = json.loads(text)
                results.append({
                    "project_id": meta.get("project_id", entry.name),
                    "requirement": meta.get("requirement", ""),
                    "status": meta.get("status", "unknown"),
                    "iteration": meta.get("iteration", 0),
                })
            except (json.JSONDecodeError, KeyError, OSError):
                continue
    return results


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    """Get project details from meta.json."""
    _validate_project_id(project_id)
    meta = _read_meta(project_id)
    return {
        "project_id": meta.get("project_id", project_id),
        "requirement": meta.get("requirement", ""),
        "user_stories": meta.get("user_stories", []),
        "features": meta.get("features", []),
        "architecture": meta.get("architecture", {}),
        "iteration": meta.get("iteration", 0),
        "status": meta.get("status", "unknown"),
    }


@router.get("/projects/{project_id}/files")
def get_project_files(project_id: str):
    """Return all source files for a project as a dict."""
    _validate_project_id(project_id)
    _read_meta(project_id)  # ensure project exists
    pdir = _project_dir(project_id)
    files: dict[str, str] = {}
    max_file_size = 1024 * 1024  # 1MB per file
    max_files = 100  # Maximum number of files
    for fpath in sorted(pdir.rglob("*")):
        if fpath.is_file() and len(files) < max_files:
            try:
                # Skip files that are too large
                if fpath.stat().st_size > max_file_size:
                    continue
                rel = str(fpath.relative_to(pdir))
                files[rel] = fpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return {"files": files}


@router.get("/projects/{project_id}/files/{file_path:path}")
async def preview_file(project_id: str, file_path: str):
    """Preview a file's content with appropriate media type."""
    _validate_project_id(project_id)
    _validate_file_path(file_path)

    pdir = _project_dir(project_id)
    _read_meta(project_id)  # ensure project exists
    full_path = _safe_resolve(pdir, file_path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Binary file -- serve as octet-stream
        return StreamingResponse(
            io.BytesIO(full_path.read_bytes()),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'inline; filename="{full_path.name}"'},
        )

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=_get_media_type(file_path),
        headers={"Content-Disposition": f'inline; filename="{full_path.name}"'},
    )


@router.get("/projects/{project_id}/download")
def download_project(project_id: str):
    """Download all project files as a zip archive."""
    _validate_project_id(project_id)
    _read_meta(project_id)  # ensure project exists
    pdir = _project_dir(project_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in sorted(pdir.rglob("*")):
            if fpath.is_file():
                arcname = str(fpath.relative_to(pdir))
                zf.write(fpath, arcname)
    buf.seek(0)
    zip_content = buf.getvalue()

    return StreamingResponse(
        io.BytesIO(zip_content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{project_id}.zip"',
            "Content-Length": str(len(zip_content)),
        },
    )


@router.get("/projects/{project_id}/download/{file_path:path}")
async def download_file(project_id: str, file_path: str):
    """Download a single file from a project."""
    _validate_project_id(project_id)
    _validate_file_path(file_path)

    pdir = _project_dir(project_id)
    _read_meta(project_id)  # ensure project exists
    full_path = _safe_resolve(pdir, file_path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    file_content = full_path.read_bytes()
    return StreamingResponse(
        io.BytesIO(file_content),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{full_path.name}"',
            "Content-Length": str(len(file_content)),
        },
    )


# ── Resume / Rethink / Cancel ───────────────────────────────────────────


@router.post("/resume")
def resume_project(req: ResumeRequest):
    """Resume an interrupted project (forwards to WebSocket logic)."""
    meta = _read_meta(req.project_id)
    if meta.get("status") not in ("waiting_approval", "interrupted", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Project is in '{meta.get('status')}' state, cannot resume",
        )
    return {"status": "resumed", "project_id": req.project_id}


@router.post("/rethink")
def rethink_project(req: RethinkRequest):
    """Trigger a rethink on a project (forwards to WebSocket logic)."""
    meta = _read_meta(req.project_id)
    return {"status": "rethinking", "project_id": req.project_id, "feedback": req.feedback}


@router.post("/cancel")
def cancel_project(req: CancelRequest):
    """Cancel a running project."""
    meta = _read_meta(req.project_id)
    meta["status"] = "cancelled"
    _write_meta(req.project_id, meta)

    # Update status in project memory
    _get_memory().update_status(req.project_id, "cancelled")

    return {"status": "cancelled", "project_id": req.project_id}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """Delete a project and all its files."""
    import shutil
    _validate_project_id(project_id)

    # Check if project exists
    project_dir = _project_dir(project_id)
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    # Delete project directory
    shutil.rmtree(project_dir)

    # Remove from memory
    try:
        _get_memory().update_status(project_id, "deleted")
    except Exception:
        pass

    return {"status": "deleted", "project_id": project_id}
