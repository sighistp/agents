"""Tests for doc generator module."""
import tempfile
from pathlib import Path

from blueprint.utils.doc_generator import DocGenerator


def test_generate_readme():
    """Should generate README.md content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text("def hello():\n    return 'world'\n")
        gen = DocGenerator()
        result = gen.generate(tmpdir, "做一个计算器")
        assert "readme" in result
        assert "计算器" in result["readme"]


def test_generate_empty_project():
    """Empty project should still generate readme."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = DocGenerator()
        result = gen.generate(tmpdir, "test")
        assert "readme" in result


def test_detect_tech_stack():
    """Should detect Python/Node/HTML projects."""
    gen = DocGenerator()
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "app.py").write_text("x = 1")
        stack = gen._detect_tech_stack(Path(tmpdir))
        assert "python" in stack

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "package.json").write_text("{}")
        stack = gen._detect_tech_stack(Path(tmpdir))
        assert "node" in stack
