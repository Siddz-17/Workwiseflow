import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import chat, documents, meetings, records, workspaces
from .services.embeddings import get_embedder
from .services.llm import get_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().auto_create_tables:
        init_db()
    yield


app = FastAPI(title="WorkflowWise API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip().rstrip("/") for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_origin_regex=get_settings().cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (workspaces, documents, meetings, chat, records):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    s = get_settings()
    return {
        "ok": True,
        "auth": s.auth_mode,
        "llm": get_provider().name,
        "embeddings": get_embedder().name,
        "storage": s.storage_backend,
        "queue": "rq" if s.redis_url else "in-process",
    }
