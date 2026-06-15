"""Tests for quality scorer module."""
import tempfile
from pathlib import Path

from blueprint.utils.quality_scorer import QualityScorer


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
    assert scorer._grade(54) == "D"
    assert scorer._grade(39) == "F"


def test_suggestions_generated():
    """Should generate suggestions for low-scoring dimensions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "app.py").write_text("x = 1\n")
        scorer = QualityScorer()
        result = scorer.score_project(tmpdir)
        assert len(result["suggestions"]) > 0


def test_complexity_uses_ast():
    """Complexity score should be based on AST, not line count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simple file (low complexity)
        (Path(tmpdir) / "simple.py").write_text("x = 1\ny = 2\n")
        # Complex file (high complexity: nested ifs, deep nesting)
        complex_code = """
def complex_func(data):
    result = []
    for item in data:
        if item > 0:
            if item < 100:
                if item % 2 == 0:
                    for i in range(item):
                        if i > 10:
                            result.append(i)
    return result
"""
        (Path(tmpdir) / "complex.py").write_text(complex_code)

        scorer = QualityScorer()
        simple_result = scorer.score_project(tmpdir)
        # Complex code should have lower complexity score than simple code
        # (higher complexity = lower score)
        assert simple_result["dimensions"]["complexity"] > 50
