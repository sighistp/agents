"""DevTeam — AI 开发团队启动脚本

一键启动 DevTeam 服务，浏览器自动打开。
"""

import os
import sys
import webbrowser
from pathlib import Path

# Windows 编码修复：强制 UTF-8，防止 emoji 等字符导致崩溃
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保可以导入 devteam 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from devteam.utils.logger import setup_logging

setup_logging()

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ── 创建 FastAPI 应用 ────────────────────────────────────────────────

# 先导入main.py的app（包含所有路由和lifespan）
from devteam.main import app

# ── 静态文件 ─────────────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── 路由 ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """返回主页"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "DevTeam API is running. Static files not found."}


@app.get("/index.html")
async def index_html():
    """返回主页（兼容直接访问index.html）"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "DevTeam API is running. Static files not found."}


@app.get("/login.html")
async def login_html():
    """返回登录页"""
    login_path = static_dir / "login.html"
    if login_path.exists():
        return FileResponse(str(login_path))
    return {"message": "Login page not found."}


@app.get("/projects.html")
async def projects_html():
    """返回项目列表页"""
    path = static_dir / "projects.html"
    if path.exists():
        return FileResponse(str(path))
    return {"message": "Projects page not found."}


@app.get("/project-detail.html")
async def project_detail_html():
    """返回项目详情页"""
    path = static_dir / "project-detail.html"
    if path.exists():
        return FileResponse(str(path))
    return {"message": "Project detail page not found."}


@app.get("/settings.html")
async def settings_html():
    """返回设置页"""
    path = static_dir / "settings.html"
    if path.exists():
        return FileResponse(str(path))
    return {"message": "Settings page not found."}


# ── 启动 ─────────────────────────────────────────────────────────────

def main():
    """启动 DevTeam 服务"""
    import uvicorn

    print()
    print("  ╔══════════════════════════════════╗")
    print("  ║   DevTeam — AI 开发团队           ║")
    print("  ╚══════════════════════════════════╝")
    print()
    print("  启动中... 请稍候")
    print()

    # 自动打开浏览器
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open("http://localhost:8080")

    import threading
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    print("  ╔══════════════════════════════════╗")
    print("  ║   服务已就绪！                    ║")
    print("  ║   http://localhost:8080           ║")
    print("  ║   按 Ctrl+C 停止服务              ║")
    print("  ╚══════════════════════════════════╝")
    print()

    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")


if __name__ == "__main__":
    main()
