"""DevTeam -- FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from devteam.api.projects import router as projects_router
from devteam.api.auth import router as auth_router
from devteam.api.websocket import router as ws_router
from devteam.api.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    # Startup: initialize memory database (already done in __init__)
    from devteam.utils.memory import get_memory
    mem = get_memory()

    yield

    # Shutdown: close database connections
    mem.close()
    import gc
    gc.collect()


app = FastAPI(title="DevTeam", lifespan=lifespan)

app.include_router(projects_router)
app.include_router(auth_router)
app.include_router(ws_router)
app.include_router(settings_router)


@app.get("/health")
def health():
    return {"status": "ok"}
