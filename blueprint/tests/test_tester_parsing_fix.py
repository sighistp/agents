"""Tests for P2.4: test_passed default value."""


def test_extract_test_passed_no_match_returns_false():
    """P2.4: When no test output pattern matches, should return False."""
    from blueprint.agents.tester import _extract_test_passed
    result = _extract_test_passed("Some random output with no test results", False)
    assert result is False


def test_extract_test_passed_explicit_pass():
    """Explicit pass should return True (pytest format: N passed)."""
    from blueprint.agents.tester import _extract_test_passed
    result = _extract_test_passed("5 passed, 0 failed in 0.1s", False)
    assert result is True


def test_extract_test_passed_zero_failures():
    """0 failures should return True."""
    from blueprint.agents.tester import _extract_test_passed
    result = _extract_test_passed("全部通过（0失败）", False)
    assert result is True


def test_extract_test_passed_execution_error_overrides():
    """When had_execution_errors is True, should always return False."""
    from blueprint.agents.tester import _extract_test_passed
    result = _extract_test_passed("5 passed, 0 failed in 0.1s", True)
    assert result is False
