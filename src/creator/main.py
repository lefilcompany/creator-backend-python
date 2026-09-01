from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.responses import JSONResponse

from creator.api.dependencies import (
    get_auth_client,
    get_current_user,
    get_storage_provider,
    get_uow,
)
from creator.api.schemas import AuthLoginRequest, AuthSignupRequest
from creator.application.unit_of_work import UnitOfWork
from creator.domain.auth import AuthSession, AuthSignupResult
from creator.infrastructure.auth import (
    AuthClient,
    AuthConfigurationError,
    AuthInvalidResponseError,
    AuthLoginRejectedError,
    AuthRateLimitedError,
    AuthSignupRejectedError,
    AuthTimeoutError,
    AuthUpstreamError,
)
from creator.repositories import ImageRecord, UserRecord
from creator.services.storage.provider import StorageProvider, StorageUrlError


def _request_id(request: Request | None = None) -> UUID:
    if request is None:
        return uuid4()
    try:
        return UUID(request.headers.get("X-Request-ID", ""))
    except ValueError:
        return uuid4()


def _json_response(
    payload: dict[str, Any],
    request_id: UUID,
    status_code: int,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    response_headers = {"X-Request-ID": str(request_id)}
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers=response_headers,
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
    headers: Mapping[str, str] | None = None,
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
        headers,
    )


def not_implemented(request: Request) -> JSONResponse:
    return error_response(
        "NOT_IMPLEMENTED",
        "Endpoint reserved by contract.",
        status_code=501,
        request=request,
    )


def _auth_session_data(session: AuthSession) -> dict[str, Any]:
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": session.token_type,
        "expires_in": session.expires_in,
        "principal": {
            "subject": session.principal.subject,
            "email": session.principal.email,
            "role": session.principal.role,
        },
        "provider": session.provider,
        "metadata": session.metadata,
    }


def _auth_signup_data(result: AuthSignupResult) -> dict[str, Any]:
    return {
        "principal": {
            "subject": result.principal.subject,
            "email": result.principal.email,
            "role": result.principal.role,
        },
        "session": _auth_session_data(result.session) if result.session else None,
        "confirmation_required": result.confirmation_required,
        "provider": result.provider,
        "metadata": result.metadata,
    }


def _image_data(image: ImageRecord, *, public_url: str | None = None) -> dict[str, Any]:
    return {
        "id": str(image.id),
        "workspace_id": str(image.workspace_id),
        "content_id": str(image.content_id),
        "generation_id": str(image.generation_id),
        "version_number": image.version_number,
        "storage_path": image.storage_path,
        "public_url": public_url or image.public_url,
        "mime_type": image.mime_type,
        "width": image.width,
        "height": image.height,
        "model": image.model,
        "prompt": image.prompt,
        "metadata": image.metadata,
        "created_at": image.created_at.isoformat(),
        "updated_at": image.updated_at.isoformat(),
        "deleted_at": image.deleted_at.isoformat() if image.deleted_at else None,
    }


def create_app() -> FastAPI:
    application = FastAPI(title="Creator API", version="0.1.0")

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code", "HTTP_ERROR"))
            message = str(detail.get("message", "Request failed"))
        else:
            code = "HTTP_ERROR"
            message = str(detail)
        return error_response(
            code,
            message,
            status_code=exc.status_code,
            request=request,
            headers=exc.headers,
        )

    @application.get("/health")
    async def health(request: Request) -> JSONResponse:
        return success_response({"status": "ok"}, request)

    @application.get("/health/live")
    async def live_health(request: Request) -> JSONResponse:
        return success_response({"status": "ok"}, request)

    @application.post("/api/v1/auth/login")
    def login_with_password(
        payload: AuthLoginRequest,
        request: Request,
        auth_client: Annotated[AuthClient, Depends(get_auth_client)],
    ) -> JSONResponse:
        try:
            session = auth_client.sign_in_with_password(
                email=payload.email,
                password=payload.password,
            )
        except AuthConfigurationError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "AUTHENTICATION_MISCONFIGURED",
                    "message": "Authentication is not configured",
                },
            ) from error
        except AuthLoginRejectedError as error:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "LOGIN_REJECTED",
                    "message": "Invalid email or password",
                },
            ) from error
        except AuthRateLimitedError as error:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "AUTH_RATE_LIMITED",
                    "message": "Authentication quota or rate limit exceeded",
                },
            ) from error
        except AuthInvalidResponseError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "AUTH_INVALID_RESPONSE",
                    "message": "Authentication provider returned an invalid response",
                },
            ) from error
        except AuthTimeoutError as error:
            raise HTTPException(
                status_code=504,
                detail={
                    "code": "AUTH_TIMEOUT",
                    "message": "Authentication provider timed out",
                },
            ) from error
        except AuthUpstreamError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "AUTH_UPSTREAM_ERROR",
                    "message": "Authentication provider failed",
                },
            ) from error

        return success_response(_auth_session_data(session), request)

    @application.post("/api/v1/auth/signup")
    def signup_with_password(
        payload: AuthSignupRequest,
        request: Request,
        auth_client: Annotated[AuthClient, Depends(get_auth_client)],
    ) -> JSONResponse:
        try:
            result = auth_client.sign_up_with_password(
                email=payload.email,
                password=payload.password,
            )
        except AuthConfigurationError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "AUTHENTICATION_MISCONFIGURED",
                    "message": "Authentication is not configured",
                },
            ) from error
        except AuthSignupRejectedError as error:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "SIGNUP_REJECTED",
                    "message": "Signup request was rejected",
                },
            ) from error
        except AuthRateLimitedError as error:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "AUTH_RATE_LIMITED",
                    "message": "Authentication quota or rate limit exceeded",
                },
            ) from error
        except AuthInvalidResponseError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "AUTH_INVALID_RESPONSE",
                    "message": "Authentication provider returned an invalid response",
                },
            ) from error
        except AuthTimeoutError as error:
            raise HTTPException(
                status_code=504,
                detail={
                    "code": "AUTH_TIMEOUT",
                    "message": "Authentication provider timed out",
                },
            ) from error
        except AuthUpstreamError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "AUTH_UPSTREAM_ERROR",
                    "message": "Authentication provider failed",
                },
            ) from error

        return success_response(_auth_signup_data(result), request)

    api_dependencies = [Depends(get_current_user)]
    application.add_api_route(
        "/api/v1/content/generate",
        not_implemented,
        methods=["POST"],
        dependencies=api_dependencies,
    )
    application.add_api_route(
        "/api/v1/images/generate",
        not_implemented,
        methods=["POST"],
        dependencies=api_dependencies,
    )

    @application.get("/api/v1/images/{id}")
    def get_image(
        image_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    ) -> JSONResponse:
        image = unit_of_work.image_generations.get_image_for_user(
            user_id=current_user.id,
            image_id=image_id,
        )
        if image is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "IMAGE_NOT_FOUND",
                    "message": "Image not found",
                },
            )
        try:
            public_url = storage.get_url(image.storage_path)
        except StorageUrlError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "STORAGE_URL_UNAVAILABLE",
                    "message": "Stored image URL is unavailable",
                },
            ) from error
        return success_response(_image_data(image, public_url=public_url), request)

    application.add_api_route(
        "/api/v1/content",
        not_implemented,
        methods=["GET"],
        dependencies=api_dependencies,
    )
    application.add_api_route(
        "/api/v1/content/{id}",
        not_implemented,
        methods=["DELETE"],
        dependencies=api_dependencies,
    )
    return application


app = create_app()

__all__ = ["app", "create_app", "error_response", "not_implemented", "success_response"]
