"""Tests for sandbox code execution."""
import pytest


def test_execute_python_hello():
    """Python code printing hello should return stdout."""
    from devteam.sandbox.executor import execute_python

    result = execute_python("print('hello')")

    assert result["stdout"] == "hello\n"
    assert result["stderr"] == ""
    assert result["returncode"] == 0


def test_execute_python_syntax_error():
    """Python code with syntax error should return error."""
    from devteam.sandbox.executor import execute_python

    result = execute_python("def foo(")

    assert result["returncode"] != 0
    assert "SyntaxError" in result["stderr"] or "syntax" in result["stderr"].lower()


def test_python_timeout():
    """Python code that times out should return timeout error."""
    from devteam.sandbox.executor import execute_python

    code = "import time; time.sleep(10)"
    result = execute_python(code, timeout=1)

    assert result["returncode"] == -1
    assert "timeout" in result["stderr"].lower()


def test_execute_sql_select():
    """SQL SELECT should return results."""
    from devteam.sandbox.executor import execute_sql

    result = execute_sql("SELECT 1 + 1 AS result")

    assert result["returncode"] == 0
    assert "2" in result["stdout"]


def test_execute_sql_syntax_error():
    """SQL with syntax error should return error."""
    from devteam.sandbox.executor import execute_sql

    result = execute_sql("SELCT * FORM table")

    assert result["returncode"] != 0
    assert result["stderr"] != ""


def test_python_runs_in_temp_directory():
    """Python code should run in an isolated temp directory, not the project root."""
    from devteam.sandbox.executor import execute_python
    import os

    code = "import os; print(os.getcwd())"
    result = execute_python(code)

    assert result["returncode"] == 0
    # Should be in a temp directory, not the project root
    cwd = result["stdout"].strip()
    assert "tmp" in cwd.lower() or "temp" in cwd.lower() or not cwd.startswith(os.getcwd())
