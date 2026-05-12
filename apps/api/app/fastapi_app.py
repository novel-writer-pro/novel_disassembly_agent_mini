from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.routers.loom import router as loom_router
from apps.api.app.routers.writer import router as writer_router
from apps.api.app.routers.quality import router as quality_router
from apps.api.app.routers.library import router as library_router
from apps.api.app.routers.chapters import router as chapters_router
from apps.api.app.routers.risk_review import router as risk_review_router
from apps.api.app.routers.pipeline import router as pipeline_router
from apps.api.app.routers.import_recovery import router as import_recovery_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Novel Analyzer API",
        version="0.3.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(loom_router)
    app.include_router(writer_router)
    app.include_router(quality_router)
    app.include_router(library_router)
    app.include_router(chapters_router)
    app.include_router(risk_review_router)
    app.include_router(pipeline_router)
    app.include_router(import_recovery_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "novel-analyzer-api"}

    return app


app = create_app()
