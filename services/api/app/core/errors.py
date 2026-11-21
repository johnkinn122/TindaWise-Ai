"""Domain errors and their HTTP mapping.

Services raise these plain exceptions; they never import FastAPI. The handlers in
`register_error_handlers` turn them into one consistent JSON shape:

    {"error": {"code": "...", "message": "...", "fields": {"field": "problem"}}}
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or {}


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class InsufficientStockError(DomainError):
    status_code = 409
    code = "insufficient_stock"


class InvalidInputError(DomainError):
    status_code = 422
    code = "validation_error"


class NotConfiguredError(DomainError):
    status_code = 501
    code = "not_configured"


def _error_body(code: str, message: str, fields: dict[str, str] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "fields": fields or {}}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_error_body(exc.code, exc.message, exc.fields)
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            # loc looks like ("body", "price") or ("query", "limit"); keep the field name.
            loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query")]
            key = ".".join(loc) or "request"
            fields.setdefault(key, err.get("msg", "Invalid value"))
        return JSONResponse(
            status_code=422,
            content=_error_body("validation_error", "Some fields need attention.", fields),
        )
