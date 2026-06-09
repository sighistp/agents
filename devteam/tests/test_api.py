"""Tests for REST API project endpoints."""

import json
import os
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devteam.api.projects import router as projects_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def projects_dir(tmp_path):
    """Provide a temporary projects directory."""
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
def app(projects_dir, monkeypatch):
    """Create a FastAPI test app with the projects router."""
    monkeypatch.setenv("DEVTEAM_PROJECT_DIR", str(projects_dir))
    test_app = FastAPI()
    test_app.include_router(projects_router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _create_sample_project(projects_dir: Path, project_id: str = "test-project"):
    """Helper to create a sample project on disk."""
    project_path = projects_dir / project_id
    project_path.mkdir(exist_ok=True)
    meta = {
        "project_id": project_id,
        "requirement": "Build a todo app",
        "user_stories": [{"id": "US1", "title": "Add task"}],
        "features": [{"name": "Task CRUD"}],
        "architecture": {"tech_stack": {"backend": "FastAPI"}},
        "iteration": 1,
        "status": "delivered",
    }
    (project_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    with open(project_path / "main.py", "w", encoding="utf-8", newline="") as f:
        f.write("print('hello')\n")
    with open(project_path / "README.md", "w", encoding="utf-8", newline="") as f:
        f.write("# Todo App\n")
    return project_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateProject:
    def test_create_project_success(self, client, projects_dir):
        resp = client.post("/api/projects", json={
            "requirement": "Build a REST API",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "project_id" in data
        assert data["status"] == "created"

        # Verify project directory was created
        project_path = projects_dir / data["project_id"]
        assert project_path.exists()
        meta_path = project_path / "meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["requirement"] == "Build a REST API"

    def test_create_project_with_custom_id(self, client, projects_dir):
        resp = client.post("/api/projects", json={
            "requirement": "Build a chatbot",
            "project_id": "my-chatbot",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "my-chatbot"
        assert (projects_dir / "my-chatbot").exists()


class TestListProjects:
    def test_list_empty(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_projects(self, client, projects_dir):
        _create_sample_project(projects_dir, "proj-a")
        _create_sample_project(projects_dir, "proj-b")
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        ids = {p["project_id"] for p in data}
        assert ids == {"proj-a", "proj-b"}


class TestGetProject:
    def test_get_project_success(self, client, projects_dir):
        _create_sample_project(projects_dir, "my-proj")
        resp = client.get("/api/projects/my-proj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "my-proj"
        assert data["requirement"] == "Build a todo app"
        assert data["status"] == "delivered"

    def test_get_project_not_found(self, client):
        resp = client.get("/api/projects/nonexistent")
        assert resp.status_code == 404


class TestGetProjectFiles:
    def test_get_files(self, client, projects_dir):
        _create_sample_project(projects_dir, "file-proj")
        resp = client.get("/api/projects/file-proj/files")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        files = data["files"]
        assert "main.py" in files
        assert "README.md" in files
        assert files["main.py"] == "print('hello')\n"

    def test_get_files_not_found(self, client):
        resp = client.get("/api/projects/ghost/files")
        assert resp.status_code == 404


class TestDownloadProject:
    def test_download_zip(self, client, projects_dir):
        _create_sample_project(projects_dir, "zip-proj")
        resp = client.get("/api/projects/zip-proj/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

        # Verify the zip contents
        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            names = zf.namelist()
            assert "meta.json" in names
            assert "main.py" in names
            assert "README.md" in names
            main_content = zf.read("main.py").decode("utf-8")
            assert main_content == "print('hello')\n"

    def test_download_not_found(self, client):
        resp = client.get("/api/projects/missing/download")
        assert resp.status_code == 404


class TestCancelProject:
    def test_cancel_project(self, client, projects_dir):
        _create_sample_project(projects_dir, "cancel-proj")
        resp = client.post("/api/cancel", json={"project_id": "cancel-proj"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"


class TestResumeAndRethink:
    def test_resume_no_active(self, client):
        """Resume without a project should return an error."""
        resp = client.post("/api/resume", json={"project_id": "nope"})
        assert resp.status_code in (400, 404)

    def test_rethink_no_active(self, client):
        resp = client.post("/api/rethink", json={"project_id": "nope"})
        assert resp.status_code in (400, 404)
