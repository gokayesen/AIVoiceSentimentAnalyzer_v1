from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.errors import UploadValidationError, upload_validation_error_handler
from app.routers.calls import router as calls_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="AI Voice Sentiment Analyzer — web-api", lifespan=lifespan)

# Story 2.2: the frontend (Docker-served on :3000, Vite dev server on :5173)
# calls this API cross-origin. No auth/cookies exist in this product (PRD
# §2.3), so allow_credentials stays False — nothing credential-bearing to
# allow, and there is no reason to widen the allow_origins contract for it.
# Both the `localhost` and `127.0.0.1` forms are listed (code review,
# 2026-08-15) since browsers treat them as distinct origins even though they
# resolve to the same machine — a developer/teammate reaching either service
# via the numeric form would otherwise hit a silent CORS block.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(calls_router)
app.add_exception_handler(UploadValidationError, upload_validation_error_handler)
