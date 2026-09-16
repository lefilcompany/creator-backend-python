from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

from creator.api.dependencies import (
    enforce_rate_limit,
    get_auth_client,
    get_current_user,
    get_generation_queue,
    get_llm_provider,
    get_metrics_registry,
    get_storage_provider,
    get_uow,
)
from creator.api.schemas import (
    AssetCreateRequest,
    AssetUpdateRequest,
    AuthLoginRequest,
    AuthSignupRequest,
    BrandCreateRequest,
    BrandSettingsUpdateRequest,
    BrandSettingsUpsertRequest,
    BrandUpdateRequest,
    ContentCreateRequest,
    ContentUpdateRequest,
    GenerateContentRequest,
    GenerateImageRequest,
    GenerationCreateRequest,
    GenerationUpdateRequest,
    ImproveContentRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    RegenerateImageRequest,
    SettingsUpdateRequest,
    UserCreateRequest,
    UserUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
)
from creator.application.content_generation import (
    ContentGenerationPersistenceError,
    GenerateContentCommand,
    WorkspaceAccessDeniedError,
    generate_content,
)
from creator.application.content_improvement import (
    ContentImprovementInvalidResponseError,
    ImproveContentCommand,
    ImprovedContentPreview,
    improve_content,
)
from creator.application.image_generation import (
    GenerationQueue,
    IdempotencyConflictError,
    QueueEnqueueError,
    submit_image_generation,
    submit_image_regeneration,
)
from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings, get_settings
from creator.domain.auth import AuthSession, AuthSignupResult, Principal
from creator.domain.exceptions import EntityNotFoundError, PersistenceError
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
from creator.infrastructure.metrics import MetricsRegistry
from creator.integrations.gemini.exceptions import (
    GeminiAuthenticationError,
    GeminiBlockedContentError,
    GeminiInvalidResponseError,
    GeminiProviderError,
    GeminiQuotaError,
    GeminiTimeoutError,
    GeminiTransientError,
)
from creator.repositories import (
    AssetRecord,
    BrandRecord,
    BrandSettingsRecord,
    ContentDetailRecord,
    ContentFilters,
    ContentRecord,
    GenerationRecord,
    ImageGenerationStatusRecord,
    ImageRecord,
    Page,
    ProjectRecord,
    SettingsRecord,
    UserRecord,
    WorkspaceMembershipRecord,
    WorkspaceRecord,
)
from creator.repositories.common import PageRequest
from creator.services.ai.provider import LLMProvider, ProviderNotConfiguredError
from creator.services.storage.provider import StorageProvider, StorageUrlError

OPENAPI_TAGS = [
    {"name": "System", "description": "Health, liveness and operational endpoints."},
    {"name": "Auth", "description": "Authentication and signup endpoints."},
    {"name": "Users", "description": "User profile and administration endpoints."},
    {"name": "Settings", "description": "Authenticated Principal settings endpoints."},
    {"name": "Workspaces", "description": "Workspace lifecycle endpoints."},
    {"name": "Brands", "description": "Brand and Brand Settings endpoints."},
    {"name": "Projects", "description": "Project endpoints."},
    {"name": "Contents", "description": "Content CRUD and content workflow endpoints."},
    {"name": "Generations", "description": "Generation lifecycle endpoints."},
    {"name": "Assets", "description": "Asset metadata endpoints."},
    {"name": "Images", "description": "Image generation and retrieval endpoints."},
]


def _request_id(request: Request | None = None) -> UUID:
    if request is None:
        return uuid4()
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, UUID):
        return existing
    try:
        request_id = UUID(request.headers.get("X-Request-ID", ""))
    except ValueError:
        request_id = uuid4()
    request.state.request_id = request_id
    return request_id


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


def _workspace_data(workspace: WorkspaceRecord) -> dict[str, Any]:
    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "created_at": workspace.created_at.isoformat(),
        "updated_at": workspace.updated_at.isoformat(),
        "deleted_at": workspace.deleted_at.isoformat() if workspace.deleted_at else None,
    }


def _workspace_membership_data(membership: WorkspaceMembershipRecord) -> dict[str, Any]:
    return {
        "id": str(membership.id),
        "workspace_id": str(membership.workspace_id),
        "user_id": str(membership.user_id),
        "role": membership.role,
        "created_at": membership.created_at.isoformat(),
        "updated_at": membership.updated_at.isoformat(),
        "deleted_at": membership.deleted_at.isoformat() if membership.deleted_at else None,
    }


def _auth_signup_data(
    result: AuthSignupResult,
    *,
    workspace: WorkspaceRecord,
    membership: WorkspaceMembershipRecord,
) -> dict[str, Any]:
    return {
        "principal": {
            "subject": result.principal.subject,
            "email": result.principal.email,
            "role": result.principal.role,
        },
        "session": _auth_session_data(result.session) if result.session else None,
        "workspace": _workspace_data(workspace),
        "membership": _workspace_membership_data(membership),
        "confirmation_required": result.confirmation_required,
        "provider": result.provider,
        "metadata": result.metadata,
    }


def _bootstrap_signup_workspace(
    *,
    unit_of_work: UnitOfWork,
    principal: Principal,
    workspace_name: str,
) -> tuple[UserRecord, WorkspaceRecord, WorkspaceMembershipRecord]:
    existing = unit_of_work.users.get_by_external_id(principal.subject, include_deleted=True)
    if existing is not None and existing.deleted_at is not None:
        raise EntityNotFoundError("User not found")
    user = existing or unit_of_work.users.add(
        external_id=principal.subject,
        email=principal.email,
        display_name=None,
    )
    created = unit_of_work.workspaces.create_for_user(
        user_id=user.id,
        name=workspace_name,
    )
    unit_of_work.commit()
    return user, created.workspace, created.membership


def _user_data(user: UserRecord) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "external_id": user.external_id,
        "email": user.email,
        "display_name": user.display_name,
        "global_role": user.global_role,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
    }


def _settings_data(settings: SettingsRecord) -> dict[str, Any]:
    return {
        "id": str(settings.id),
        "user_id": str(settings.user_id),
        "brand_name": settings.brand_name,
        "segment": settings.segment,
        "tone": settings.tone,
        "voice": settings.voice,
        "visual_style": settings.visual_style,
        "default_preferences": settings.default_preferences,
        "created_at": settings.created_at.isoformat(),
        "updated_at": settings.updated_at.isoformat(),
    }


def _brand_data(brand: BrandRecord) -> dict[str, Any]:
    return {
        "id": str(brand.id),
        "workspace_id": str(brand.workspace_id),
        "created_by_user_id": str(brand.created_by_user_id) if brand.created_by_user_id else None,
        "name": brand.name,
        "description": brand.description,
        "brand_voice": brand.brand_voice,
        "metadata": brand.metadata,
        "created_at": brand.created_at.isoformat(),
        "updated_at": brand.updated_at.isoformat(),
        "deleted_at": brand.deleted_at.isoformat() if brand.deleted_at else None,
    }


def _project_data(project: ProjectRecord) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "brand_id": str(project.brand_id) if project.brand_id else None,
        "created_by_user_id": str(project.created_by_user_id)
        if project.created_by_user_id
        else None,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "metadata": project.metadata,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "deleted_at": project.deleted_at.isoformat() if project.deleted_at else None,
    }


def _content_data(
    content: ContentRecord,
    *,
    generation_id: UUID | None = None,
    generation_model: str | None = None,
    generation_parameters: dict[str, object] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(content.id),
        "workspace_id": str(content.workspace_id),
        "brand_id": str(content.brand_id) if content.brand_id else None,
        "project_id": str(content.project_id) if content.project_id else None,
        "created_by_user_id": str(content.created_by_user_id)
        if content.created_by_user_id
        else None,
        "type": content.content_type,
        "title": content.title,
        "payload": content.payload,
        "created_at": content.created_at.isoformat(),
        "updated_at": content.updated_at.isoformat(),
        "deleted_at": content.deleted_at.isoformat() if content.deleted_at else None,
    }
    if generation_id is not None:
        data["generation"] = {
            "id": str(generation_id),
            "model": generation_model,
            "parameters": generation_parameters or {},
        }
    return data


def _page_data(page: Page[Any], serializer: Any) -> dict[str, Any]:
    return {
        "items": [serializer(item) for item in page.items],
        "pagination": {
            "page": page.page,
            "limit": page.limit,
            "total": page.total,
        },
    }


def _content_page_data(page: Page[ContentRecord]) -> dict[str, Any]:
    return _page_data(page, _content_data)


def _content_detail_data(detail: ContentDetailRecord) -> dict[str, Any]:
    data = _content_data(detail.content)
    data["images"] = [_image_data(image) for image in detail.images]
    return data


def _improved_content_data(preview: ImprovedContentPreview) -> dict[str, Any]:
    return {
        "text": preview.text,
        "justification": preview.justification,
        "original_text": preview.original_text,
        "objective": preview.objective,
        "persistence": preview.persistence,
        "content_id": str(preview.content_id) if preview.content_id else None,
        "prompt_template": preview.prompt_template,
    }


def _generation_data(generation: GenerationRecord) -> dict[str, Any]:
    return {
        "id": str(generation.id),
        "workspace_id": str(generation.workspace_id),
        "content_id": str(generation.content_id),
        "brand_id": str(generation.brand_id) if generation.brand_id else None,
        "project_id": str(generation.project_id) if generation.project_id else None,
        "requested_by_user_id": str(generation.requested_by_user_id)
        if generation.requested_by_user_id
        else None,
        "type": generation.generation_type,
        "model": generation.model,
        "prompt": generation.prompt,
        "parameters": generation.parameters,
        "created_at": generation.created_at.isoformat(),
        "updated_at": generation.updated_at.isoformat(),
        "deleted_at": generation.deleted_at.isoformat() if generation.deleted_at else None,
    }


def _asset_data(asset: AssetRecord) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "workspace_id": str(asset.workspace_id),
        "brand_id": str(asset.brand_id) if asset.brand_id else None,
        "project_id": str(asset.project_id) if asset.project_id else None,
        "content_id": str(asset.content_id) if asset.content_id else None,
        "uploaded_by_user_id": str(asset.uploaded_by_user_id)
        if asset.uploaded_by_user_id
        else None,
        "asset_type": asset.asset_type,
        "storage_path": asset.storage_path,
        "public_url": asset.public_url,
        "mime_type": asset.mime_type,
        "byte_size": asset.byte_size,
        "checksum": asset.checksum,
        "metadata": asset.metadata,
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
        "deleted_at": asset.deleted_at.isoformat() if asset.deleted_at else None,
    }


def _brand_settings_data(settings: BrandSettingsRecord) -> dict[str, Any]:
    return {
        "id": str(settings.id),
        "workspace_id": str(settings.workspace_id),
        "brand_id": str(settings.brand_id),
        "voice_settings": settings.voice_settings,
        "visual_settings": settings.visual_settings,
        "generation_defaults": settings.generation_defaults,
        "metadata": settings.metadata,
        "created_at": settings.created_at.isoformat(),
        "updated_at": settings.updated_at.isoformat(),
        "deleted_at": settings.deleted_at.isoformat() if settings.deleted_at else None,
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


def _page_request(page: int, limit: int, sort: str) -> PageRequest:
    return PageRequest(page=page, limit=limit, sort="asc" if sort == "created_at" else "desc")


def _require_admin(user: UserRecord) -> None:
    if user.global_role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_REQUIRED", "message": "Administrator role is required"},
        )


def _require_workspace_write(
    unit_of_work: UnitOfWork,
    *,
    user_id: UUID,
    workspace_id: UUID,
) -> None:
    if not unit_of_work.workspaces.user_has_workspace_role(
        user_id=user_id,
        workspace_id=workspace_id,
        minimum_role="editor",
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "WORKSPACE_ACCESS_DENIED",
                "message": "Workspace is not writable by the authenticated user",
            },
        )


def _not_found(entity: str) -> HTTPException:
    code = entity.upper().replace(" ", "_")
    return HTTPException(
        status_code=404,
        detail={"code": f"{code}_NOT_FOUND", "message": f"{entity} not found"},
    )


def _install_rate_limit_openapi(application: FastAPI) -> None:
    original_openapi = application.openapi

    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema:
            return application.openapi_schema

        schema = original_openapi()
        components = schema.setdefault("components", {})
        schemas = components.setdefault("schemas", {})
        schemas.setdefault(
            "ErrorResponse",
            {
                "type": "object",
                "required": ["success", "error", "meta"],
                "properties": {
                    "success": {"const": False},
                    "error": {
                        "type": "object",
                        "required": ["code", "message"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    },
                    "meta": {
                        "type": "object",
                        "required": ["request_id"],
                        "properties": {"request_id": {"type": "string", "format": "uuid"}},
                    },
                },
            },
        )
        responses = components.setdefault("responses", {})
        responses.setdefault(
            "RateLimitExceeded",
            {
                "description": "The caller exceeded the configured per-endpoint rate limit.",
                "headers": {
                    "Retry-After": {"schema": {"type": "integer", "minimum": 1}},
                    "RateLimit-Limit": {"schema": {"type": "integer", "minimum": 1}},
                    "RateLimit-Remaining": {"schema": {"type": "integer", "minimum": 0}},
                    "RateLimit-Reset": {"schema": {"type": "integer", "minimum": 1}},
                },
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
                },
            },
        )
        responses.setdefault(
            "RateLimiterUnavailable",
            {
                "description": "The distributed rate limiter is unavailable.",
                "headers": {"Retry-After": {"schema": {"type": "integer", "minimum": 1}}},
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
                },
            },
        )

        generation_paths = {
            "/api/v1/content/generate",
            "/api/v1/content/improve",
            "/api/v1/images/generate",
            "/api/v1/images/{id}/regenerate",
        }
        for path, path_item in schema.get("paths", {}).items():
            if not path.startswith("/api/v1/"):
                continue
            for operation in path_item.values():
                if not isinstance(operation, dict) or "responses" not in operation:
                    continue
                operation["responses"].setdefault(
                    "429",
                    {"$ref": "#/components/responses/RateLimitExceeded"},
                )
                if path in generation_paths:
                    operation["responses"].setdefault(
                        "503", {"$ref": "#/components/responses/RateLimiterUnavailable"}
                    )

        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi  # type: ignore[method-assign]


def create_app() -> FastAPI:
    application = FastAPI(
        title="Creator API",
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        dependencies=[Depends(enforce_rate_limit)],
    )
    _install_rate_limit_openapi(application)

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

    @application.get("/health", tags=["System"])
    async def health(request: Request) -> JSONResponse:
        return success_response({"status": "ok"}, request)

    @application.get("/health/live", tags=["System"])
    async def live_health(request: Request) -> JSONResponse:
        return success_response({"status": "ok"}, request)

    @application.get("/metrics", include_in_schema=True, tags=["System"])
    def metrics(
        registry: Annotated[MetricsRegistry, Depends(get_metrics_registry)],
    ) -> PlainTextResponse:
        # Keep this endpoint outside /api/v1 so observability cannot consume user quota.
        return PlainTextResponse(registry.render(), media_type=registry.content_type)

    @application.post("/api/v1/auth/login", tags=["Auth"])
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

    @application.post("/api/v1/auth/signup", tags=["Auth"])
    def signup_with_password(
        payload: AuthSignupRequest,
        request: Request,
        auth_client: Annotated[AuthClient, Depends(get_auth_client)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
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
                    "message": error.provider_message or "Signup request was rejected",
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

        try:
            _, workspace, membership = _bootstrap_signup_workspace(
                unit_of_work=unit_of_work,
                principal=result.principal,
                workspace_name=payload.workspace.name,
            )
        except PersistenceError as error:
            unit_of_work.rollback()
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "SIGNUP_BOOTSTRAP_FAILED",
                    "message": "Signup Workspace could not be created",
                },
            ) from error

        return success_response(
            _auth_signup_data(result, workspace=workspace, membership=membership),
            request,
        )

    @application.get("/api/v1/users/me", tags=["Users"])
    def get_my_profile(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
    ) -> JSONResponse:
        return success_response(_user_data(current_user), request)

    @application.get("/api/v1/settings", tags=["Settings"])
    def get_my_settings(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        settings = unit_of_work.settings.get_or_create_for_user(current_user.id)
        unit_of_work.commit()
        return success_response(_settings_data(settings), request)

    @application.patch("/api/v1/settings", tags=["Settings"])
    def update_my_settings(
        payload: SettingsUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        unit_of_work.settings.get_or_create_for_user(current_user.id)
        changes = payload.model_dump(exclude_unset=True)
        settings = unit_of_work.settings.update_partial(current_user.id, changes)
        unit_of_work.commit()
        return success_response(_settings_data(settings), request)

    @application.get("/api/v1/users", tags=["Users"])
    def list_users(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        _require_admin(current_user)
        users = unit_of_work.users.list(page=_page_request(page, limit, sort))
        return success_response(_page_data(users, _user_data), request)

    @application.post("/api/v1/users", tags=["Users"])
    def create_user(
        payload: UserCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_admin(current_user)
        user = unit_of_work.users.add(
            external_id=payload.external_id,
            email=payload.email,
            display_name=payload.display_name,
            global_role=payload.global_role,
        )
        unit_of_work.commit()
        return success_response(_user_data(user), request, status_code=201)

    @application.get("/api/v1/users/{id}", tags=["Users"])
    def get_user(
        user_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_admin(current_user)
        user = unit_of_work.users.get_by_id(user_id)
        if user is None:
            raise _not_found("User")
        return success_response(_user_data(user), request)

    @application.put("/api/v1/users/{id}", tags=["Users"])
    def update_user(
        user_id: Annotated[UUID, Path(alias="id")],
        payload: UserUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_admin(current_user)
        try:
            user = unit_of_work.users.update(
                user_id,
                email=payload.email,
                display_name=payload.display_name,
                global_role=payload.global_role,
            )
        except EntityNotFoundError as error:
            raise _not_found("User") from error
        unit_of_work.commit()
        return success_response(_user_data(user), request)

    @application.delete("/api/v1/users/{id}", tags=["Users"])
    def delete_user(
        user_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_admin(current_user)
        try:
            unit_of_work.users.soft_delete(user_id)
        except EntityNotFoundError as error:
            raise _not_found("User") from error
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/workspaces", tags=["Workspaces"])
    def list_workspaces(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        workspaces = unit_of_work.workspaces.list_for_user(
            user_id=current_user.id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(workspaces, _workspace_data), request)

    @application.post("/api/v1/workspaces", tags=["Workspaces"])
    def create_workspace(
        payload: WorkspaceCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        created = unit_of_work.workspaces.create_for_user(
            user_id=current_user.id,
            name=payload.name,
        )
        unit_of_work.commit()
        return success_response(
            {
                "workspace": _workspace_data(created.workspace),
                "membership": _workspace_membership_data(created.membership),
            },
            request,
            status_code=201,
        )

    @application.get("/api/v1/workspaces/{id}", tags=["Workspaces"])
    def get_workspace(
        workspace_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        workspace = unit_of_work.workspaces.get_for_user(
            user_id=current_user.id,
            workspace_id=workspace_id,
        )
        if workspace is None:
            raise _not_found("Workspace")
        return success_response(_workspace_data(workspace), request)

    @application.put("/api/v1/workspaces/{id}", tags=["Workspaces"])
    def update_workspace(
        workspace_id: Annotated[UUID, Path(alias="id")],
        payload: WorkspaceUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            workspace = unit_of_work.workspaces.update(
                user_id=current_user.id,
                workspace_id=workspace_id,
                name=payload.name,
            )
        except EntityNotFoundError as error:
            raise _not_found("Workspace") from error
        unit_of_work.commit()
        return success_response(_workspace_data(workspace), request)

    @application.delete("/api/v1/workspaces/{id}", tags=["Workspaces"])
    def delete_workspace(
        workspace_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            workspace = unit_of_work.workspaces.soft_delete_for_user(
                user_id=current_user.id,
                workspace_id=workspace_id,
            )
        except EntityNotFoundError as error:
            raise _not_found("Workspace") from error
        unit_of_work.commit()
        return success_response({"workspace": _workspace_data(workspace)}, request)

    @application.get("/api/v1/brands", tags=["Brands"])
    def list_brands(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        brands = unit_of_work.brands.list_for_user(
            user_id=current_user.id,
            workspace_id=workspace_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(brands, _brand_data), request)

    @application.post("/api/v1/brands", tags=["Brands"])
    def create_brand(
        payload: BrandCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        brand = unit_of_work.brands.add(
            workspace_id=payload.workspace_id,
            created_by_user_id=current_user.id,
            name=payload.name,
            description=payload.description,
            brand_voice=payload.brand_voice,
            metadata=payload.metadata,
        )
        unit_of_work.commit()
        return success_response(_brand_data(brand), request, status_code=201)

    @application.get("/api/v1/brands/{id}", tags=["Brands"])
    def get_brand(
        brand_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        brand = unit_of_work.brands.get_for_user(user_id=current_user.id, brand_id=brand_id)
        if brand is None:
            raise _not_found("Brand")
        return success_response(_brand_data(brand), request)

    @application.put("/api/v1/brands/{id}", tags=["Brands"])
    def update_brand(
        brand_id: Annotated[UUID, Path(alias="id")],
        payload: BrandUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            brand = unit_of_work.brands.update(
                user_id=current_user.id,
                brand_id=brand_id,
                name=payload.name,
                description=payload.description,
                brand_voice=payload.brand_voice,
                metadata=payload.metadata,
            )
        except EntityNotFoundError as error:
            raise _not_found("Brand") from error
        unit_of_work.commit()
        return success_response(_brand_data(brand), request)

    @application.delete("/api/v1/brands/{id}", tags=["Brands"])
    def delete_brand(
        brand_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            unit_of_work.brands.soft_delete(user_id=current_user.id, brand_id=brand_id)
        except EntityNotFoundError as error:
            raise _not_found("Brand") from error
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/brands/{id}/settings", tags=["Brands"])
    def get_brand_settings(
        brand_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        settings = unit_of_work.brand_settings.get_for_user(
            user_id=current_user.id,
            brand_id=brand_id,
        )
        if settings is None:
            raise _not_found("Brand settings")
        return success_response(_brand_settings_data(settings), request)

    @application.put("/api/v1/brands/{id}/settings", tags=["Brands"])
    def upsert_brand_settings(
        brand_id: Annotated[UUID, Path(alias="id")],
        payload: BrandSettingsUpsertRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        settings = unit_of_work.brand_settings.upsert(
            user_id=current_user.id,
            workspace_id=payload.workspace_id,
            brand_id=brand_id,
            voice_settings=payload.voice_settings,
            visual_settings=payload.visual_settings,
            generation_defaults=payload.generation_defaults,
            metadata=payload.metadata,
        )
        unit_of_work.commit()
        return success_response(_brand_settings_data(settings), request)

    @application.patch("/api/v1/brands/{id}/settings", tags=["Brands"])
    def update_brand_settings(
        brand_id: Annotated[UUID, Path(alias="id")],
        payload: BrandSettingsUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            settings = unit_of_work.brand_settings.update(
                user_id=current_user.id,
                brand_id=brand_id,
                voice_settings=payload.voice_settings,
                visual_settings=payload.visual_settings,
                generation_defaults=payload.generation_defaults,
                metadata=payload.metadata,
            )
        except EntityNotFoundError as error:
            raise _not_found("Brand settings") from error
        unit_of_work.commit()
        return success_response(_brand_settings_data(settings), request)

    @application.delete("/api/v1/brands/{id}/settings", tags=["Brands"])
    def delete_brand_settings(
        brand_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            unit_of_work.brand_settings.soft_delete(user_id=current_user.id, brand_id=brand_id)
        except EntityNotFoundError as error:
            raise _not_found("Brand settings") from error
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/projects", tags=["Projects"])
    def list_projects(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
        brand_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        projects = unit_of_work.projects.list_for_user(
            user_id=current_user.id,
            workspace_id=workspace_id,
            brand_id=brand_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(projects, _project_data), request)

    @application.post("/api/v1/projects", tags=["Projects"])
    def create_project(
        payload: ProjectCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        project = unit_of_work.projects.add(
            workspace_id=payload.workspace_id,
            brand_id=payload.brand_id,
            created_by_user_id=current_user.id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            metadata=payload.metadata,
        )
        unit_of_work.commit()
        return success_response(_project_data(project), request, status_code=201)

    @application.get("/api/v1/projects/{id}", tags=["Projects"])
    def get_project(
        project_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        project = unit_of_work.projects.get_for_user(
            user_id=current_user.id,
            project_id=project_id,
        )
        if project is None:
            raise _not_found("Project")
        return success_response(_project_data(project), request)

    @application.put("/api/v1/projects/{id}", tags=["Projects"])
    def update_project(
        project_id: Annotated[UUID, Path(alias="id")],
        payload: ProjectUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            project = unit_of_work.projects.update(
                user_id=current_user.id,
                project_id=project_id,
                name=payload.name,
                description=payload.description,
                status=payload.status,
                metadata=payload.metadata,
            )
        except EntityNotFoundError as error:
            raise _not_found("Project") from error
        unit_of_work.commit()
        return success_response(_project_data(project), request)

    @application.delete("/api/v1/projects/{id}", tags=["Projects"])
    def delete_project(
        project_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            unit_of_work.projects.soft_delete(user_id=current_user.id, project_id=project_id)
        except EntityNotFoundError as error:
            raise _not_found("Project") from error
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.post("/api/v1/contents", tags=["Contents"])
    def create_content(
        payload: ContentCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        content = unit_of_work.contents.add(
            workspace_id=payload.workspace_id,
            created_by_user_id=current_user.id,
            content_type=payload.type,
            brand_id=payload.brand_id,
            project_id=payload.project_id,
            title=payload.title,
            payload=payload.payload,
        )
        unit_of_work.commit()
        return success_response(_content_data(content), request, status_code=201)

    @application.get("/api/v1/contents/{id}", tags=["Contents"])
    @application.get("/api/v1/content/{id}", tags=["Contents"])
    def get_content(
        content_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        detail = unit_of_work.contents.get_detail_by_id_for_user(
            user_id=current_user.id,
            content_id=content_id,
        )
        if detail is None:
            raise _not_found("Content")
        return success_response(_content_detail_data(detail), request)

    @application.put("/api/v1/contents/{id}", tags=["Contents"])
    def update_content(
        content_id: Annotated[UUID, Path(alias="id")],
        payload: ContentUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.contents.get_by_id_for_user(
            user_id=current_user.id,
            content_id=content_id,
        )
        if existing is None:
            raise _not_found("Content")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        try:
            content = unit_of_work.contents.update(
                content_id,
                brand_id=payload.brand_id,
                project_id=payload.project_id,
                title=payload.title,
                payload=payload.payload,
            )
        except EntityNotFoundError as error:
            raise _not_found("Content") from error
        unit_of_work.commit()
        return success_response(_content_data(content), request)

    @application.delete("/api/v1/contents/{id}", tags=["Contents"])
    @application.delete("/api/v1/content/{id}", tags=["Contents"])
    def delete_content(
        content_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.contents.get_by_id_for_user(
            user_id=current_user.id,
            content_id=content_id,
            include_deleted=True,
        )
        if existing is None:
            raise _not_found("Content")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        try:
            unit_of_work.contents.soft_delete(content_id)
        except EntityNotFoundError as error:
            raise _not_found("Content") from error
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/generations", tags=["Generations"])
    def list_generations(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
        content_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        generations = unit_of_work.generations.list_for_user(
            user_id=current_user.id,
            workspace_id=workspace_id,
            content_id=content_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(generations, _generation_data), request)

    @application.post("/api/v1/generations", tags=["Generations"])
    def create_generation(
        payload: GenerationCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        generation = unit_of_work.generations.add(
            workspace_id=payload.workspace_id,
            content_id=payload.content_id,
            requested_by_user_id=current_user.id,
            generation_type=payload.type,
            brand_id=payload.brand_id,
            project_id=payload.project_id,
            model=payload.model,
            prompt=payload.prompt,
            parameters=payload.parameters,
        )
        unit_of_work.commit()
        return success_response(_generation_data(generation), request, status_code=201)

    @application.get("/api/v1/generations/{id}", tags=["Generations"])
    def get_generation(
        generation_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        generation = unit_of_work.generations.get_for_user(
            user_id=current_user.id,
            generation_id=generation_id,
        )
        if generation is None:
            raise _not_found("Generation")
        return success_response(_generation_data(generation), request)

    @application.put("/api/v1/generations/{id}", tags=["Generations"])
    def update_generation(
        generation_id: Annotated[UUID, Path(alias="id")],
        payload: GenerationUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            generation = unit_of_work.generations.update(
                user_id=current_user.id,
                generation_id=generation_id,
                model=payload.model,
                prompt=payload.prompt,
                parameters=payload.parameters,
            )
        except EntityNotFoundError as error:
            raise _not_found("Generation") from error
        unit_of_work.commit()
        return success_response(_generation_data(generation), request)

    @application.delete("/api/v1/generations/{id}", tags=["Generations"])
    def delete_generation(
        generation_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            unit_of_work.generations.soft_delete(
                user_id=current_user.id, generation_id=generation_id
            )
        except EntityNotFoundError as error:
            raise _not_found("Generation") from error
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/assets", tags=["Assets"])
    def list_assets(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        content_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        assets = unit_of_work.assets.list_for_user(
            user_id=current_user.id,
            workspace_id=workspace_id,
            brand_id=brand_id,
            project_id=project_id,
            content_id=content_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(assets, _asset_data), request)

    @application.post("/api/v1/assets", tags=["Assets"])
    def create_asset(
        payload: AssetCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        asset = unit_of_work.assets.add(
            workspace_id=payload.workspace_id,
            brand_id=payload.brand_id,
            project_id=payload.project_id,
            content_id=payload.content_id,
            uploaded_by_user_id=current_user.id,
            asset_type=payload.asset_type,
            storage_path=payload.storage_path,
            public_url=payload.public_url,
            mime_type=payload.mime_type,
            byte_size=payload.byte_size,
            checksum=payload.checksum,
            metadata=payload.metadata,
        )
        unit_of_work.commit()
        return success_response(_asset_data(asset), request, status_code=201)

    @application.get("/api/v1/assets/{id}", tags=["Assets"])
    def get_asset(
        asset_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        asset = unit_of_work.assets.get_for_user(user_id=current_user.id, asset_id=asset_id)
        if asset is None:
            raise _not_found("Asset")
        return success_response(_asset_data(asset), request)

    @application.put("/api/v1/assets/{id}", tags=["Assets"])
    def update_asset(
        asset_id: Annotated[UUID, Path(alias="id")],
        payload: AssetUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            asset = unit_of_work.assets.update(
                user_id=current_user.id,
                asset_id=asset_id,
                asset_type=payload.asset_type,
                public_url=payload.public_url,
                metadata=payload.metadata,
            )
        except EntityNotFoundError as error:
            raise _not_found("Asset") from error
        unit_of_work.commit()
        return success_response(_asset_data(asset), request)

    @application.delete("/api/v1/assets/{id}", tags=["Assets"])
    def delete_asset(
        asset_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        try:
            unit_of_work.assets.soft_delete(user_id=current_user.id, asset_id=asset_id)
        except EntityNotFoundError as error:
            raise _not_found("Asset") from error
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.post("/api/v1/content/generate", tags=["Contents"])
    def generate_text_content(
        payload: GenerateContentRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        settings: Annotated[Settings, Depends(get_settings)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    ) -> JSONResponse:
        try:
            generated = generate_content(
                unit_of_work=unit_of_work,
                settings=settings,
                llm_provider=llm_provider,
                user=current_user,
                command=GenerateContentCommand(
                    workspace_id=payload.workspace_id,
                    topic=payload.topic,
                    audience=payload.audience,
                    tone=payload.tone,
                    content_type=payload.content_type,
                    brand_voice=payload.brand_voice,
                ),
            )
        except WorkspaceAccessDeniedError as error:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "WORKSPACE_ACCESS_DENIED",
                    "message": "Workspace is not visible to the authenticated user",
                },
            ) from error
        except ProviderNotConfiguredError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "LLM_PROVIDER_MISCONFIGURED",
                    "message": "LLM provider is not configured",
                },
            ) from error
        except GeminiAuthenticationError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "LLM_PROVIDER_MISCONFIGURED",
                    "message": "LLM provider authentication is not configured",
                },
            ) from error
        except GeminiQuotaError as error:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "LLM_PROVIDER_RATE_LIMITED",
                    "message": "LLM provider quota or rate limit exceeded",
                },
            ) from error
        except GeminiBlockedContentError as error:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "CONTENT_GENERATION_BLOCKED",
                    "message": "Content generation was blocked by the provider",
                },
            ) from error
        except GeminiInvalidResponseError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "LLM_PROVIDER_INVALID_RESPONSE",
                    "message": "LLM provider returned an invalid response",
                },
            ) from error
        except GeminiTimeoutError as error:
            raise HTTPException(
                status_code=504,
                detail={
                    "code": "LLM_PROVIDER_TIMEOUT",
                    "message": "LLM provider timed out",
                },
            ) from error
        except (GeminiTransientError, GeminiProviderError) as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "LLM_PROVIDER_UNAVAILABLE",
                    "message": "LLM provider is unavailable",
                },
            ) from error
        except ContentGenerationPersistenceError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "CONTENT_GENERATION_PERSISTENCE_FAILED",
                    "message": "Generated Content could not be persisted",
                },
            ) from error

        return success_response(
            _content_data(
                generated.content,
                generation_id=generated.generation_id,
                generation_model=generated.generation_model,
                generation_parameters=generated.generation_parameters,
            ),
            request,
        )

    @application.post("/api/v1/content/improve", tags=["Contents"])
    def improve_text_content(
        payload: ImproveContentRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        settings: Annotated[Settings, Depends(get_settings)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    ) -> JSONResponse:
        try:
            preview = improve_content(
                unit_of_work=unit_of_work,
                settings=settings,
                llm_provider=llm_provider,
                user=current_user,
                command=ImproveContentCommand(
                    workspace_id=payload.workspace_id,
                    text=payload.text,
                    content_id=payload.content_id,
                    objective=payload.objective,
                    context=payload.context,
                    audience=payload.audience,
                ),
            )
        except WorkspaceAccessDeniedError as error:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "WORKSPACE_ACCESS_DENIED",
                    "message": "Workspace is not visible to the authenticated user",
                },
            ) from error
        except EntityNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "CONTENT_NOT_FOUND", "message": "Content not found"},
            ) from error
        except ProviderNotConfiguredError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "LLM_PROVIDER_MISCONFIGURED",
                    "message": "LLM provider is not configured",
                },
            ) from error
        except GeminiAuthenticationError as error:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "LLM_PROVIDER_MISCONFIGURED",
                    "message": "LLM provider authentication is not configured",
                },
            ) from error
        except GeminiQuotaError as error:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "LLM_PROVIDER_RATE_LIMITED",
                    "message": "LLM provider quota or rate limit exceeded",
                },
            ) from error
        except GeminiBlockedContentError as error:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "CONTENT_IMPROVEMENT_BLOCKED",
                    "message": "Content improvement was blocked by the provider",
                },
            ) from error
        except (GeminiInvalidResponseError, ContentImprovementInvalidResponseError) as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "LLM_PROVIDER_INVALID_RESPONSE",
                    "message": "LLM provider returned an invalid response",
                },
            ) from error
        except GeminiTimeoutError as error:
            raise HTTPException(
                status_code=504,
                detail={
                    "code": "LLM_PROVIDER_TIMEOUT",
                    "message": "LLM provider timed out",
                },
            ) from error
        except (GeminiTransientError, GeminiProviderError) as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "LLM_PROVIDER_UNAVAILABLE",
                    "message": "LLM provider is unavailable",
                },
            ) from error

        return success_response(_improved_content_data(preview), request)

    @application.post("/api/v1/images/generate", tags=["Images"])
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
            request_id = _request_id(request)
            status = submit_image_generation(
                unit_of_work=unit_of_work,
                queue=queue,
                settings=settings,
                user=current_user,
                content_id=payload.content_id,
                style=payload.style,
                idempotency_key=idempotency_key,
                request_id=request_id,
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

    @application.post("/api/v1/images/{id}/regenerate", tags=["Images"])
    def regenerate_image(
        image_id: Annotated[UUID, Path(alias="id")],
        payload: RegenerateImageRequest,
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
            request_id = _request_id(request)
            status = submit_image_regeneration(
                unit_of_work=unit_of_work,
                queue=queue,
                settings=settings,
                user=current_user,
                image_id=image_id,
                style=payload.style,
                idempotency_key=idempotency_key,
                request_id=request_id,
            )
        except EntityNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "IMAGE_NOT_FOUND", "message": "Image not found"},
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
                    "message": "Image regeneration could not be queued",
                },
            ) from error

        return success_response(_image_generation_status_data(status), request, status_code=202)

    @application.get("/api/v1/images/{id}", tags=["Images"])
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

    @application.get("/api/v1/content", tags=["Contents"])
    @application.get("/api/v1/contents", tags=["Contents"])
    def list_content(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
        q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        content_type: Annotated[
            str | None,
            Query(alias="type", pattern="^(IMAGE|TEXT)$"),
        ] = None,
    ) -> JSONResponse:
        content_page = unit_of_work.contents.list_for_user(
            user_id=current_user.id,
            filters=ContentFilters(content_type=content_type, query=q),
            page=PageRequest(
                page=page,
                limit=limit,
                sort="asc" if sort == "created_at" else "desc",
            ),
        )
        return success_response(_content_page_data(content_page), request)

    return application


app = create_app()

__all__ = ["app", "create_app", "error_response", "not_implemented", "success_response"]
