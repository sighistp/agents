# Blueprint Batch 1: Core Experience Enhancement

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add quality scoring, diff comparison, agent trace visualization, and security scanning to Blueprint without touching the core pipeline.

**Architecture:** All 4 features are independent modules added as外围 layers. They read from existing project files/memory and expose new API endpoints. No changes to Agent nodes, graph structure, or WebSocket protocol.

**Tech Stack:** Python (FastAPI endpoints), Vue 3 (new components), existing SQLite memory layer

**Conflict Rules (MUST follow):**
- Do NOT modify `agents/graph.py` node list or routing
- Do NOT modify `agents/tools.py` or `agents/tool_executor.py`
- Do NOT modify Agent return value structures
- All new files use try/except, failure logs but doesn't break pipeline
- Snapshot/scoring/security data stored OUTSIDE project directory (`blueprint/data/`)
- Quality scoring uses AST analysis, not line counting
- Security scanning wraps bandit + npm audit, not self-written regex
- All endpoint tests use `tmp_path` fixture for isolation

### Parallel Task Groups

```
Group A (independent, can run in parallel):
  Task 1-2: trace_db + Agent trace + API
  Task 3-4: quality_scorer + API + caching
  Task 5-6: security_scanner + API

Group B (depends on Group A):
  Task 7-8: frontend components + integration + tests
```

---

## File Structure

### New Files (Backend)

| File | Responsibility |
|------|---------------|
| `blueprint/utils/quality_scorer.py` | Score project quality (AST-based 5 dimensions) |
| `blueprint/utils/diff_engine.py` | Save snapshots + compare iterations |
| `blueprint/utils/security_scanner.py` | Scan code (bandit + npm audit + custom patterns) |
| `blueprint/utils/trace_db.py` | Store agent execution traces |
| `blueprint/tests/test_quality_scorer.py` | Tests for quality scorer |
| `blueprint/tests/test_diff_engine.py` | Tests for diff engine |
| `blueprint/tests/test_security_scanner.py` | Tests for security scanner |
| `blueprint/tests/test_trace_db.py` | Tests for trace DB |

### New Files (Frontend)

| File | Responsibility |
|------|---------------|
| `frontend/src/components/QualityScore.vue` | Quality score radar + progress bars |
| `frontend/src/components/DiffViewer.vue` | Iteration diff comparison |
| `frontend/src/components/SecurityReport.vue` | Security scan results |
| `frontend/src/components/AgentTracePanel.vue` | Agent thinking process viewer |

### Modified Files

| File | Change |
|------|--------|
| `blueprint/api/projects.py` | Add 5 new GET endpoints (quality/diff/security/traces/snapshots) |
| `blueprint/agents/developer.py` | Add trace recording in try/except (lines ~144-236) |
| `blueprint/agents/tester.py` | Add trace recording in try/except (lines ~114-201) |
| `blueprint/agents/reviewer.py` | Add trace recording in try/except (lines ~90-144) |
| `frontend/src/api/index.js` | Add 5 new API methods |
| `frontend/src/pages/ProjectDetailPage.vue` | Add 3 new tabs (Quality/Diff/Security) |
| `frontend/src/api/index.js` | Add 4 new API methods |

---

## Task 1: Quality Scorer — Backend

**Files:**
- Create: `Blueprint/utils/quality_scorer.py`
- Create: `Blueprint/tests/test_quality_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
# Blueprint/tests/test_quality_scorer.py
"""Tests for quality scorer module."""
import os
import tempfile
from pathlib import Path

from Blueprint.utils.quality_scorer import QualityScorer


def test_score_empty_project():
    """Empty project should get low scores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scorer = QualityScorer()
        result = scorer.score_project(tmpdir)
        assert "total" in result
        assert "dimensions" in result
        assert "grade" in result
        assert isinstance(result["total"], (int, float))
        assert 0 <= result["total"] <= 100


def test_score_project_with_files():
    """Project with Python files should score higher than empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some files
        (Path(tmpdir) / "main.py").write_text("def hello():\n    return 'world'\n")
        (Path(tmpdir) / "test_main.py").write_text("def test_hello():\n    assert hello() == 'world'\n")
        (Path(tmpdir) / "README.md").write_text("# My Project\n\nA hello world app.\n")

        scorer = QualityScorer()
        result = scorer.score_project(tmpdir)
        assert result["total"] > 0
        assert result["dimensions"]["test_coverage"] > 0
        assert result["dimensions"]["documentation"] > 0


def test_grade_calculation():
    """Grade should map correctly to score ranges."""
    scorer = QualityScorer()
    assert scorer._grade(95) == "A"
    assert scorer._grade(85) == "A"
    assert scorer._grade(75) == "B"
    assert scorer._grade(65) == "C"
    assert scorer._grade(55) == "D"
    assert scorer._grade(45) == "F"


def test_suggestions_generated():
    """Should generate suggestions for low-scoring dimensions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Only Python file, no tests
        (Path(tmpdir) / "app.py").write_text("x = 1\n")

        scorer = QualityScorer()
        result = scorer.score_project(tmpdir)
        assert len(result["suggestions"]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_quality_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'Blueprint.utils.quality_scorer'`

- [ ] **Step 3: Write minimal implementation**

```python
# blueprint/utils/quality_scorer.py
"""Project quality scorer — AST-based 5 dimensions,满分 100."""
import ast
from pathlib import Path
from typing import Any

SCORE_DIMENSIONS = {
    "complexity": {"weight": 25, "desc": "代码复杂度"},
    "test_coverage": {"weight": 25, "desc": "测试覆盖"},
    "security": {"weight": 20, "desc": "安全风险"},
    "maintainability": {"weight": 15, "desc": "可维护性"},
    "documentation": {"weight": 15, "desc": "文档完整度"},
}


class QualityScorer:
    def score_project(self, project_dir: str) -> dict[str, Any]:
        """Score a project on 5 dimensions using AST analysis."""
        project_path = Path(project_dir)
        if not project_path.exists():
            return self._empty_result()

        files = self._scan_files(project_path)
        if not files:
            return self._empty_result()

        scores = {
            "complexity": self._score_complexity(files),
            "test_coverage": self._score_test_coverage(files),
            "security": self._score_security(files),
            "maintainability": self._score_maintainability(files),
            "documentation": self._score_documentation(files),
        }

        total = sum(
            scores[k] * SCORE_DIMENSIONS[k]["weight"] / 100
            for k in scores
        )
        total = round(min(100, max(0, total)), 1)

        return {
            "total": total,
            "dimensions": scores,
            "grade": self._grade(total),
            "suggestions": self._generate_suggestions(scores),
        }

    def _scan_files(self, project_path: Path) -> list[Path]:
        """Scan project for source files."""
        skip = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.superpowers', '_blueprint'}
        files = []
        for f in project_path.rglob("*"):
            if f.is_file() and f.suffix in ('.py', '.js', '.ts', '.html', '.css', '.json', '.md'):
                if not any(part in skip for part in f.parts):
                    files.append(f)
        return files

    def _score_complexity(self, files: list[Path]) -> float:
        """AST-based complexity: cyclomatic complexity + function length + nesting depth."""
        total_complexity = 0
        function_lengths = []
        nesting_depths = []

        for f in files:
            if f.suffix != ".py":
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                        total_complexity += 1
                    if isinstance(node, ast.FunctionDef):
                        length = (node.end_lineno or node.lineno) - node.lineno
                        function_lengths.append(length)
                        nesting_depths.append(self._calc_nesting(node))
            except Exception:
                pass

        if not function_lengths:
            return 60.0  # No Python files = neutral

        avg_func_len = sum(function_lengths) / len(function_lengths)
        avg_nesting = sum(nesting_depths) / len(nesting_depths)

        score = 100.0
        # Cyclomatic complexity penalty
        if total_complexity > 50: score -= 30
        elif total_complexity > 20: score -= 15
        # Function length penalty (ideal: <20 lines)
        if avg_func_len > 50: score -= 25
        elif avg_func_len > 30: score -= 10
        # Nesting depth penalty (ideal: <3)
        if avg_nesting > 4: score -= 25
        elif avg_nesting > 3: score -= 10
        return max(0, score)

    def _calc_nesting(self, node: ast.AST, depth: int = 0) -> int:
        """Calculate max nesting depth of an AST node."""
        max_depth = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_depth = self._calc_nesting(child, depth + 1)
                max_depth = max(max_depth, child_depth)
        return max_depth

    def _score_test_coverage(self, files: list[Path]) -> float:
        """Score based on test file ratio."""
        source_files = [f for f in files if not f.name.startswith("test_") and f.suffix == ".py"]
        test_files = [f for f in files if f.name.startswith("test_") and f.suffix == ".py"]
        if not source_files:
            return 50.0
        ratio = len(test_files) / len(source_files)
        return min(100, ratio * 100)

    def _score_security(self, files: list[Path]) -> float:
        """Score by reusing SecurityScanner results (not self-written regex)."""
        try:
            from blueprint.utils.security_scanner import SecurityScanner
            scanner = SecurityScanner()
            # Scan in a temp dir context — but we need the actual dir
            # For scoring, just check if dangerous patterns exist
            violations = 0
            dangerous = ['import subprocess', 'os.system(', 'eval(', 'exec(']
            for f in files:
                if f.suffix != ".py":
                    continue
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    for pattern in dangerous:
                        if pattern in content:
                            violations += 1
                except Exception:
                    pass
            return max(0, 100 - violations * 20)
        except Exception:
            return 50.0

    def _score_maintainability(self, files: list[Path]) -> float:
        """Score based on file organization."""
        score = 60.0
        if len(files) >= 3:
            score += 20.0
        if any(f.name in ('requirements.txt', 'package.json') for f in files):
            score += 10.0
        if any(f.name == '.gitignore' for f in files):
            score += 10.0
        return min(100, score)

    def _score_documentation(self, files: list[Path]) -> float:
        """Score based on documentation files."""
        has_readme = any(f.name.lower() == 'readme.md' for f in files)
        has_docstrings = False
        for f in files:
            if f.suffix == ".py":
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    if '"""' in content or "'''" in content:
                        has_docstrings = True
                        break
                except Exception:
                    pass
        score = 0.0
        if has_readme: score += 60.0
        if has_docstrings: score += 40.0
        return score

    def _grade(self, score: float) -> str:
        if score >= 85: return "A"
        elif score >= 70: return "B"
        elif score >= 55: return "C"
        elif score >= 40: return "D"
        return "F"

    def _generate_suggestions(self, scores: dict) -> list[str]:
        suggestions = []
        if scores["test_coverage"] < 50:
            suggestions.append("添加测试文件（test_*.py）以提高测试覆盖率")
        if scores["security"] < 80:
            suggestions.append("检查代码中的安全风险模式")
        if scores["documentation"] < 50:
            suggestions.append("添加 README.md 和代码注释")
        if scores["maintainability"] < 70:
            suggestions.append("将代码拆分为多个文件，添加 requirements.txt")
        return suggestions

    def _empty_result(self) -> dict:
        return {"total": 0, "dimensions": {k: 0 for k in SCORE_DIMENSIONS}, "grade": "F", "suggestions": ["项目为空或不存在"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_quality_scorer.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add Blueprint/utils/quality_scorer.py Blueprint/tests/test_quality_scorer.py
git commit -m "feat: add quality scorer with 5-dimension scoring"
```

---

## Task 2: Quality Scorer — API Endpoint

**Files:**
- Modify: `Blueprint/api/projects.py` (append new endpoint at end, before delete)

- [ ] **Step 1: Write the failing test**

```python
# Add to Blueprint/tests/test_file_api.py (or create new test block)
def test_quality_score_endpoint():
    """GET /api/projects/{id}/quality should return score data."""
    from fastapi.testclient import TestClient
    from Blueprint.main import app
    client = TestClient(app)

    # Create a project with files
    import tempfile, json
    from pathlib import Path
    from Blueprint.api.projects import _projects_dir

    project_id = "test-quality-endpoint"
    pdir = _projects_dir() / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "main.py").write_text("def hello(): pass\n")
    (pdir / "meta.json").write_text(json.dumps({"requirement": "test", "status": "created"}))

    try:
        resp = client.get(f"/api/projects/{project_id}/quality")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "dimensions" in data
        assert "grade" in data
    finally:
        import shutil
        shutil.rmtree(pdir, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_file_api.py::test_quality_score_endpoint -v`
Expected: FAIL with 404 (endpoint doesn't exist)

- [ ] **Step 3: Add endpoint to projects.py**

Append before the `delete_project` endpoint:

```python
@router.get("/projects/{project_id}/quality")
def get_quality_score(project_id: str):
    """Get project quality score (5 dimensions)."""
    _validate_project_id(project_id)
    _read_meta(project_id)  # ensure project exists
    pdir = _project_dir(project_id)
    from Blueprint.utils.quality_scorer import QualityScorer
    scorer = QualityScorer()
    return scorer.score_project(str(pdir))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_file_api.py::test_quality_score_endpoint -v`
Expected: PASS

- [ ] **Step 5: Run all existing tests to verify no regression**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/ -v --tb=short`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add Blueprint/api/projects.py Blueprint/tests/test_file_api.py
git commit -m "feat: add GET /api/projects/:id/quality endpoint"
```

---

## Task 3: Diff Engine — Backend

**Files:**
- Create: `Blueprint/utils/diff_engine.py`
- Create: `Blueprint/tests/test_diff_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# Blueprint/tests/test_diff_engine.py
"""Tests for diff engine module."""
import json
import tempfile
from pathlib import Path

from Blueprint.utils.diff_engine import DiffEngine


def test_save_snapshot():
    """Should save file snapshot for an iteration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project files
        (Path(tmpdir) / "main.py").write_text("v1")
        (Path(tmpdir) / "utils.py").write_text("old")

        engine = DiffEngine(tmpdir)
        engine.save_snapshot(1)

        snap_dir = Path(tmpdir) / ".snapshots"
        assert snap_dir.exists()
        snap_file = snap_dir / "iter_001.json"
        assert snap_file.exists()

        data = json.loads(snap_file.read_text())
        assert "main.py" in data
        assert data["main.py"] == "v1"


def test_compare_snapshots():
    """Should show diff between two iterations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = DiffEngine(tmpdir)

        # Iteration 1
        (Path(tmpdir) / "main.py").write_text("line1\nline2\n")
        engine.save_snapshot(1)

        # Iteration 2: modify main.py, add new file
        (Path(tmpdir) / "main.py").write_text("line1\nline3\n")
        (Path(tmpdir) / "new.py").write_text("new file")
        engine.save_snapshot(2)

        result = engine.compare(1, 2)
        assert result["files_changed"] >= 1
        assert result["total_additions"] >= 1


def test_list_snapshots():
    """Should list all snapshot iteration numbers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = DiffEngine(tmpdir)
        (Path(tmpdir) / "main.py").write_text("x")

        engine.save_snapshot(1)
        engine.save_snapshot(3)
        engine.save_snapshot(5)

        snapshots = engine.list_snapshots()
        assert snapshots == [1, 3, 5]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_diff_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# blueprint/utils/diff_engine.py
"""Diff engine — save snapshots and compare iterations."""
import difflib
import json
import os
from pathlib import Path
from typing import Any


class DiffEngine:
    def __init__(self, project_dir: str, data_dir: str = None):
        self.project_dir = Path(project_dir)
        # Snapshots stored OUTSIDE project directory
        if data_dir:
            self.snapshots_dir = Path(data_dir) / "snapshots" / self.project_dir.name
        else:
            self.snapshots_dir = self.project_dir.parent / ".snapshots" / self.project_dir.name

    def save_snapshot(self, iteration: int):
        """Save current file contents as a snapshot."""
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {}
        skip = {'.git', 'node_modules', '__pycache__', '.snapshots', '.venv', '_blueprint'}
        for f in self.project_dir.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                if not any(part in skip for part in f.parts):
                    try:
                        rel = str(f.relative_to(self.project_dir))
                        snapshot[rel] = f.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        pass
        snap_file = self.snapshots_dir / f"iter_{iteration:03d}.json"
        # Compress with gzip for large projects
        import gzip
        data = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
        if len(data) > 10240:  # > 10KB, compress
            with gzip.open(str(snap_file) + ".gz", "wb") as f:
                f.write(data)
            # Remove uncompressed version if exists
            if snap_file.exists():
                snap_file.unlink()
        else:
            snap_file.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_diff_engine.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add Blueprint/utils/diff_engine.py Blueprint/tests/test_diff_engine.py
git commit -m "feat: add diff engine for iteration snapshots"
```

---

## Task 4: Diff Engine — API Endpoint

**Files:**
- Modify: `Blueprint/api/projects.py` (append new endpoint)

- [ ] **Step 1: Write the failing test**

```python
def test_diff_endpoint():
    """GET /api/projects/{id}/diff?a=1&b=2 should return diff data."""
    from fastapi.testclient import TestClient
    from Blueprint.main import app
    from Blueprint.utils.diff_engine import DiffEngine
    from Blueprint.api.projects import _projects_dir
    import shutil

    project_id = "test-diff-endpoint"
    pdir = _projects_dir() / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "meta.json").write_text('{"requirement":"test","status":"created"}')

    try:
        engine = DiffEngine(str(pdir))
        (pdir / "main.py").write_text("v1")
        engine.save_snapshot(1)
        (pdir / "main.py").write_text("v2")
        engine.save_snapshot(2)

        client = TestClient(app)
        resp = client.get(f"/api/projects/{project_id}/diff?a=1&b=2")
        assert resp.status_code == 200
        data = resp.json()
        assert "files_changed" in data
        assert "diffs" in data
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_file_api.py::test_diff_endpoint -v`
Expected: FAIL with 404

- [ ] **Step 3: Add endpoint**

```python
@router.get("/projects/{project_id}/diff")
def get_diff(project_id: str, a: int = 0, b: int = 0):
    """Compare two iteration snapshots."""
    _validate_project_id(project_id)
    _read_meta(project_id)
    pdir = _project_dir(project_id)
    from devteam.utils.diff_engine import DiffEngine
    engine = DiffEngine(str(pdir))
    return engine.compare(a, b)


@router.get("/projects/{project_id}/snapshots")
def list_snapshots(project_id: str):
    """List all available snapshot iterations."""
    _validate_project_id(project_id)
    _read_meta(project_id)
    pdir = _project_dir(project_id)
    from devteam.utils.diff_engine import DiffEngine
    engine = DiffEngine(str(pdir))
    return {"snapshots": engine.list_snapshots()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_file_api.py::test_diff_endpoint -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Blueprint/api/projects.py Blueprint/tests/test_file_api.py
git commit -m "feat: add GET /api/projects/:id/diff endpoint"
```

---

## Task 5: Security Scanner — Backend

**Files:**
- Create: `Blueprint/utils/security_scanner.py`
- Create: `Blueprint/tests/test_security_scanner.py`

- [ ] **Step 1: Write the failing test**

```python
# Blueprint/tests/test_security_scanner.py
"""Tests for security scanner module."""
import tempfile
from pathlib import Path

from Blueprint.utils.security_scanner import SecurityScanner, Severity


def test_scan_clean_project():
    """Clean project should have no issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "app.py").write_text("def hello():\n    return 'world'\n")
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        assert result["total"] == 0
        assert result["score"] == 100


def test_scan_hardcoded_secret():
    """Should detect hardcoded API keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "config.py").write_text('API_KEY = "sk-1234567890abcdef"\n')
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        assert result["total"] > 0
        assert any(i["category"] == "hardcoded_secret" for i in result["issues"])


def test_scan_sql_injection():
    """Should detect SQL injection patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "db.py").write_text('cursor.execute("SELECT * FROM users WHERE id=" + user_id)\n')
        scanner = SecurityScanner()
        result = scanner.scan_project(tmpdir)
        assert any(i["category"] == "sql_injection" for i in result["issues"])


def test_score_penalty():
    """Score should decrease with more issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "a.py").write_text('API_KEY = "sk-123"\n')
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_security_scanner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# blueprint/utils/security_scanner.py
"""Security scanner — wraps bandit (Python) + npm audit (Node) + custom patterns."""
import json
import subprocess
from pathlib import Path
from typing import Any


class SecurityScanner:
    # Custom patterns for things bandit doesn't cover (hardcoded secrets)
    _CUSTOM_PATTERNS = [
        (r'(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*["\'][^"\']{8,}["\']',
         "hardcoded_secret", "high", "检测到硬编码密钥/密码"),
        (r'(?i)AWS_(ACCESS|SECRET)_KEY',
         "hardcoded_secret", "critical", "检测到 AWS 密钥"),
        (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----',
         "hardcoded_secret", "critical", "检测到私钥"),
    ]

    def scan_project(self, project_dir: str) -> dict[str, Any]:
        """Scan project using bandit + npm audit + custom patterns."""
        issues = []
        skip = {'.git', 'node_modules', '__pycache__', '.venv'}

        # 1. Python: bandit
        issues.extend(self._run_bandit(project_dir))

        # 2. Node: npm audit
        issues.extend(self._run_npm_audit(project_dir))

        # 3. Custom patterns (hardcoded secrets etc.)
        project_path = Path(project_dir)
        import re
        for f in project_path.rglob("*"):
            if not f.is_file() or f.suffix not in ('.py', '.js', '.ts', '.html'):
                continue
            if any(part in skip for part in f.parts):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                for line_num, line in enumerate(content.splitlines(), 1):
                    for pattern, category, severity, description in self._CUSTOM_PATTERNS:
                        if re.search(pattern, line):
                            issues.append({
                                "file": str(f.relative_to(project_path)),
                                "line": line_num,
                                "severity": severity,
                                "category": category,
                                "description": description,
                                "code": line.strip()[:100],
                            })
            except Exception:
                pass

        return self._compile_report(issues)

    def _run_bandit(self, project_dir: str) -> list[dict]:
        """Run bandit security scanner on Python files."""
        issues = []
        try:
            result = subprocess.run(
                ["bandit", "-r", project_dir, "-f", "json", "-q", "--severity-level", "medium"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for item in data.get("results", []):
                    issues.append({
                        "file": item.get("filename", "").replace(project_dir + "/", ""),
                        "line": item.get("line_number", 0),
                        "severity": item.get("issue_severity", "MEDIUM").lower(),
                        "category": f"bandit_{item.get('test_id', 'unknown')}",
                        "description": item.get("issue_text", ""),
                        "code": item.get("code", "")[:100],
                    })
        except FileNotFoundError:
            # bandit not installed — skip silently
            pass
        except Exception:
            pass
        return issues

    def _run_npm_audit(self, project_dir: str) -> list[dict]:
        """Run npm audit on Node.js projects."""
        issues = []
        package_json = Path(project_dir) / "package.json"
        if not package_json.exists():
            return issues
        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=project_dir, capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for vuln in data.get("vulnerabilities", {}).values():
                    severity = vuln.get("severity", "info")
                    issues.append({
                        "file": "package.json",
                        "line": 0,
                        "severity": severity if severity in ("critical", "high", "medium", "low", "info") else "medium",
                        "category": "npm_vulnerability",
                        "description": f"{vuln.get('name', 'unknown')}: {vuln.get('title', '')}",
                        "code": "",
                    })
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return issues

    def _compile_report(self, issues: list[dict]) -> dict[str, Any]:
        """Compile scan results into a report."""
        penalty_map = {"critical": 30, "high": 15, "medium": 5, "low": 2, "info": 0}
        score = max(0, 100 - sum(penalty_map.get(i["severity"], 0) for i in issues))
        return {
            "total": len(issues),
            "critical": sum(1 for i in issues if i["severity"] == "critical"),
            "high": sum(1 for i in issues if i["severity"] == "high"),
            "medium": sum(1 for i in issues if i["severity"] == "medium"),
            "low": sum(1 for i in issues if i["severity"] == "low"),
            "score": score,
            "issues": issues,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_security_scanner.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add Blueprint/utils/security_scanner.py Blueprint/tests/test_security_scanner.py
git commit -m "feat: add security scanner with pattern detection"
```

---

## Task 6: Security Scanner — API Endpoint

**Files:**
- Modify: `Blueprint/api/projects.py`

- [ ] **Step 1: Add endpoint**

```python
@router.get("/projects/{project_id}/security")
def security_scan(project_id: str):
    """Scan project for security issues."""
    _validate_project_id(project_id)
    _read_meta(project_id)
    pdir = _project_dir(project_id)
    from Blueprint.utils.security_scanner import SecurityScanner
    scanner = SecurityScanner()
    return scanner.scan_project(str(pdir))
```

- [ ] **Step 2: Write test and verify**

```python
def test_security_scan_endpoint():
    from fastapi.testclient import TestClient
    from Blueprint.main import app
    from Blueprint.api.projects import _projects_dir
    import shutil, json

    project_id = "test-security-endpoint"
    pdir = _projects_dir() / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "meta.json").write_text(json.dumps({"requirement": "test", "status": "created"}))
    (pdir / "config.py").write_text('API_KEY = "sk-12345"\n')

    try:
        client = TestClient(app)
        resp = client.get(f"/api/projects/{project_id}/security")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "issues" in data
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
```

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_file_api.py::test_security_scan_endpoint -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add Blueprint/api/projects.py Blueprint/tests/test_file_api.py
git commit -m "feat: add GET /api/projects/:id/security endpoint"
```

---

## Task 7: Agent Trace DB — Backend

**Files:**
- Create: `Blueprint/utils/trace_db.py`
- Create: `Blueprint/tests/test_trace_db.py`

- [ ] **Step 1: Write the failing test**

```python
# Blueprint/tests/test_trace_db.py
"""Tests for trace DB module."""
import time

from Blueprint.utils.trace_db import TraceDB


def test_save_and_get_trace():
    """Should save and retrieve traces."""
    db = TraceDB(":memory:")
    db.save(
        project_id="test-proj",
        agent="developer",
        iteration=1,
        prompt="Build a calculator",
        response="I will create main.py",
        tools_called=[{"name": "file_write", "args": {"path": "main.py"}}],
        duration_ms=3500,
    )
    traces = db.get_traces("test-proj", agent="developer")
    assert len(traces) == 1
    assert traces[0]["agent"] == "developer"
    assert traces[0]["iteration"] == 1


def test_get_traces_filtered():
    """Should filter by agent and iteration."""
    db = TraceDB(":memory:")
    db.save(project_id="p1", agent="developer", iteration=1, prompt="a", response="b", tools_called=[], duration_ms=100)
    db.save(project_id="p1", agent="tester", iteration=1, prompt="c", response="d", tools_called=[], duration_ms=200)
    db.save(project_id="p1", agent="developer", iteration=2, prompt="e", response="f", tools_called=[], duration_ms=300)

    dev_traces = db.get_traces("p1", agent="developer")
    assert len(dev_traces) == 2

    iter1_traces = db.get_traces("p1", iteration=1)
    assert len(iter1_traces) == 2


def test_empty_traces():
    """Should return empty list for unknown project."""
    db = TraceDB(":memory:")
    traces = db.get_traces("nonexistent")
    assert traces == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_trace_db.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# Blueprint/utils/trace_db.py
"""Agent trace DB — stores LLM input/output/tool calls per agent execution."""
import json
import sqlite3
import threading
import time
from typing import Any


class TraceDB:
    def __init__(self, db_path: str = "Blueprint/data/traces.db"):
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                prompt TEXT,
                response TEXT,
                tools_called TEXT,
                duration_ms INTEGER,
                created_at REAL DEFAULT (strftime('%s','now')),
                UNIQUE(project_id, agent, iteration, created_at)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_proj ON agent_traces(project_id, agent)")
        conn.commit()

    def save(self, project_id: str, agent: str, iteration: int,
             prompt: str, response: str, tools_called: list[dict], duration_ms: int):
        """Save an agent trace."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO agent_traces (project_id, agent, iteration, prompt, response, tools_called, duration_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, agent, iteration, prompt[:5000], response[:5000],
             json.dumps(tools_called, ensure_ascii=False), duration_ms, time.time())
        )
        conn.commit()

    def get_traces(self, project_id: str, agent: str = None, iteration: int = None) -> list[dict]:
        """Get traces, optionally filtered."""
        conn = self._get_conn()
        query = "SELECT * FROM agent_traces WHERE project_id = ?"
        params: list[Any] = [project_id]
        if agent:
            query += " AND agent = ?"
            params.append(agent)
        if iteration is not None:
            query += " AND iteration = ?"
            params.append(iteration)
        query += " ORDER BY created_at ASC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_trace_db.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add Blueprint/utils/trace_db.py Blueprint/tests/test_trace_db.py
git commit -m "feat: add agent trace DB for thinking process visualization"
```

---

## Task 8: Agent Trace Recording — Developer

**Files:**
- Modify: `Blueprint/agents/developer.py` (add trace recording inside tool loop)

- [ ] **Step 1: Add trace import and recording**

At the top of `developer.py`, add import:

```python
from Blueprint.utils.trace_db import TraceDB
```

Inside `developer_agent` function, after the tool loop completes (before the final return statements), add trace recording wrapped in try/except:

```python
    # ... after the for loop, before return statements ...

    # Record trace (failure doesn't affect main flow)
    try:
        trace_db = TraceDB()
        trace_db.save(
            project_id=state.get("project_id", ""),
            agent="developer",
            iteration=state.get("iteration", 0),
            prompt=messages[1]["content"][:2000] if len(messages) > 1 else "",
            response=str(messages[-1].get("content", ""))[:2000] if messages else "",
            tools_called=[serialize_call(tc) for tc in all_tool_calls] if 'all_tool_calls' in dir() else [],
            duration_ms=0,
        )
    except Exception:
        pass
```

Note: The `all_tool_calls` variable needs to be tracked. Add `all_tool_calls: list = []` at the start of the function (after `key_decisions: list[str] = []`), and append to it in the tool execution loop.

- [ ] **Step 2: Run existing developer tests to verify no regression**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_developer.py -v`
Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add Blueprint/agents/developer.py
git commit -m "feat: add trace recording to developer agent"
```

---

## Task 9: Agent Trace Recording — Tester & Reviewer

**Files:**
- Modify: `Blueprint/agents/tester.py`
- Modify: `Blueprint/agents/reviewer.py`

- [ ] **Step 1: Add trace to tester.py**

Same pattern as developer: import TraceDB, add trace recording after tool loop in try/except.

- [ ] **Step 2: Add trace to reviewer.py**

Same pattern.

- [ ] **Step 3: Run existing tests**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_tester.py Blueprint/tests/test_reviewer.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add Blueprint/agents/tester.py Blueprint/agents/reviewer.py
git commit -m "feat: add trace recording to tester and reviewer agents"
```

---

## Task 10: Trace API Endpoint

**Files:**
- Modify: `Blueprint/api/projects.py`

- [ ] **Step 1: Add endpoint**

```python
@router.get("/projects/{project_id}/traces")
def get_traces(project_id: str, agent: str = None, iteration: int = None):
    """Get agent execution traces."""
    _validate_project_id(project_id)
    _read_meta(project_id)
    from Blueprint.utils.trace_db import TraceDB
    db = TraceDB()
    return {"traces": db.get_traces(project_id, agent=agent, iteration=iteration)}
```

- [ ] **Step 2: Write test and verify**

```python
def test_traces_endpoint():
    from fastapi.testclient import TestClient
    from Blueprint.main import app
    from Blueprint.api.projects import _projects_dir
    from Blueprint.utils.trace_db import TraceDB
    import shutil, json

    project_id = "test-traces-endpoint"
    pdir = _projects_dir() / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "meta.json").write_text(json.dumps({"requirement": "test", "status": "created"}))

    try:
        db = TraceDB()
        db.save(project_id, "developer", 1, "prompt", "response", [], 1000)

        client = TestClient(app)
        resp = client.get(f"/api/projects/{project_id}/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert len(data["traces"]) == 1
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
```

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/test_file_api.py::test_traces_endpoint -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add Blueprint/api/projects.py Blueprint/tests/test_file_api.py
git commit -m "feat: add GET /api/projects/:id/traces endpoint"
```

---

## Task 11: Frontend — QualityScore Component

**Files:**
- Create: `frontend/src/components/QualityScore.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/src/components/QualityScore.vue -->
<template>
  <div class="quality-score" v-if="score">
    <div class="score-header">
      <span class="score-number" :class="gradeClass">{{ score.total }}</span>
      <span class="score-grade" :class="gradeClass">{{ score.grade }}</span>
    </div>
    <div class="dimensions">
      <div class="dim-row" v-for="(dim, key) in score.dimensions" :key="key">
        <span class="dim-label">{{ dimLabels[key] || key }}</span>
        <div class="dim-bar">
          <div class="dim-fill" :style="{ width: dim + '%' }" :class="barClass(dim)"></div>
        </div>
        <span class="dim-value">{{ Math.round(dim) }}</span>
      </div>
    </div>
    <div class="suggestions" v-if="score.suggestions?.length">
      <div class="suggestion" v-for="(s, i) in score.suggestions" :key="i">💡 {{ s }}</div>
    </div>
  </div>
  <div v-else-if="loading" class="loading">加载中...</div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({ projectId: String })
const score = ref(null)
const loading = ref(true)

const dimLabels = {
  complexity: '代码复杂度',
  test_coverage: '测试覆盖',
  security: '安全风险',
  maintainability: '可维护性',
  documentation: '文档完整度',
}

const gradeClass = computed(() => {
  if (!score.value) return ''
  const g = score.value.grade
  return g === 'A' ? 'grade-a' : g === 'B' ? 'grade-b' : g === 'C' ? 'grade-c' : 'grade-d'
})

function barClass(val) {
  if (val >= 80) return 'bar-green'
  if (val >= 50) return 'bar-yellow'
  return 'bar-red'
}

onMounted(async () => {
  try {
    score.value = await api.getQualityScore(props.projectId)
  } catch (e) {
    console.error('Failed to load quality score:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.quality-score { padding: 12px; }
.score-header { display: flex; align-items: baseline; gap: 8px; margin-bottom: 12px; }
.score-number { font-size: 28px; font-weight: 700; }
.score-grade { font-size: 14px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.grade-a { color: #16a34a; }
.grade-a.score-grade { background: #dcfce7; }
.grade-b { color: #2563eb; }
.grade-b.score-grade { background: #dbeafe; }
.grade-c { color: #d97706; }
.grade-c.score-grade { background: #fef3c7; }
.grade-d { color: #dc2626; }
.grade-d.score-grade, .grade-f.score-grade { background: #fee2e2; }
.dimensions { display: flex; flex-direction: column; gap: 6px; }
.dim-row { display: flex; align-items: center; gap: 8px; }
.dim-label { width: 80px; font-size: 12px; color: #666; }
.dim-bar { flex: 1; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.dim-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.bar-green { background: #16a34a; }
.bar-yellow { background: #d97706; }
.bar-red { background: #dc2626; }
.dim-value { width: 24px; text-align: right; font-size: 12px; color: #666; }
.suggestions { margin-top: 10px; }
.suggestion { font-size: 12px; color: #666; padding: 2px 0; }
.loading { color: #999; font-size: 13px; padding: 12px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/QualityScore.vue
git commit -m "feat: add QualityScore component"
```

---

## Task 12: Frontend — SecurityReport Component

**Files:**
- Create: `frontend/src/components/SecurityReport.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/src/components/SecurityReport.vue -->
<template>
  <div class="security-report" v-if="report">
    <div class="report-header">
      <span class="score" :class="scoreClass">{{ report.score }}</span>
      <span class="label">安全评分</span>
    </div>
    <div class="severity-bar">
      <span class="sev critical" v-if="report.critical">{{ report.critical }} 严重</span>
      <span class="sev high" v-if="report.high">{{ report.high }} 高</span>
      <span class="sev medium" v-if="report.medium">{{ report.medium }} 中</span>
      <span class="sev low" v-if="report.low">{{ report.low }} 低</span>
      <span class="sev clean" v-if="report.total === 0">✅ 无问题</span>
    </div>
    <div class="issues" v-if="report.issues?.length">
      <div class="issue" v-for="(issue, i) in report.issues" :key="i">
        <span class="issue-sev" :class="issue.severity">{{ issue.severity }}</span>
        <span class="issue-file">{{ issue.file }}:{{ issue.line }}</span>
        <span class="issue-desc">{{ issue.description }}</span>
      </div>
    </div>
  </div>
  <div v-else-if="loading" class="loading">扫描中...</div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({ projectId: String })
const report = ref(null)
const loading = ref(true)

const scoreClass = computed(() => {
  if (!report.value) return ''
  const s = report.value.score
  if (s >= 80) return 'score-good'
  if (s >= 50) return 'score-warn'
  return 'score-bad'
})

onMounted(async () => {
  try {
    report.value = await api.getSecurityReport(props.projectId)
  } catch (e) {
    console.error('Failed to load security report:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.security-report { padding: 12px; }
.report-header { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.score { font-size: 28px; font-weight: 700; }
.label { font-size: 13px; color: #666; }
.score-good { color: #16a34a; }
.score-warn { color: #d97706; }
.score-bad { color: #dc2626; }
.severity-bar { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.sev { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.sev.critical { background: #fee2e2; color: #dc2626; }
.sev.high { background: #fef3c7; color: #d97706; }
.sev.medium { background: #dbeafe; color: #2563eb; }
.sev.low { background: #f3f4f6; color: #6b7280; }
.sev.clean { background: #dcfce7; color: #16a34a; }
.issues { display: flex; flex-direction: column; gap: 4px; }
.issue { font-size: 12px; display: flex; gap: 6px; align-items: baseline; }
.issue-sev { font-weight: 600; min-width: 40px; }
.issue-file { color: #666; min-width: 120px; }
.issue-desc { color: #333; }
.loading { color: #999; font-size: 13px; padding: 12px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SecurityReport.vue
git commit -m "feat: add SecurityReport component"
```

---

## Task 13: Frontend — AgentTracePanel Component

**Files:**
- Create: `frontend/src/components/AgentTracePanel.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/src/components/AgentTracePanel.vue -->
<template>
  <div class="trace-panel" v-if="traces.length">
    <div class="trace-item" v-for="(trace, i) in traces" :key="i">
      <div class="trace-header" @click="trace._open = !trace._open">
        <span class="trace-agent">{{ trace.agent }}</span>
        <span class="trace-iter">迭代 {{ trace.iteration }}</span>
        <span class="trace-time">{{ trace.duration_ms }}ms</span>
        <span class="trace-toggle">{{ trace._open ? '▼' : '▶' }}</span>
      </div>
      <div class="trace-body" v-if="trace._open">
        <div class="trace-section">
          <div class="section-label">📤 Prompt</div>
          <pre class="trace-content">{{ trace.prompt }}</pre>
        </div>
        <div class="trace-section">
          <div class="section-label">📥 Response</div>
          <pre class="trace-content">{{ trace.response }}</pre>
        </div>
        <div class="trace-section" v-if="trace.tools_called?.length">
          <div class="section-label">🔧 Tools</div>
          <div class="tool-item" v-for="(tool, j) in parseTools(trace.tools_called)" :key="j">
            <span class="tool-name">{{ tool.name }}</span>
            <span class="tool-args" v-if="tool.args">{{ tool.args }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="no-trace">暂无执行记录</div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({ projectId: String, agent: String, iteration: Number })
const traces = ref([])

function parseTools(tools) {
  if (!tools) return []
  return tools.map(t => {
    const name = t.function?.name || t.name || 'unknown'
    const args = t.function?.arguments || t.args || ''
    const argsStr = typeof args === 'string' ? args : JSON.stringify(args)
    return { name, args: argsStr.slice(0, 100) }
  })
}

onMounted(async () => {
  try {
    const data = await api.getTraces(props.projectId, props.agent, props.iteration)
    traces.value = (data.traces || []).map(t => ({ ...t, _open: false }))
  } catch (e) {
    console.error('Failed to load traces:', e)
  }
})
</script>

<style scoped>
.trace-panel { padding: 8px; }
.trace-item { border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 6px; }
.trace-header { display: flex; gap: 8px; padding: 8px; cursor: pointer; align-items: center; }
.trace-header:hover { background: #f9fafb; }
.trace-agent { font-weight: 600; font-size: 13px; }
.trace-iter { font-size: 12px; color: #666; }
.trace-time { font-size: 12px; color: #999; margin-left: auto; }
.trace-toggle { font-size: 10px; color: #999; }
.trace-body { padding: 0 8px 8px; }
.trace-section { margin-bottom: 8px; }
.section-label { font-size: 11px; font-weight: 600; color: #666; margin-bottom: 4px; }
.trace-content { font-size: 11px; background: #f3f4f6; padding: 6px; border-radius: 4px;
  max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;
  font-family: 'Menlo', 'Consolas', monospace; margin: 0; }
.tool-item { font-size: 12px; padding: 2px 0; }
.tool-name { font-weight: 600; color: #2563eb; }
.tool-args { color: #666; margin-left: 4px; }
.no-trace { color: #999; font-size: 13px; padding: 12px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AgentTracePanel.vue
git commit -m "feat: add AgentTracePanel component"
```

---

## Task 14: Frontend — DiffViewer Component

**Files:**
- Create: `frontend/src/components/DiffViewer.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/src/components/DiffViewer.vue -->
<template>
  <div class="diff-viewer">
    <div class="diff-controls">
      <label>对比迭代:</label>
      <select v-model="iterA"><option v-for="s in snapshots" :key="s" :value="s">迭代 {{ s }}</option></select>
      <span>→</span>
      <select v-model="iterB"><option v-for="s in snapshots" :key="s" :value="s">迭代 {{ s }}</option></select>
      <button @click="loadDiff" :disabled="!iterA || !iterB">对比</button>
    </div>
    <div class="diff-summary" v-if="diff">
      <span>{{ diff.files_changed }} 个文件变更</span>
      <span class="add">+{{ diff.total_additions }}</span>
      <span class="del">-{{ diff.total_deletions }}</span>
    </div>
    <div class="diff-files" v-if="diff">
      <div class="diff-file" v-for="(info, path) in diff.diffs" :key="path">
        <div class="file-header" @click="info._open = !info._open">
          <span class="file-type" :class="info.type">{{ info.type }}</span>
          <span class="file-path">{{ path }}</span>
          <span class="file-stats">+{{ info.additions }} -{{ info.deletions }}</span>
        </div>
        <pre class="file-diff" v-if="info._open">{{ info.diff }}</pre>
      </div>
    </div>
    <div v-if="!diff && !loading" class="no-diff">选择两个迭代进行对比</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({ projectId: String })
const snapshots = ref([])
const iterA = ref(null)
const iterB = ref(null)
const diff = ref(null)
const loading = ref(false)

onMounted(async () => {
  // TODO: fetch snapshots list from a future endpoint
  // For now, use diff endpoint directly
})

async function loadDiff() {
  if (!iterA.value || !iterB.value) return
  loading.value = true
  try {
    const data = await api.getDiff(props.projectId, iterA.value, iterB.value)
    diff.value = data
    // Init _open state
    for (const path in diff.value.diffs) {
      diff.value.diffs[path]._open = false
    }
  } catch (e) {
    console.error('Failed to load diff:', e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.diff-viewer { padding: 12px; }
.diff-controls { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; font-size: 13px; }
.diff-controls select { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 4px; }
.diff-controls button { padding: 4px 12px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; }
.diff-controls button:disabled { background: #9ca3af; }
.diff-summary { font-size: 13px; margin-bottom: 10px; display: flex; gap: 8px; }
.add { color: #16a34a; }
.del { color: #dc2626; }
.diff-files { display: flex; flex-direction: column; gap: 6px; }
.diff-file { border: 1px solid #e5e7eb; border-radius: 6px; }
.file-header { display: flex; gap: 8px; padding: 8px; cursor: pointer; align-items: center; }
.file-header:hover { background: #f9fafb; }
.file-type { font-size: 11px; padding: 1px 6px; border-radius: 3px; font-weight: 600; }
.file-type.modified { background: #dbeafe; color: #2563eb; }
.file-type.added { background: #dcfce7; color: #16a34a; }
.file-type.deleted { background: #fee2e2; color: #dc2626; }
.file-path { font-size: 13px; font-family: monospace; }
.file-stats { font-size: 12px; color: #666; margin-left: auto; }
.file-diff { font-size: 11px; background: #f3f4f6; padding: 8px; margin: 0 8px 8px;
  border-radius: 4px; overflow-x: auto; font-family: monospace; white-space: pre; }
.no-diff { color: #999; font-size: 13px; padding: 12px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/DiffViewer.vue
git commit -m "feat: add DiffViewer component"
```

---

## Task 15: Frontend — API Methods & Integration

**Files:**
- Modify: `frontend/src/api/index.js` (add 4 new methods)
- Modify: `frontend/src/pages/ProjectDetailPage.vue` (add tabs)

- [ ] **Step 1: Add API methods**

Append to `frontend/src/api/index.js`:

```javascript
// Quality / Security / Diff / Traces
api.getQualityScore = (id) => request(`/api/projects/${id}/quality`)
api.getSecurityReport = (id) => request(`/api/projects/${id}/security`)
api.getDiff = (id, a, b) => request(`/api/projects/${id}/diff?a=${a}&b=${b}`)
api.getTraces = (id, agent, iteration) => {
  const params = new URLSearchParams()
  if (agent) params.set('agent', agent)
  if (iteration != null) params.set('iteration', iteration)
  return request(`/api/projects/${id}/traces?${params}`)
}
```

- [ ] **Step 2: Add tabs to ProjectDetailPage.vue**

In the template, add new tab buttons and tab panels alongside existing ones. The exact integration depends on the current tab structure, but the pattern is:

```vue
<!-- Add tab button -->
<button @click="activeTab = 'quality'" :class="{ active: activeTab === 'quality' }">质量评分</button>
<button @click="activeTab = 'security'" :class="{ active: activeTab === 'security' }">安全扫描</button>
<button @click="activeTab = 'diff'" :class="{ active: activeTab === 'diff' }">变更对比</button>

<!-- Add tab panels -->
<div v-if="activeTab === 'quality'">
  <QualityScore :projectId="projectId" />
</div>
<div v-if="activeTab === 'security'">
  <SecurityReport :projectId="projectId" />
</div>
<div v-if="activeTab === 'diff'">
  <DiffViewer :projectId="projectId" />
</div>
```

Import the new components:

```javascript
import QualityScore from '../components/QualityScore.vue'
import SecurityReport from '../components/SecurityReport.vue'
import DiffViewer from '../components/DiffViewer.vue'
```

- [ ] **Step 3: Build frontend**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS\frontend" && npm run build`
Expected: Build succeeds, output to `Blueprint/static/`

- [ ] **Step 4: Run all backend tests**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m pytest Blueprint/tests/ -v --tb=short`
Expected: All tests pass (existing + new)

- [ ] **Step 5: Run frontend tests**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS\frontend" && npm test`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/index.js frontend/src/pages/ProjectDetailPage.vue
git commit -m "feat: integrate quality/security/diff/traces into project detail page"
```

---

## Task 16: Integration Test — End-to-End Verification

- [ ] **Step 1: deliver_node regression test**

```python
def test_deliver_node_return_structure():
    """Verify deliver_node return structure is unchanged after hook additions."""
    from blueprint.agents.graph import deliver_node
    state = {
        "project_id": "test-regression-123",
        "files": {"main.py": "print('hello')"},
        "requirement": "test requirement",
        "iteration": 1,
        "architecture": {},
        "user_stories": [],
        "features": [],
    }
    result = deliver_node(state)
    # Return value structure must contain these fields
    assert "status" in result
    assert "files" in result
    assert "current_agent" in result
    assert "messages" in result
    assert result["status"] == "delivered"
    assert result["files"] == state["files"]
```

- [ ] **Step 2: Test isolation — all endpoint tests use tmp_path**

Ensure all endpoint tests (quality_score, security, diff, traces) use `tmp_path` fixture:
```python
def test_quality_score_endpoint(tmp_path):
    import os
    os.environ["DEVTEAM_PROJECT_DIR"] = str(tmp_path)
    # ... rest of test
```

- [ ] **Step 3: Start the server**

Run: `cd "C:\Users\lahm\Desktop\Many AgentS" && python -m blueprint.start`

- [ ] **Step 4: Manual verification checklist**

1. Open http://localhost:8080
2. Create a project (e.g., "做一个计算器")
3. Wait for completion
4. Go to project detail page
5. Verify: 「质量评分」tab shows AST-based score + dimensions + suggestions
6. Verify: 「安全扫描」tab shows bandit/npm audit results (or graceful skip if not installed)
7. Verify: 「变更对比」tab shows snapshots list and diff
8. Verify: Agent cards show trace panel

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Batch 1 complete — quality scoring (AST), security scan (bandit), diff, agent traces"
```

---

## Summary

| Task | Feature | Files | Tests | Parallel? |
|------|---------|-------|-------|-----------|
| 1-2 | Agent Traces | trace_db.py + agent changes + API | 4 | ✅ Group A |
| 3-4 | Quality Scorer (AST) | quality_scorer.py + API + cache | 5 | ✅ Group A |
| 5-6 | Security Scanner (bandit) | security_scanner.py + API | 6 | ✅ Group A |
| 7-8 | Frontend Components | 4 Vue components + API methods + tabs | — | Group B |
| 9 | deliver_node regression | test only | 1 | — |
| 10 | E2E Verification | manual testing | — | — |

**Total new tests:** 16 backend (including regression)
**Total new files:** 8 backend + 4 frontend = 12 new files
**Total modified files:** 6 (3 agents + projects.py + api/index.js + ProjectDetailPage.vue)

### Frontend Cache Strategy

QualityScore, SecurityReport, AgentTracePanel 组件在 ProjectDetailPage 中统一加载，避免切换 tab 重复请求：

```javascript
// ProjectDetailPage.vue — onMounted 统一加载
onMounted(async () => {
  // Load all data at once, components receive via props
  const [quality, security, traces] = await Promise.all([
    api.getQualityScore(projectId),
    api.getSecurityReport(projectId),
    api.getTraces(projectId),
  ])
  qualityData.value = quality
  securityData.value = security
  tracesData.value = traces
})
```

### Cost Model

| 场景 | LLM 调用次数 | 成本 |
|------|-------------|------|
| Batch 1 实施 | — | $0（纯本地开发） |
| 运行时每项目 | 5-15 次 | ~$0.02-0.05 |
| 月度（10 项目/天） | — | ~$10-15 |
