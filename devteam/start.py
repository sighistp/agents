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

_index_path = static_dir / "index.html"


@app.get("/")
async def root():
    """返回 SPA 首页"""
    if _index_path.exists():
        return FileResponse(str(_index_path))
    return {"message": "DevTeam API is running. Static files not found."}


# ── SPA Catch-all ─────────────────────────────────────────────────────
# Vue Router 使用 clean URL（/login、/projects、/settings 等），
# 浏览器直接访问或刷新时需要服务器返回 index.html 让前端路由处理。
# 此路由必须在所有 API 路由之后注册（API 在 main.py 中已注册）。

@app.get("/{path:path}")
async def spa_catch_all(path: str):
    """所有非 API/非静态路径返回 index.html，由 Vue Router 处理路由。"""
    # 跳过 API 和静态文件路径（由其他路由处理）
    if path.startswith("api/") or path.startswith("assets/") or path.startswith("static/"):
        return {"detail": "Not Found"}
    if _index_path.exists():
        return FileResponse(str(_index_path))
    return {"message": "SPA not found"}


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
