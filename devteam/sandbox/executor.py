"""Sandbox code executor - runs code in isolated temp directories with resource limits."""
import os
import signal
import subprocess
import sys
import tempfile
import time


# Resource limits for sandboxed execution
MAX_MEMORY_MB = 256  # Maximum memory in MB
MAX_CPU_SECONDS = 30  # Maximum CPU time in seconds

# Safe environment for sandboxed execution (no secrets)
_SAFE_ENV = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
    "LANG": "en_US.UTF-8",
    "PYTHONIOENCODING": "utf-8",
}


def _get_safe_env(tmpdir: str) -> dict:
    """Create a safe environment for sandboxed execution."""
    env = _SAFE_ENV.copy()
    env["HOME"] = tmpdir
    env["TMPDIR"] = tmpdir
    env["TEMP"] = tmpdir  # Windows
    return env


def _set_resource_limits():
    """Set resource limits for the child process."""
    if sys.platform == "win32":
        # Windows: use Job Objects via subprocess creation flags
        # CREATE_JOB_OBJECT = 0x00020000, JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        # Not fully supported via preexec_fn, rely on timeout + taskkill
        return

    try:
        import resource
        memory_limit = MAX_MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS))
    except (ImportError, ValueError):
        pass


def execute_python(code: str, timeout: int = 30, cwd: str | None = None) -> dict:
    """Execute Python code with timeout and resource limits.

    Args:
        code: Python source code to execute
        timeout: Maximum execution time in seconds
        cwd: Working directory for execution (None = use tmpdir)

    Returns:
        dict with keys: stdout, stderr, returncode
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "main.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        exec_cwd = cwd if cwd and os.path.isdir(cwd) else tmpdir
        try:
            # Use sys.executable for consistent Python interpreter
            python_cmd = sys.executable if sys.executable else "python"
            proc = subprocess.Popen(
                [python_cmd, file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=exec_cwd,
                env=_get_safe_env(tmpdir),  # Safe environment without secrets
                start_new_session=True,  # New process group
                preexec_fn=_set_resource_limits if sys.platform != "win32" else None
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return {"stdout": stdout, "stderr": stderr, "returncode": proc.returncode}
        except subprocess.TimeoutExpired:
            # Kill entire process tree on timeout
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True)
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), 9)  # SIGKILL
                except ProcessLookupError:
                    pass
            try:
                proc.kill()
                proc.wait()
            except (OSError, ProcessLookupError):
                pass  # Process already terminated
            return {"stdout": "", "stderr": "Timeout", "returncode": -1}


def execute_node(code: str, timeout: int = 30) -> dict:
    """Execute Node.js code in a temporary directory with timeout and resource limits.

    Args:
        code: JavaScript source code to execute
        timeout: Maximum execution time in seconds

    Returns:
        dict with keys: stdout, stderr, returncode
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "main.js")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            proc = subprocess.Popen(
                ["node", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=tmpdir,
                env=_get_safe_env(tmpdir),  # Safe environment without secrets
                start_new_session=True,
                preexec_fn=_set_resource_limits if sys.platform != "win32" else None
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return {"stdout": stdout, "stderr": stderr, "returncode": proc.returncode}
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True)
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), 9)
                except ProcessLookupError:
                    pass
            try:
                proc.kill()
                proc.wait()
            except (OSError, ProcessLookupError):
                pass
            return {"stdout": "", "stderr": "Timeout", "returncode": -1}


def execute_sql(code: str, timeout: int = 30) -> dict:
    """Execute SQL in an in-memory SQLite database with timeout protection.

    Args:
        code: SQL statement to execute
        timeout: Maximum execution time in seconds

    Returns:
        dict with keys: stdout, stderr, returncode
    """
    import sqlite3
    conn = sqlite3.connect(":memory:")
    deadline = time.time() + timeout

    def progress_handler():
        """Abort query if deadline exceeded."""
        return 1 if time.time() > deadline else 0

    conn.set_progress_handler(progress_handler, 100)  # Check every 100 VM instructions
    max_rows = 1000  # Maximum rows to return
    max_output_size = 1024 * 100  # 100KB max output
    try:
        cursor = conn.execute(code)
        rows = cursor.fetchmany(max_rows)
        output = str(rows)
        if len(output) > max_output_size:
            output = output[:max_output_size] + "\n... (truncated)"
        return {"stdout": output, "stderr": "", "returncode": 0}
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            return {"stdout": "", "stderr": "Timeout", "returncode": -1}
        return {"stdout": "", "stderr": str(e), "returncode": 1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": 1}
    finally:
        conn.close()
