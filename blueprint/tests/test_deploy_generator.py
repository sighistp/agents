"""Tests for deploy generator module."""
import tempfile
from pathlib import Path

from blueprint.utils.deploy_generator import DeployGenerator


def test_generate_dockerfile_python():
    """Should generate Dockerfile for Python project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text("x = 1")
        gen = DeployGenerator()
        result = gen.generate(tmpdir)
        assert "Dockerfile" in result
        assert "python" in result["Dockerfile"].lower()


def test_generate_dockerfile_node():
    """Should generate Dockerfile for Node project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "package.json").write_text("{}")
        gen = DeployGenerator()
        result = gen.generate(tmpdir)
        assert "Dockerfile" in result
        assert "node" in result["Dockerfile"].lower()


def test_generate_compose():
    """Should generate docker-compose.yml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text("x = 1")
        gen = DeployGenerator()
        result = gen.generate(tmpdir)
        assert "docker-compose.yml" in result


def test_generate_start_script():
    """Should generate start.sh."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text("x = 1")
        gen = DeployGenerator()
        result = gen.generate(tmpdir)
        assert "start.sh" in result
