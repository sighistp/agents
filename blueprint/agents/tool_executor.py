"""工具执行引擎"""
import json
import os
import tempfile
from pathlib import Path

from blueprint.agents.tools import get_call_name, get_call_args

_progress_callback = None

def set_progress_callback(cb):
    global _progress_callback
    _progress_callback = cb


def execute_tool(call, project_dir: str) -> str:
    """执行 tool_call，返回 JSON 字符串。失败不抛异常。"""
    name = get_call_name(call)
    args = get_call_args(call)

    if _progress_callback:
        try:
            _progress_callback(tool=name, args_summary=f"执行 {name}")
        except Exception:
            pass

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
        elif name == "run_linter":
            if "path" not in args:
                return json.dumps({"error": "run_linter 缺少 path 参数"})
            return _run_linter(args, project_dir)
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
        'settings.json', 'api_presets.json', '.blueprint_secret',
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
    """Execute Python code with project files available.

    Copies project files to temp directory so imports work,
    but blocks access to sensitive files like .env.
    """
    import shutil
    code = args["code"]
    _check_code_safety(code)
    from blueprint.sandbox.executor import execute_python as sandbox_exec
    timeout = min(args.get("timeout", 15), 30)

    # Create a working directory with project files (excluding sensitive ones)
    with tempfile.TemporaryDirectory() as workdir:
        if project_dir and os.path.isdir(project_dir):
            sensitive_names = {'.env', '.env.local', '.blueprint_secret', 'settings.json', '.git',
                               'node_modules', '__pycache__', 'venv', '.venv', '.superpowers'}
            for item in os.listdir(project_dir):
                if item in sensitive_names or item.startswith('.'):
                    continue
                src = os.path.join(project_dir, item)
                dst = os.path.join(workdir, item)
                try:
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
                    elif os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                except (OSError, shutil.Error):
                    pass

        result = sandbox_exec(code, timeout=timeout, cwd=workdir)
        return json.dumps(result)


# 统一的危险模式列表
_DANGEROUS_PATTERNS = [
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
    'shutil.rmtree',
    'os.unlink',
    'Path.unlink',
]


def _check_content_safety(content: str, filename: str):
    """C6: Block obviously malicious file content.

    Only checks Python files for dangerous imports/calls.
    HTML files are NOT checked — they need <script> tags to work.
    XSS risk is mitigated by DOMPurify in the frontend's OutputPanel.
    """
    if filename.endswith('.py'):
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in content:
                raise ValueError(f"文件内容包含不允许的模式: {pattern}")


def _check_code_safety(code: str):
    """C6: Block obviously dangerous code patterns."""
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in code:
            raise ValueError(f"代码包含不允许的模式: {pattern}")


def _run_linter(args: dict, project_dir: str) -> str:
    """Run ruff linter on a file, return structured results."""
    path = _resolve_safe_path(args["path"], project_dir)
    if not os.path.exists(path):
        return json.dumps({"error": f"文件不存在: {args['path']}"})

    try:
        import subprocess
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", path],
            capture_output=True, text=True, timeout=15
        )
        issues = json.loads(result.stdout) if result.stdout.strip() else []
        return json.dumps({
            "issues": [
                {
                    "file": i.get("filename", ""),
                    "line": i.get("location", {}).get("row", 0),
                    "code": i.get("code", ""),
                    "message": i.get("message", ""),
                    "severity": i.get("fix", {}).get("applicability", "error"),
                }
                for i in issues
            ],
            "score": max(0, 100 - len(issues) * 5),
            "total": len(issues),
        })
    except FileNotFoundError:
        return json.dumps({"issues": [], "score": 100, "total": 0, "skipped": True, "reason": "ruff not installed"})
    except Exception as e:
        return json.dumps({"error": f"linter 失败: {e}"})


