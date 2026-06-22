"""Tests for P2.5: Content-Disposition header injection."""
import pytest


def test_sanitize_filename_removes_newlines():
    """P2.5: Should strip \\r\\n from filenames."""
    from blueprint.api.projects import _sanitize_filename
    result = _sanitize_filename("evil\r\nname.py")
    assert "\r" not in result
    assert "\n" not in result


def test_sanitize_filename_removes_path_separators():
    """P2.5: Should strip path separators."""
    from blueprint.api.projects import _sanitize_filename
    result = _sanitize_filename("../../../etc/passwd")
    assert "/" not in result


def test_sanitize_filename_preserves_normal():
    """P2.5: Normal filenames should pass through."""
    from blueprint.api.projects import _sanitize_filename
    result = _sanitize_filename("my_project.py")
    assert result == "my_project.py"


def test_sanitize_filename_limits_length():
    """P2.5: Long filenames should be truncated."""
    from blueprint.api.projects import _sanitize_filename
    result = _sanitize_filename("a" * 300)
    assert len(result) <= 200


def test_sanitize_filename_removes_null_bytes():
    """P2.5: Should strip null bytes."""
    from blueprint.api.projects import _sanitize_filename
    result = _sanitize_filename("file\x00name.py")
    assert "\x00" not in result


def test_sanitize_filename_removes_control_chars():
    """P2.5: Should strip control characters."""
    from blueprint.api.projects import _sanitize_filename
    result = _sanitize_filename("file\x01\x02\x1fname.py")
    assert "\x01" not in result
    assert "\x02" not in result
    assert "\x1f" not in result


def test_sanitize_filename_removes_colon_and_quotes():
    """P2.5: Should strip characters dangerous in headers."""
    from blueprint.api.projects import _sanitize_filename
    result = _sanitize_filename('file:"name"<>|?.py')
    for ch in ':"<>|':
        assert ch not in result
