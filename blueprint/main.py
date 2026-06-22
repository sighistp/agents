"""Blueprint — FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from blueprint.api.projects import router as projects_router
from blueprint.api.auth import router as auth_router
from blueprint.api.websocket import router as ws_router
from blueprint.api.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    from blueprint.utils.memory import get_memory
    mem = get_memory()
    yield
    mem.close()
    import gc
    gc.collect()


app = FastAPI(title="Blueprint", lifespan=lifespan)

# CORS middleware — origins read from config (default: localhost only)
from blueprint.config import settings as _cfg
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(auth_router)
app.include_router(ws_router)
app.include_router(settings_router)


@app.get("/health")
def health():
    return {"status": "ok"}
