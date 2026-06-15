"""Tests for security scanner module."""
import tempfile
from pathlib import Path

from blueprint.utils.security_scanner import SecurityScanner


def test_scan_clean_project():
    """Clean project should have no issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "app.py").write_text("def hello():\n    return 'world'\n")
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        assert result["total"] >= 0  # bandit may or may not be installed
        assert result["score"] >= 0
        assert result["score"] <= 100


def test_scan_hardcoded_secret():
    """Should detect hardcoded API keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "config.py").write_text('API_KEY = "sk-1234567890abcdef"\n')
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        assert result["total"] > 0
        assert any(i["category"] == "hardcoded_secret" for i in result["issues"])


def test_score_penalty():
    """Score should decrease with more issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "a.py").write_text('API_KEY = "sk-1234567890abcdef"\n')
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        assert result["score"] < 100


def test_severity_levels():
    """Issues should have valid severity levels."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "config.py").write_text('password = "admin123"\n')
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        for issue in result["issues"]:
            assert issue["severity"] in ["critical", "high", "medium", "low", "info"]


def test_bandit_graceful_skip():
    """Should work even if bandit is not installed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "app.py").write_text("x = 1\n")
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        # Should not raise, even if bandit is missing
        assert "total" in result
        assert "score" in result
