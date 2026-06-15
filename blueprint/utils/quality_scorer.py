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

        total = sum(scores[k] * SCORE_DIMENSIONS[k]["weight"] / 100 for k in scores)
        total = round(min(100, max(0, total)), 1)

        return {
            "total": total,
            "dimensions": scores,
            "grade": self._grade(total),
            "suggestions": self._generate_suggestions(scores),
        }

    def _scan_files(self, project_path: Path) -> list[Path]:
        skip = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.superpowers', '_blueprint'}
        files = []
        for f in project_path.rglob("*"):
            if f.is_file() and f.suffix in ('.py', '.js', '.ts', '.html', '.css', '.json', '.md'):
                if not any(part in skip for part in f.parts):
                    files.append(f)
        return files

    def _score_complexity(self, files: list[Path]) -> float:
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
            return 60.0

        avg_func_len = sum(function_lengths) / len(function_lengths)
        avg_nesting = sum(nesting_depths) / len(nesting_depths)

        score = 100.0
        if total_complexity > 50: score -= 30
        elif total_complexity > 20: score -= 15
        if avg_func_len > 50: score -= 25
        elif avg_func_len > 30: score -= 10
        if avg_nesting > 4: score -= 25
        elif avg_nesting > 3: score -= 10
        return max(0, score)

    def _calc_nesting(self, node: ast.AST, depth: int = 0) -> int:
        max_depth = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_depth = self._calc_nesting(child, depth + 1)
                max_depth = max(max_depth, child_depth)
        return max_depth

    def _score_test_coverage(self, files: list[Path]) -> float:
        source_files = [f for f in files if not f.name.startswith("test_") and f.suffix == ".py"]
        test_files = [f for f in files if f.name.startswith("test_") and f.suffix == ".py"]
        if not source_files:
            return 50.0
        ratio = len(test_files) / len(source_files)
        return min(100, ratio * 100)

    def _score_security(self, files: list[Path]) -> float:
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

    def _score_maintainability(self, files: list[Path]) -> float:
        score = 60.0
        if len(files) >= 3:
            score += 20.0
        if any(f.name in ('requirements.txt', 'package.json') for f in files):
            score += 10.0
        if any(f.name == '.gitignore' for f in files):
            score += 10.0
        return min(100, score)

    def _score_documentation(self, files: list[Path]) -> float:
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
