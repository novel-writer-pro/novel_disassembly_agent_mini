from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.app.routers.meta import router as meta_router
from apps.api.app.routers.whole_book_imitation import router as whole_book_imitation_router
from apps.api.app.routers.reader import router as reader_router
from apps.api.app.routers.loom import router as loom_router
from apps.api.app.routers.writer import router as writer_router
from apps.api.app.routers.quality import router as quality_router
from apps.api.app.routers.library import router as library_router
from apps.api.app.routers.chapters import router as chapters_router
from apps.api.app.routers.risk_review import router as risk_review_router
from apps.api.app.routers.pipeline import router as pipeline_router
from apps.api.app.routers.import_recovery import router as import_recovery_router
from apps.api.app.routers.whole_book import router as whole_book_router
from apps.api.app.routers.steering_character import router as steering_character_router


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

    @app.exception_handler(RequestValidationError)
    async def _validation_to_400(request: Request, exc: RequestValidationError):
        """Match WSGI behaviour: missing/invalid query/body params -> 400 + {'error': ...}.

        WSGI canonical responses use {'error': 'missing query parameter: foo'}
        for missing required fields. We mirror that on the FastAPI surface so
        v5 cutover is schema-equivalent for clients.
        """
        errs = exc.errors()
        first = errs[0] if errs else {}
        loc = first.get("loc") or []
        kind = first.get("type") or "validation_error"

        if kind == "missing":
            param = loc[-1] if loc else "unknown"
            section = "query" if (len(loc) >= 1 and loc[0] == "query") else (
                "body" if (len(loc) >= 1 and loc[0] == "body") else "request"
            )
            if section == "query":
                msg = f"missing query parameter: {param}"
            elif section == "body":
                msg = f"missing field: {param}" if param != "body" else "request body required"
            else:
                msg = f"missing parameter: {param}"
        else:
            param = loc[-1] if loc else "?"
            msg = f"invalid parameter: {param}"

        return JSONResponse(status_code=400, content={"error": msg})

    app.include_router(meta_router)
    app.include_router(whole_book_imitation_router)
    app.include_router(reader_router)
    app.include_router(loom_router)
    app.include_router(writer_router)
    app.include_router(quality_router)
    app.include_router(library_router)
    app.include_router(chapters_router)
    app.include_router(risk_review_router)
    app.include_router(pipeline_router)
    app.include_router(import_recovery_router)
    app.include_router(whole_book_router)
    app.include_router(steering_character_router)

    return app


app = create_app()
