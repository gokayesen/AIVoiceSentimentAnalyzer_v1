from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.errors import UploadValidationError, upload_validation_error_handler
from app.routers.calls import router as calls_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="AI Voice Sentiment Analyzer — web-api", lifespan=lifespan)

app.include_router(calls_router)
app.add_exception_handler(UploadValidationError, upload_validation_error_handler)
