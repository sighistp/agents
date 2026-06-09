"""工具执行引擎"""
import json
import os
from pathlib import Path

from devteam.agents.tools import get_call_name, get_call_args


def execute_tool(call, project_dir: str) -> str:
    """执行 tool_call，返回 JSON 字符串。失败不抛异常。"""
    name = get_call_name(call)
    args = get_call_args(call)

    try:
        if name == "file_write":
            if "path" not in args or "content" not in args:
                return json.dumps({"error": "file_write 缺少 path 或 content 参数"})
            return _file_write(args, project_dir)
        elif name == "file_read":
            if "path" not in args:
                return json.dumps({"error": "file_read 缺少 path 参数"})
            return _file_read(args, project_dir)
        elif name == "execute_python":
            if "code" not in args:
                return json.dumps({"error": "execute_python 缺少 code 参数"})
            return _execute_python(args, project_dir)
        elif name == "done":
            return json.dumps({"status": "completed", **args})
        else:
            return json.dumps({"error": f"未知工具: {name}"})
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


def _resolve_safe_path(path: str, project_dir: str) -> str:
    """Validate and resolve path atomically. Returns resolved path or raises."""
    if not path or ".." in path or path.startswith(("/", "\\")):
        raise ValueError(f"不安全的文件路径: {path}")
    resolved = (Path(project_dir) / path).resolve()
    project_real = Path(project_dir).resolve()
    if not resolved.is_relative_to(project_real):
        raise ValueError(f"路径逃逸: {path}")
    # Block access to sensitive files (C4: prevent settings.json overwrite)
    blocked_names = {
        '.env', '.env.local', '.env.production', '.gitconfig', '.ssh',
        'settings.json', 'api_presets.json', '.devteam_secret',
        'config.py', 'config.json', 'credentials.json',
    }
    if resolved.name in blocked_names:
        raise ValueError(f"不允许访问系统配置文件: {path}")
    # Block entire data/ and .git/ directories
    blocked_dirs = {'data', '.git', '.claude', 'node_modules', '__pycache__'}
    parts = resolved.relative_to(project_real).parts
    if parts and parts[0] in blocked_dirs:
        raise ValueError(f"不允许访问系统目录: {path}")
    return str(resolved)


def _file_write(args, project_dir):
    path = _resolve_safe_path(args["path"], project_dir)
    content = args["content"]
    # C6: Block obviously malicious content
    _check_content_safety(content, args["path"])
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return json.dumps({"success": True, "path": args["path"]})


def _file_read(args, project_dir):
    path = _resolve_safe_path(args["path"], project_dir)
    if not os.path.exists(path):
        return json.dumps({"error": f"文件不存在: {args['path']}"})
    with open(path, "r", encoding="utf-8") as f:
        return json.dumps({"content": f.read()})


def _execute_python(args, project_dir):
    """Execute Python code in an isolated temp directory.

    Does NOT use project_dir as cwd to prevent access to .env and other sensitive files.
    The code runs in a fresh temp directory with a safe environment.
    """
    code = args["code"]
    # C6: Check for dangerous patterns before execution
    _check_code_safety(code)
    from devteam.sandbox.executor import execute_python as sandbox_exec
    timeout = min(args.get("timeout", 15), 30)
    result = sandbox_exec(code, timeout=timeout, cwd=None)
    return json.dumps(result)


def _check_content_safety(content: str, filename: str):
    """C6: Block obviously malicious file content."""
    # Only check Python files for dangerous imports
    if not filename.endswith('.py'):
        return
    dangerous_patterns = [
        'import socket',
        'import urllib',
        'import requests',
        'import httpx',
        'import subprocess',
        'os.system(',
        'os.popen(',
        'eval(',
        'exec(',
        '__import__(',
    ]
    for pattern in dangerous_patterns:
        if pattern in content:
            raise ValueError(f"文件内容包含不允许的模式: {pattern}")


def _check_code_safety(code: str):
    """C6: Block obviously dangerous code patterns."""
    dangerous = [
        'import socket',
        'import urllib',
        'import httpx',
        'os.system(',
        'os.popen(',
        '__import__(',
    ]
    for pattern in dangerous:
        if pattern in code:
            raise ValueError(f"代码包含不允许的模式: {pattern}")


def _validate_path(path, project_dir):
    if not path or ".." in path or path.startswith(("/", "\\")):
        raise ValueError(f"不安全的文件路径: {path}")
    real = os.path.realpath(os.path.join(project_dir, path))
    if not real.startswith(os.path.realpath(project_dir)):
        raise ValueError(f"路径逃逸: {path}")
