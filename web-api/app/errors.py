"""Structured, rule-specific upload/validation errors (FR-2; Consistency Conventions).

Every rejection returns a machine-readable error_code + a message naming the
specific failed rule + actionable next_step guidance — never a generic
validation failure.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class UploadValidationError(Exception):
    def __init__(
        self, error_code: str, message: str, next_step: str, status_code: int = 422
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.next_step = next_step
        self.status_code = status_code
        super().__init__(message)


def unsupported_format(detail: str) -> UploadValidationError:
    return UploadValidationError(
        error_code="UNSUPPORTED_FORMAT",
        message=f"Unsupported audio format: {detail}. Accepted formats are WAV, MP3, and M4A.",
        next_step="Re-export the recording as WAV, MP3, or M4A and upload again.",
    )


def file_too_large(size_bytes: int, max_bytes: int) -> UploadValidationError:
    max_mb = max_bytes // (1024 * 1024)
    return UploadValidationError(
        error_code="FILE_TOO_LARGE",
        message=(
            f"File size {size_bytes} bytes exceeds the {max_bytes} byte ({max_mb}MB) limit."
        ),
        next_step=f"Trim or compress the recording to under {max_mb}MB and upload again.",
    )


def internal_error(detail: str = "") -> UploadValidationError:
    return UploadValidationError(
        error_code="INTERNAL_ERROR",
        message=f"An unexpected error occurred while processing the upload.{(' ' + detail) if detail else ''}",
        next_step="Please retry. If this persists, contact support.",
        status_code=500,
    )


def duration_exceeded(duration_seconds: float, max_seconds: int) -> UploadValidationError:
    return UploadValidationError(
        error_code="DURATION_EXCEEDED",
        message=(
            f"Audio duration {duration_seconds:.1f}s exceeds the {max_seconds}s "
            "(30 minute) limit."
        ),
        next_step="Trim the recording to under 30 minutes and upload again.",
    )


def undecodable_file(detail: str = "") -> UploadValidationError:
    return UploadValidationError(
        error_code="UNDECODABLE_FILE",
        message=f"File could not be decoded as valid audio.{(' ' + detail) if detail else ''}",
        next_step="Confirm the file is not corrupt and re-export it, then upload again.",
    )


def call_not_found(call_id: str) -> UploadValidationError:
    return UploadValidationError(
        error_code="CALL_NOT_FOUND",
        message=f"No Call found with id {call_id}.",
        next_step="Verify the Call id and try again.",
        status_code=404,
    )


def call_not_complete(
    call_id: str, status: str, resource: str = "This data"
) -> UploadValidationError:
    return UploadValidationError(
        error_code="CALL_NOT_COMPLETE",
        message=f"Call {call_id} is currently '{status}'. {resource} is only "
        "available once the Call reaches 'complete'.",
        next_step="Poll the Call's status and retry once it reaches 'complete'.",
        status_code=409,
    )


def call_deletion_in_progress(call_id: str) -> UploadValidationError:
    """Story 1.10 (AD-12): the Call's in-flight job did not finish within the
    bounded await window (DELETE_AWAIT_TIMEOUT_SECONDS) — nothing was
    deleted, deliberately, since a live job may still be writing."""
    return UploadValidationError(
        error_code="CALL_DELETION_IN_PROGRESS",
        message=f"Call {call_id} is still being processed and could not be safely "
        "deleted within the wait window.",
        next_step="Retry the delete request shortly, once processing has finished.",
        status_code=409,
    )


async def upload_validation_error_handler(
    request: Request, exc: UploadValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "next_step": exc.next_step,
        },
    )
