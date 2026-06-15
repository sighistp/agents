"""Tests for new analysis endpoints: quality, diff, snapshots, security, traces."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from blueprint.api.projects import router as projects_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def projects_dir(tmp_path):
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
def app(projects_dir, monkeypatch):
    monkeypatch.setenv("BLUEPRINT_PROJECT_DIR", str(projects_dir))
    test_app = FastAPI()
    test_app.include_router(projects_router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _create_sample_project(projects_dir: Path, project_id: str = "test-proj"):
    project_path = projects_dir / project_id
    project_path.mkdir(exist_ok=True)
    meta = {
        "project_id": project_id,
        "requirement": "Build a todo app",
        "user_stories": [],
        "features": [],
        "architecture": {},
        "iteration": 1,
        "status": "delivered",
    }
    (project_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (project_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (project_path / "README.md").write_text("# Todo\n", encoding="utf-8")
    return project_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestQualityEndpoint:
    def test_quality_success(self, client, projects_dir):
        _create_sample_project(projects_dir, "q-proj")
        resp = client.get("/api/projects/q-proj/quality")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "dimensions" in data
        assert "grade" in data
        assert "suggestions" in data

    def test_quality_not_found(self, client):
        resp = client.get("/api/projects/nonexistent/quality")
        assert resp.status_code == 404


class TestDiffEndpoint:
    def test_diff_success(self, client, projects_dir):
        proj = _create_sample_project(projects_dir, "d-proj")
        # Create two snapshots by using DiffEngine directly
        from blueprint.utils.diff_engine import DiffEngine
        engine = DiffEngine(str(proj))
        engine.save_snapshot(0)
        (proj / "main.py").write_text("print('updated')\n", encoding="utf-8")
        engine.save_snapshot(1)
        resp = client.get("/api/projects/d-proj/diff?a=0&b=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "iterations" in data
        assert data["iterations"] == [0, 1]
        assert "files_changed" in data

    def test_diff_defaults(self, client, projects_dir):
        proj = _create_sample_project(projects_dir, "d-proj2")
        from blueprint.utils.diff_engine import DiffEngine
        engine = DiffEngine(str(proj))
        engine.save_snapshot(0)
        resp = client.get("/api/projects/d-proj2/diff")
        assert resp.status_code == 200
        data = resp.json()
        assert "iterations" in data

    def test_diff_not_found(self, client):
        resp = client.get("/api/projects/nonexistent/diff?a=0&b=1")
        assert resp.status_code == 404


class TestSnapshotsEndpoint:
    def test_snapshots_success(self, client, projects_dir):
        proj = _create_sample_project(projects_dir, "s-proj")
        from blueprint.utils.diff_engine import DiffEngine
        engine = DiffEngine(str(proj))
        engine.save_snapshot(0)
        engine.save_snapshot(1)
        resp = client.get("/api/projects/s-proj/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data
        assert data["snapshots"] == [0, 1]

    def test_snapshots_empty(self, client, projects_dir):
        _create_sample_project(projects_dir, "s-empty")
        resp = client.get("/api/projects/s-empty/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["snapshots"] == []

    def test_snapshots_not_found(self, client):
        resp = client.get("/api/projects/nonexistent/snapshots")
        assert resp.status_code == 404


class TestSecurityEndpoint:
    def test_security_success(self, client, projects_dir):
        _create_sample_project(projects_dir, "sec-proj")
        resp = client.get("/api/projects/sec-proj/security")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "score" in data
        assert "issues" in data
        assert isinstance(data["issues"], list)

    def test_security_not_found(self, client):
        resp = client.get("/api/projects/nonexistent/security")
        assert resp.status_code == 404


class TestTracesEndpoint:
    def test_traces_success(self, client, projects_dir):
        _create_sample_project(projects_dir, "t-proj")
        resp = client.get("/api/projects/t-proj/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert isinstance(data["traces"], list)

    def test_traces_with_filters(self, client, projects_dir):
        _create_sample_project(projects_dir, "t-proj2")
        resp = client.get("/api/projects/t-proj2/traces?agent=coder&iteration=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data

    def test_traces_not_found(self, client):
        resp = client.get("/api/projects/nonexistent/traces")
        assert resp.status_code == 404
