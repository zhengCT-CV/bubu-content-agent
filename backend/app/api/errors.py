from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import BubuError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(BubuError)
    async def bubu_error_handler(request: Request, exc: BubuError) -> JSONResponse:
        status = 404 if exc.code == "NOT_FOUND" else 409 if exc.code == "CONFLICT" else 400
        return JSONResponse(
            status_code=status,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "request_id": request.headers.get("x-request-id", str(uuid4())),
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": str(exc),
                "detail": {},
                "request_id": request.headers.get("x-request-id", str(uuid4())),
            },
        )
