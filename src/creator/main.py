from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from creator.api.schemas import ErrorDetail, ErrorResponse, Meta, SuccessResponse

app = FastAPI(title="Creator API", version="0.1.0", docs_url="/docs", redoc_url="/redoc")


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = UUID(request.headers.get("X-Request-ID", str(uuid4())))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = str(request_id)
    return response


def error_response(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message),
        meta=Meta(request_id=request.state.request_id),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@app.get("/health/live", response_model=SuccessResponse, tags=["health"])
async def live_health(request: Request) -> SuccessResponse:
    return SuccessResponse(data={"status": "ok"}, meta=Meta(request_id=request.state.request_id))


async def not_implemented(request: Request) -> JSONResponse:
    return error_response(
        request,
        "NOT_IMPLEMENTED",
        "Endpoint reserved for the next implementation increment",
        501,
    )


for method, path in [
    ("post", "/api/v1/content/generate"),
    ("post", "/api/v1/images/generate"),
    ("get", "/api/v1/images/{id}"),
    ("get", "/api/v1/content"),
    ("delete", "/api/v1/content/{id}"),
]:
    app.add_api_route(path, not_implemented, methods=[method.upper()], include_in_schema=True)
