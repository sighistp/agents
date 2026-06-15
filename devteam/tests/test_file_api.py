"""Tests for project CRUD and file management API."""
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devteam.api.projects import router
from devteam.utils.memory import ProjectMemory


@pytest.fixture()
def tmp_projects(tmp_path, monkeypatch):
    """Provide a temporary projects directory via env var."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    monkeypatch.setenv("DEVTEAM_PROJECT_DIR", str(projects_dir))
    return projects_dir


@pytest.fixture()
def memory(tmp_path, monkeypatch):
    """Provide a temporary memory database for testing."""
    db_path = str(tmp_path / "test_memory.db")
    mem = ProjectMemory(db_path)
    import devteam.utils.memory as mem_mod
    mem_mod._memory = mem
    yield mem
    mem.close()
    mem_mod._memory = None


@pytest.fixture()
def client(tmp_projects, memory):
    """Create a TestClient with the projects router."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _create_project(tmp_projects, project_id="test-proj", requirement="Build an app"):
    """Helper: create a project directory with meta.json and some files."""
    pdir = tmp_projects / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "project_id": project_id,
        "requirement": requirement,
        "user_stories": [],
        "features": [],
        "architecture": {},
        "iteration": 0,
        "status": "created",
    }
    (pdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return pdir


# ── Create Project ───────────────────────────────────────────────────────


def test_create_project(client, tmp_projects):
    """POST /api/projects should create a project and return its info."""
    resp = client.post(
        "/api/projects",
        json={"requirement": "Build a todo app", "project_id": "my-todo"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "my-todo"
    assert data["status"] == "created"

    # Verify directory was created on disk
    assert (tmp_projects / "my-todo" / "meta.json").exists()


def test_create_project_auto_id(client):
    """POST /api/projects without project_id should auto-generate one."""
    resp = client.post("/api/projects", json={"requirement": "Something"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"]  # non-empty
    assert len(data["project_id"]) > 0


def test_create_project_invalid_id(client):
    """POST /api/projects with invalid project_id should return 400."""
    resp = client.post(
        "/api/projects",
        json={"requirement": "Bad", "project_id": "../escape"},
    )
    assert resp.status_code == 400


def test_create_project_duplicate(client, tmp_projects):
    """POST /api/projects with existing project_id should upsert (return 200)."""
    _create_project(tmp_projects, "dup-proj")
    resp = client.post(
        "/api/projects",
        json={"requirement": "Updated requirement", "project_id": "dup-proj"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "updated"


# ── List Projects ────────────────────────────────────────────────────────


def test_list_projects_empty(client, tmp_projects):
    """GET /api/projects with no projects should return empty list."""
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_projects(client, tmp_projects):
    """GET /api/projects should list all projects."""
    _create_project(tmp_projects, "proj-a", "Requirement A")
    _create_project(tmp_projects, "proj-b", "Requirement B")

    resp = client.get("/api/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 2
    ids = {p["project_id"] for p in projects}
    assert ids == {"proj-a", "proj-b"}


# ── Get Project ──────────────────────────────────────────────────────────


def test_get_project(client, tmp_projects):
    """GET /api/projects/{id} should return project details."""
    _create_project(tmp_projects, "detail-proj", "Do something")

    resp = client.get("/api/projects/detail-proj")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "detail-proj"
    assert data["requirement"] == "Do something"


def test_get_project_not_found(client, tmp_projects):
    """GET /api/projects/{id} for missing project should return 404."""
    resp = client.get("/api/projects/nonexistent")
    assert resp.status_code == 404


# ── Get Project Files ────────────────────────────────────────────────────


def test_get_project_files(client, tmp_projects):
    """GET /api/projects/{id}/files should return file contents as dict."""
    pdir = _create_project(tmp_projects, "files-proj")
    (pdir / "main.py").write_text("print('hello')", encoding="utf-8")
    (pdir / "style.css").write_text("body{}", encoding="utf-8")
    subdir = pdir / "src"
    subdir.mkdir()
    (subdir / "utils.py").write_text("def helper(): pass", encoding="utf-8")

    resp = client.get("/api/projects/files-proj/files")
    assert resp.status_code == 200
    data = resp.json()
    files = data["files"]
    assert "main.py" in files
    assert "style.css" in files
    assert str(Path("src/utils.py")) in files
    assert files["main.py"] == "print('hello')"


def test_get_project_files_not_found(client, tmp_projects):
    """GET /api/projects/{id}/files for missing project should return 404."""
    resp = client.get("/api/projects/ghost/files")
    assert resp.status_code == 404


# ── Preview File ─────────────────────────────────────────────────────────


def test_preview_file_text(client, tmp_projects):
    """GET /api/projects/{id}/files/{path} should return file content."""
    pdir = _create_project(tmp_projects, "preview-proj")
    (pdir / "hello.py").write_text("print('world')", encoding="utf-8")

    resp = client.get("/api/projects/preview-proj/files/hello.py")
    assert resp.status_code == 200
    assert "text/x-python" in resp.headers["content-type"]
    assert resp.text == "print('world')"


def test_preview_file_html(client, tmp_projects):
    """Preview should return correct media type for HTML files."""
    pdir = _create_project(tmp_projects, "html-proj")
    (pdir / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")

    resp = client.get("/api/projects/html-proj/files/index.html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_preview_file_css(client, tmp_projects):
    """Preview should return correct media type for CSS files."""
    pdir = _create_project(tmp_projects, "css-proj")
    (pdir / "style.css").write_text("body { color: red; }", encoding="utf-8")

    resp = client.get("/api/projects/css-proj/files/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_preview_file_js(client, tmp_projects):
    """Preview should return correct media type for JS files."""
    pdir = _create_project(tmp_projects, "js-proj")
    (pdir / "app.js").write_text("console.log('hi');", encoding="utf-8")

    resp = client.get("/api/projects/js-proj/files/app.js")
    assert resp.status_code == 200
    assert "text/javascript" in resp.headers["content-type"]


def test_preview_file_not_found(client, tmp_projects):
    """Preview of missing file should return 404."""
    _create_project(tmp_projects, "no-file-proj")
    resp = client.get("/api/projects/no-file-proj/files/missing.txt")
    assert resp.status_code == 404


def test_preview_file_path_traversal(client, tmp_projects):
    """Preview with path traversal should be rejected (400) or not found (404)."""
    _create_project(tmp_projects, "secure-proj")
    # The HTTP client may normalize '..' in URLs, so we get either 400 or 404
    resp = client.get("/api/projects/secure-proj/files/../../../etc/passwd")
    assert resp.status_code in (400, 404)


def test_preview_file_path_traversal_double_dot(client, tmp_projects):
    """Preview with '..' in path should be rejected (400) or not found (404)."""
    _create_project(tmp_projects, "secure2-proj")
    resp = client.get("/api/projects/secure2-proj/files/sub/../../secret.txt")
    assert resp.status_code in (400, 404)


def test_preview_binary_file(client, tmp_projects):
    """Preview of binary file should return octet-stream."""
    pdir = _create_project(tmp_projects, "bin-proj")
    (pdir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

    resp = client.get("/api/projects/bin-proj/files/image.png")
    assert resp.status_code == 200
    assert "application/octet-stream" in resp.headers["content-type"]


def test_preview_subdirectory_file(client, tmp_projects):
    """Preview should work for files in subdirectories."""
    pdir = _create_project(tmp_projects, "subdir-proj")
    subdir = pdir / "src"
    subdir.mkdir()
    (subdir / "main.py").write_text("def main(): pass", encoding="utf-8")

    resp = client.get("/api/projects/subdir-proj/files/src/main.py")
    assert resp.status_code == 200
    assert "def main(): pass" in resp.text


# ── Download Single File ─────────────────────────────────────────────────


def test_download_file(client, tmp_projects):
    """GET /api/projects/{id}/download/{path} should return file bytes."""
    pdir = _create_project(tmp_projects, "dl-proj")
    (pdir / "readme.txt").write_text("Hello World", encoding="utf-8")

    resp = client.get("/api/projects/dl-proj/download/readme.txt")
    assert resp.status_code == 200
    assert resp.content == b"Hello World"
    assert "application/octet-stream" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_download_file_not_found(client, tmp_projects):
    """Download of missing file should return 404."""
    _create_project(tmp_projects, "dl-miss-proj")
    resp = client.get("/api/projects/dl-miss-proj/download/nope.txt")
    assert resp.status_code == 404


def test_download_file_path_traversal(client, tmp_projects):
    """Download with path traversal should be rejected (400) or not found (404)."""
    _create_project(tmp_projects, "dl-sec-proj")
    resp = client.get("/api/projects/dl-sec-proj/download/../../secret")
    assert resp.status_code in (400, 404)


def test_download_binary_file(client, tmp_projects):
    """Download should preserve binary content exactly."""
    pdir = _create_project(tmp_projects, "dl-bin-proj")
    binary_content = bytes(range(256))
    (pdir / "data.bin").write_bytes(binary_content)

    resp = client.get("/api/projects/dl-bin-proj/download/data.bin")
    assert resp.status_code == 200
    assert resp.content == binary_content


# ── Download Project Zip ─────────────────────────────────────────────────


def test_download_project_zip(client, tmp_projects):
    """GET /api/projects/{id}/download should return a valid zip."""
    pdir = _create_project(tmp_projects, "zip-proj")
    (pdir / "main.py").write_text("print('hello')", encoding="utf-8")
    (pdir / "readme.txt").write_text("README content", encoding="utf-8")
    subdir = pdir / "lib"
    subdir.mkdir()
    (subdir / "utils.py").write_text("def util(): pass", encoding="utf-8")

    resp = client.get("/api/projects/zip-proj/download")
    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]
    assert "zip-proj.zip" in resp.headers.get("content-disposition", "")

    # Verify zip contents
    zip_buffer = io.BytesIO(resp.content)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        names = set(zf.namelist())
        assert "main.py" in names
        assert "readme.txt" in names
        assert "lib/utils.py" in names
        assert "meta.json" in names

        # Verify file contents
        assert zf.read("main.py") == b"print('hello')"
        assert zf.read("readme.txt") == b"README content"


def test_download_project_zip_not_found(client, tmp_projects):
    """Zip download for missing project should return 404."""
    resp = client.get("/api/projects/ghost/download")
    assert resp.status_code == 404


def test_download_project_zip_empty(client, tmp_projects):
    """Zip download for project with only meta.json should still work."""
    _create_project(tmp_projects, "empty-proj")

    resp = client.get("/api/projects/empty-proj/download")
    assert resp.status_code == 200

    zip_buffer = io.BytesIO(resp.content)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        names = set(zf.namelist())
        assert "meta.json" in names


# ── Invalid Project ID ───────────────────────────────────────────────────


def test_invalid_project_id_in_get(client):
    """GET with invalid project_id should return 400."""
    resp = client.get("/api/projects/bad%20space")
    assert resp.status_code == 400


# ── Conversations / Executions / Export ─────────────────────────────────


def test_get_conversations(client, tmp_projects):
    """GET /api/projects/{id}/conversations returns conversation history."""
    _create_project(tmp_projects, "conv-proj")
    resp = client.get("/api/projects/conv-proj/conversations")
    assert resp.status_code == 200
    assert "conversations" in resp.json()


def test_get_executions(client, tmp_projects):
    """GET /api/projects/{id}/executions returns execution summary."""
    _create_project(tmp_projects, "exec-proj")
    resp = client.get("/api/projects/exec-proj/executions")
    assert resp.status_code == 200
    assert "executions" in resp.json()


def test_export_project(client, tmp_projects):
    """GET /api/projects/{id}/export returns a zip file."""
    _create_project(tmp_projects, "export-proj")
    resp = client.get("/api/projects/export-proj/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"


def test_get_state_returns_name(client, tmp_projects, memory):
    """GET /api/projects/{id}/state returns name field."""
    _create_project(tmp_projects, "name-proj")
    memory.save_snapshot("name-proj", requirement="Build an app", status="created")
    resp = client.get("/api/projects/name-proj/state")
    assert resp.status_code == 200
    assert "name" in resp.json()
