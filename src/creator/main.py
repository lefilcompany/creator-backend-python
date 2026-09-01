from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from creator.api.dependencies import (
    get_auth_client,
    get_current_user,
    get_generation_queue,
    get_storage_provider,
    get_uow,
)
from creator.api.schemas import AuthLoginRequest, AuthSignupRequest, GenerateImageRequest
from creator.application.image_generation import (
    GenerationQueue,
    IdempotencyConflictError,
    QueueEnqueueError,
    submit_image_generation,
)
from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings, get_settings
from creator.domain.auth import AuthSession, AuthSignupResult
from creator.domain.exceptions import EntityNotFoundError
from creator.domain.generation import GenerationJobStatus
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
from creator.repositories import ImageGenerationStatusRecord, ImageRecord, UserRecord
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


def success_response(
    data: dict[str, Any],
    request: Request | None = None,
    *,
    status_code: int = 200,
) -> JSONResponse:
    request_id = _request_id(request)
    return _json_response(
        {"success": True, "data": data, "meta": {"request_id": str(request_id)}},
        request_id,
        status_code,
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


def _image_generation_status_data(
    status: ImageGenerationStatusRecord,
    *,
    public_url: str | None = None,
) -> dict[str, Any]:
    job = status.job
    return {
        "id": str(job.id),
        "content_id": str(job.content_id),
        "generation_id": str(job.generation_id),
        "status": job.status.value,
        "queued_at": job.queued_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "failed_at": job.failed_at.isoformat() if job.failed_at else None,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "failure_code": job.failure_code,
        "image": _image_data(status.image, public_url=public_url) if status.image else None,
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

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            "VALIDATION_FAILED",
            "Request validation failed",
            status_code=422,
            request=request,
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
    @application.post("/api/v1/images/generate")
    def generate_image(
        payload: GenerateImageRequest,
        request: Request,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
        ],
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        settings: Annotated[Settings, Depends(get_settings)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
    ) -> JSONResponse:
        try:
            status = submit_image_generation(
                unit_of_work=unit_of_work,
                queue=queue,
                settings=settings,
                user=current_user,
                content_id=payload.content_id,
                style=payload.style,
                idempotency_key=idempotency_key,
            )
        except EntityNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"},
            ) from error
        except IdempotencyConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "IDEMPOTENCY_CONFLICT",
                    "message": "Idempotency key was reused with a different request",
                },
            ) from error
        except QueueEnqueueError as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "QUEUE_ENQUEUE_FAILED",
                    "message": "Image generation could not be queued",
                },
            ) from error

        return success_response(_image_generation_status_data(status), request, status_code=202)

    @application.get("/api/v1/images/{id}")
    def get_image(
        job_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    ) -> JSONResponse:
        status = unit_of_work.image_generations.get_status_for_user(
            user_id=current_user.id,
            job_id=job_id,
        )
        if status is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "IMAGE_GENERATION_NOT_FOUND",
                    "message": "Image Generation Job not found",
                },
            )
        public_url = None
        try:
            if status.job.status == GenerationJobStatus.COMPLETED and status.image is not None:
                public_url = storage.get_url(status.image.storage_path)
        except StorageUrlError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "STORAGE_URL_UNAVAILABLE",
                    "message": "Stored image URL is unavailable",
                },
            ) from error
        return success_response(
            _image_generation_status_data(status, public_url=public_url),
            request,
        )

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
