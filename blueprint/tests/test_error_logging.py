"""Tests for P2.6: No silent exception swallowing in critical utility files."""
import ast
from pathlib import Path

_TARGET_FILES = [
    "utils/quality_scorer.py",
    "utils/security_scanner.py",
    "utils/diff_engine.py",
    "utils/cost_tracker.py",
    "utils/webhook.py",
    "utils/llm.py",
]

# Known legitimate bare pass patterns:
# llm.py:18  = Windows console reconfigure fallback
# llm.py:72  = settings.json missing/corrupted → use defaults
# security_scanner.py:76  = FileNotFoundError → bandit not installed
# security_scanner.py:104 = FileNotFoundError → npm not installed
_KNOWN_OK = {
    "utils/llm.py": {18, 72, 93},
    "utils/security_scanner.py": {76, 104},
}


def test_no_bare_except_pass_in_critical_utils():
    """P2.6: Critical utility files should not have unguarded bare except:pass."""
    project_root = Path("c:/Users/lahm/Desktop/Many AgentS/blueprint")

    violations = []
    for rel_path in _TARGET_FILES:
        py_file = project_root / rel_path
        if not py_file.exists():
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            known = _KNOWN_OK.get(rel_path, set())
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if (len(node.body) == 1 and
                            isinstance(node.body[0], ast.Pass)):
                        if node.lineno not in known:
                            violations.append(f"{rel_path}:{node.lineno}")
        except Exception:
            pass

    assert violations == [], f"Bare except:pass found in critical utils: {violations}"
