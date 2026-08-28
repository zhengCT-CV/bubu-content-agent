from __future__ import annotations

from typing import Any


class BubuError(Exception):
    code = "BUBU_ERROR"

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotFoundError(BubuError):
    code = "NOT_FOUND"


class ConflictError(BubuError):
    code = "CONFLICT"


class ApprovalRequiredError(BubuError):
    code = "APPROVAL_REQUIRED"


class ExternalServiceError(BubuError):
    code = "EXTERNAL_SERVICE_ERROR"


class UnsafeWritebackError(BubuError):
    code = "UNSAFE_WRITEBACK"
