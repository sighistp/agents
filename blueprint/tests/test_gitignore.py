"""Tests for P0.5: Secret files must be in .gitignore."""
from pathlib import Path


def test_gitignore_covers_secrets():
    """P0.5: .gitignore must exclude all secret file patterns."""
    gitignore_path = Path(__file__).parent.parent.parent / ".gitignore"
    if not gitignore_path.exists():
        # Check project root
        gitignore_path = Path("c:/Users/lahm/Desktop/Many AgentS/.gitignore")

    content = gitignore_path.read_text().lower()

    # Must have entries for secret files
    assert ".blueprint_secret" in content or "*.secret" in content, \
        ".blueprint_secret should be in .gitignore"
    assert ".devteam_secret" in content or "*.secret" in content, \
        ".devteam_secret should be in .gitignore"


def test_no_secret_files_in_git_index():
    """P0.5: No secret files should be tracked by git."""
    import subprocess
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True,
        cwd="c:/Users/lahm/Desktop/Many AgentS"
    )
    tracked = result.stdout.lower()
    assert ".devteam_secret" not in tracked, ".devteam_secret should not be tracked"
    assert ".blueprint_secret" not in tracked, ".blueprint_secret should not be tracked"
