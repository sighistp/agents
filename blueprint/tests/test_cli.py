"""Tests for CLI tool."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from blueprint.cli import cli
from click.testing import CliRunner


def test_cli_list_projects():
    """Should list projects."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("projects").mkdir(exist_ok=True)
        (Path("projects") / "proj-1").mkdir(exist_ok=True)
        (Path("projects") / "proj-1" / "meta.json").write_text(
            json.dumps({"requirement": "test", "status": "created"})
        )
        with patch("blueprint.cli._projects_dir", return_value=Path("projects")):
            result = runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            assert "proj-1" in result.output


def test_cli_help():
    """Should show help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Blueprint" in result.output or "blueprint" in result.output.lower()
