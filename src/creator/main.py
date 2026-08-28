from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def _request_id(request: Request | None = None) -> UUID:
    if request is None:
        return uuid4()
    try:
        return UUID(request.headers.get("X-Request-ID", ""))
    except ValueError:
        return uuid4()


def _json_response(payload: dict[str, Any], request_id: UUID, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={"X-Request-ID": str(request_id)},
    )


def success_response(data: dict[str, Any], request: Request | None = None) -> JSONResponse:
    request_id = _request_id(request)
    return _json_response(
        {"success": True, "data": data, "meta": {"request_id": str(request_id)}},
        request_id,
        200,
    )


def error_response(
    code: str,
    message: str,
    *,
    status_code: int,
    request: Request | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    return _json_response(
        {
            "success": False,
            "error": {"code": code, "message": message},
            "meta": {"request_id": str(request_id)},
        },
        request_id,
        status_code,
    )


def not_implemented(request: Request) -> JSONResponse:
    return error_response(
        "NOT_IMPLEMENTED",
        "Endpoint reserved by contract.",
        status_code=501,
        request=request,
    )


def create_app() -> FastAPI:
    application = FastAPI(title="Creator API", version="0.1.0")

    @application.get("/health")
    async def health(request: Request) -> JSONResponse:
        return success_response({"status": "ok"}, request)

    @application.get("/health/live")
    async def live_health(request: Request) -> JSONResponse:
        return success_response({"status": "ok"}, request)

    application.add_api_route(
        "/api/v1/content/generate",
        not_implemented,
        methods=["POST"],
    )
    application.add_api_route(
        "/api/v1/images/generate",
        not_implemented,
        methods=["POST"],
    )
    application.add_api_route(
        "/api/v1/images/{id}",
        not_implemented,
        methods=["GET"],
    )
    application.add_api_route(
        "/api/v1/content",
        not_implemented,
        methods=["GET"],
    )
    application.add_api_route(
        "/api/v1/content/{id}",
        not_implemented,
        methods=["DELETE"],
    )
    return application


app = create_app()

__all__ = ["app", "create_app", "error_response", "not_implemented", "success_response"]
