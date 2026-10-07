from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, cast
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
from creator.api.dtos import (
    AssetCreateRequest,
    AssetUpdateRequest,
    AuthLoginRequest,
    AuthSignupRequest,
    BillingAccountCreateRequest,
    BillingAccountUpdateRequest,
    BillingAddressCreateRequest,
    BillingAddressUpdateRequest,
    BrandAssetCreateRequest,
    BrandAssetUpdateRequest,
    BrandColorCreateRequest,
    BrandColorUpdateRequest,
    BrandCreateRequest,
    BrandSettingsUpdateRequest,
    BrandSettingsUpsertRequest,
    BrandUpdateRequest,
    CampaignCreateRequest,
    CampaignUpdateRequest,
    ChargeCreateRequest,
    ChargeUpdateRequest,
    ContentCreateRequest,
    ContentUpdateRequest,
    CouponCreateRequest,
    CouponRedemptionCreateRequest,
    CouponRedemptionUpdateRequest,
    CouponUpdateRequest,
    CreditPackageCreateRequest,
    CreditPackageUpdateRequest,
    DesignStructureCreateRequest,
    GenerateContentRequest,
    GenerateImageRequest,
    GenerationCreateRequest,
    GenerationUpdateRequest,
    ImageWorkflowDecisionRequest,
    ImageWorkflowRequest,
    ImproveContentRequest,
    InvoiceCreateRequest,
    InvoiceUpdateRequest,
    NotificationCreateRequest,
    NotificationPreferenceRequest,
    NotificationUpdateRequest,
    OrderCreateRequest,
    OrderUpdateRequest,
    PaymentMethodCreateRequest,
    PaymentMethodUpdateRequest,
    PersonaCreateRequest,
    PersonaUpdateRequest,
    PlanCreateRequest,
    PlanItemCreateRequest,
    PlanItemUpdateRequest,
    PlanningCreateRequest,
    PlanningUpdateRequest,
    PlanUpdateRequest,
    PostStructureCreateRequest,
    PostStructureUpdateRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProviderCustomerCreateRequest,
    ProviderDisputeCreateRequest,
    ProviderDisputeUpdateRequest,
    ProviderSubscriptionCreateRequest,
    RefundCreateRequest,
    RefundUpdateRequest,
    RegenerateImageRequest,
    SettingsUpdateRequest,
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
    UserCreateRequest,
    UserDeviceCreateRequest,
    UserDeviceUpdateRequest,
    UserUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceCreditTransactionCreateRequest,
    WorkspaceInviteCreateRequest,
    WorkspaceInviteUpdateRequest,
    WorkspaceUpdateRequest,
)
from creator.application.agent_image_workflow import (
    AgentWorkflowDecisionError,
    AgentWorkflowIdempotencyConflictError,
    AgentWorkflowInputError,
    AgentWorkflowQueueError,
    StartImageWorkflowCommand,
    decide_image_workflow,
    start_image_workflow,
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
from creator.domain.agent_workflow import WorkflowDecision
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
    {"name": "Campaigns", "description": "Campaign lifecycle endpoints."},
    {"name": "Personas", "description": "Audience persona endpoints."},
    {"name": "Planning", "description": "Content planning endpoints."},
    {"name": "Post Structures", "description": "Post structure endpoints."},
    {"name": "Brand Assets", "description": "Brand asset endpoints."},
    {"name": "Notifications", "description": "Principal notification settings and devices."},
    {"name": "Billing", "description": "Billing plan administration endpoints."},
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


def _require_global_billing_admin(user: UserRecord) -> None:
    if user.global_role not in {"admin", "gestor"}:
        raise HTTPException(status_code=403, detail="Billing administration required")


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


def _campaign_data(campaign: Any) -> dict[str, Any]:
    return {
        "id": str(campaign.id),
        "workspace_id": str(campaign.workspace_id),
        "created_by": str(campaign.created_by),
        "name": campaign.name,
        "description": campaign.description,
        "target_audience": campaign.target_audience,
        "objectives": campaign.objectives,
        "voice": campaign.voice,
        "start_at": campaign.start_at.isoformat() if campaign.start_at else None,
        "end_at": campaign.end_at.isoformat() if campaign.end_at else None,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat(),
        "deleted_at": campaign.deleted_at.isoformat() if campaign.deleted_at else None,
    }


def _post_structure_data(post_structure: Any) -> dict[str, Any]:
    return {
        "id": str(post_structure.id),
        "workspace_id": str(post_structure.workspace_id),
        "planning_id": str(post_structure.planning_id),
        "created_by": str(post_structure.created_by),
        "title": post_structure.title,
        "objective": post_structure.objective,
        "big_idea": post_structure.big_idea,
        "main_message": post_structure.main_message,
        "headline": post_structure.headline,
        "image_cta": post_structure.image_cta,
        "art_guiding": post_structure.art_guiding,
        "status": post_structure.status,
        "format": post_structure.format,
        "ratio": post_structure.ratio,
        "resolution": post_structure.resolution,
        "created_at": post_structure.created_at.isoformat(),
        "updated_at": post_structure.updated_at.isoformat(),
        "deleted_at": post_structure.deleted_at.isoformat() if post_structure.deleted_at else None,
    }


def _planning_data(planning: Any) -> dict[str, Any]:
    return {
        "id": str(planning.id),
        "brand_id": str(planning.brand_id),
        "campaign_id": str(planning.campaign_id),
        "persona_id": str(planning.persona_id),
        "created_by": str(planning.created_by),
        "info": planning.info,
        "static_amount": planning.static_amount,
        "carousel_amount": planning.carousel_amount,
        "stories_amount": planning.stories_amount,
        "special_dates": planning.special_dates,
        "start_period": planning.start_period.isoformat() if planning.start_period else None,
        "end_period": planning.end_period.isoformat() if planning.end_period else None,
        "created_at": planning.created_at.isoformat(),
        "updated_at": planning.updated_at.isoformat(),
        "deleted_at": planning.deleted_at.isoformat() if planning.deleted_at else None,
    }


def _persona_data(persona: Any) -> dict[str, Any]:
    return {
        "id": str(persona.id),
        "brand_id": str(persona.brand_id),
        "created_by": str(persona.created_by),
        "name": persona.name,
        "age": persona.age,
        "gender": persona.gender,
        "main_goal": persona.main_goal,
        "challenge": persona.challenge,
        "interest": persona.interest,
        "routine": persona.routine,
        "journey": persona.journey,
        "trigger": persona.trigger,
        "created_at": persona.created_at.isoformat(),
        "updated_at": persona.updated_at.isoformat(),
        "deleted_at": persona.deleted_at.isoformat() if persona.deleted_at else None,
    }


def _brand_asset_data(asset: Any) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "brand_id": str(asset.brand_id),
        "type": asset.type,
        "file_url": asset.file_url,
        "file_name": asset.file_name,
        "description": asset.description,
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
        "deleted_at": asset.deleted_at.isoformat() if asset.deleted_at else None,
    }


def _user_device_data(device: Any) -> dict[str, Any]:
    return {
        "id": str(device.id),
        "user_id": str(device.user_id),
        "platform": device.platform,
        "fcm_token": device.fcm_token,
        "is_active": device.is_active,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "created_at": device.created_at.isoformat(),
        "updated_at": device.updated_at.isoformat(),
        "deleted_at": device.deleted_at.isoformat() if device.deleted_at else None,
    }


def _notification_preference_data(preference: Any) -> dict[str, Any]:
    return {
        "id": str(preference.id),
        "user_id": str(preference.user_id),
        "type": preference.type,
        "channel": preference.channel,
        "is_enabled": preference.is_enabled,
        "created_at": preference.created_at.isoformat(),
        "updated_at": preference.updated_at.isoformat(),
        "deleted_at": preference.deleted_at.isoformat() if preference.deleted_at else None,
    }


def _notification_data(notification: Any) -> dict[str, Any]:
    return {
        "id": str(notification.id),
        "workspace_id": str(notification.workspace_id),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "payload": notification.payload,
        "resource_type": notification.resource_type,
        "resource_id": str(notification.resource_id) if notification.resource_id else None,
        "created_by": str(notification.created_by) if notification.created_by else None,
        "created_at": notification.created_at.isoformat(),
        "updated_at": notification.updated_at.isoformat(),
        "deleted_at": notification.deleted_at.isoformat() if notification.deleted_at else None,
    }


def _plan_data(plan: Any) -> dict[str, Any]:
    return {
        "id": str(plan.id),
        "code": plan.code,
        "type": plan.type,
        "name": plan.name,
        "description": plan.description,
        "metadata": plan.metadata,
        "is_active": plan.is_active,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
        "deleted_at": plan.deleted_at.isoformat() if plan.deleted_at else None,
    }


def _plan_item_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "plan_id": str(item.plan_id),
        "name": item.name,
        "description": item.description,
        "quantity": item.quantity,
        "cycles": item.cycles,
        "pricing_scheme_type": item.pricing_scheme_type,
        "price_cents": item.price_cents,
        "price_brackets": item.price_brackets,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _billing_account_data(account: Any) -> dict[str, Any]:
    return {
        "id": str(account.id),
        "user_id": str(account.user_id),
        "payer_type": account.payer_type,
        "name": account.name,
        "email": account.email,
        "phone": account.phone,
        "document": account.document,
        "document_type": account.document_type,
        "company_name": account.company_name,
        "provider": account.provider,
        "provider_customer_id": account.provider_customer_id,
        "provider_customer_code": account.provider_customer_code,
        "delinquent": account.delinquent,
        "metadata": account.metadata,
        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
        "deleted_at": account.deleted_at.isoformat() if account.deleted_at else None,
    }


def _billing_address_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "street": item.street,
        "number": item.number,
        "complement": item.complement,
        "neighborhood": item.neighborhood,
        "zip_code": item.zip_code,
        "city": item.city,
        "state": item.state,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _payment_method_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "holder_name": item.holder_name,
        "holder_document": item.holder_document,
        "card_brand": item.card_brand,
        "card_last_four": item.card_last_four,
        "exp_month": item.exp_month,
        "exp_year": item.exp_year,
        "card_type": item.card_type,
        "card_status": item.card_status,
        "is_default": item.is_default,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _subscription_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "workspace_id": str(item.workspace_id),
        "plan_id": str(item.plan_id),
        "status": item.status,
        "payment_method": item.payment_method,
        "billing_day": item.billing_day,
        "start_at": item.start_at.isoformat() if item.start_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _invoice_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "subscription_id": str(item.subscription_id) if item.subscription_id else None,
        "amount_cents": item.amount_cents,
        "currency": item.currency,
        "status": item.status,
        "billing_at": item.billing_at.isoformat() if item.billing_at else None,
        "due_at": item.due_at.isoformat() if item.due_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _charge_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "invoice_id": str(item.invoice_id) if item.invoice_id else None,
        "amount_cents": item.amount_cents,
        "currency": item.currency,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _coupon_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "code": item.code,
        "type": item.type,
        "discount_percent": item.discount_percent,
        "credits_amount": item.credits_amount,
        "applies_to": item.applies_to,
        "min_purchase_cents": item.min_purchase_cents,
        "max_redemptions": item.max_redemptions,
        "once_per_workspace": item.once_per_workspace,
        "redemptions_count": item.redemptions_count,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "is_active": item.is_active,
        "internal_note": item.internal_note,
        "created_by": str(item.created_by) if item.created_by else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _credit_package_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "code": item.code,
        "name": item.name,
        "credits_amount": item.credits_amount,
        "price_cents": item.price_cents,
        "currency": item.currency,
        "is_active": item.is_active,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _order_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "workspace_id": str(item.workspace_id),
        "credit_package_id": str(item.credit_package_id) if item.credit_package_id else None,
        "subtotal_cents": item.subtotal_cents,
        "discount_cents": item.discount_cents,
        "amount_cents": item.amount_cents,
        "currency": item.currency,
        "status": item.status,
        "closed": item.closed,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _coupon_redemption_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "coupon_id": str(item.coupon_id),
        "billing_account_id": str(item.billing_account_id),
        "order_id": str(item.order_id) if item.order_id else None,
        "subscription_id": str(item.subscription_id) if item.subscription_id else None,
        "discount_percent_applied": item.discount_percent_applied,
        "discount_amount_cents": item.discount_amount_cents,
        "credits_applied": item.credits_applied,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _workspace_invite_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "workspace_id": str(item.workspace_id),
        "type": item.type,
        "role": item.role,
        "email": item.email,
        "max_uses": item.max_uses,
        "uses_count": item.uses_count,
        "status": item.status,
        "is_active": item.is_active,
        "created_by": str(item.created_by),
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
        "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _workspace_credit_transaction_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "workspace_id": str(item.workspace_id),
        "amount": item.amount,
        "transaction_type": item.transaction_type,
        "reference_type": item.reference_type,
        "reference_id": str(item.reference_id) if item.reference_id else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _refund_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "invoice_id": str(item.invoice_id) if item.invoice_id else None,
        "amount_cents": item.amount_cents,
        "currency": item.currency,
        "reason": item.reason,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _provider_dispute_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "charge_id": str(item.charge_id) if item.charge_id else None,
        "code": item.code,
        "reason": item.reason,
        "status": item.status,
        "opened_at": item.opened_at.isoformat() if item.opened_at else None,
        "deadline_at": item.deadline_at.isoformat() if item.deadline_at else None,
        "payload": item.payload,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _provider_customer_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "billing_account_id": str(item.billing_account_id),
        "provider": item.provider,
        "provider_customer_id": item.provider_customer_id,
        "provider_code": item.provider_code,
        "metadata": item.metadata,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _provider_subscription_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "subscription_id": str(item.subscription_id),
        "provider": item.provider,
        "provider_subscription_id": item.provider_subscription_id,
        "provider_status": item.provider_status,
        "payload": item.payload,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _provider_webhook_event_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "provider": item.provider,
        "provider_event_id": item.provider_event_id,
        "dedupe_key": item.dedupe_key,
        "event_type": item.event_type,
        "account_id": item.account_id,
        "resource_type": item.resource_type,
        "resource_id": item.resource_id,
        "payload": item.payload,
        "signature_verified": item.signature_verified,
        "status": item.status,
        "attempts": item.attempts,
        "last_error": item.last_error,
        "received_at": item.received_at.isoformat(),
        "processed_at": item.processed_at.isoformat() if item.processed_at else None,
    }


def _provider_idempotency_key_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "provider": item.provider,
        "idempotency_key": item.idempotency_key,
        "request_hash": item.request_hash,
        "resource_type": item.resource_type,
        "resource_id": item.resource_id,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _design_structure_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "post_structure_id": str(item.post_structure_id),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _brand_color_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "brand_id": str(item.brand_id),
        "workspace_id": str(item.workspace_id),
        "created_by": str(item.created_by),
        "order": item.order,
        "color_name": item.color_name,
        "hex_code": item.hex_code,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _subscription_history_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "subscription_id": str(item.subscription_id),
        "change_type": item.change_type,
        "previous_plan_id": str(item.previous_plan_id) if item.previous_plan_id else None,
        "plan_id": str(item.plan_id) if item.plan_id else None,
        "previous_status": item.previous_status,
        "status": item.status,
        "reason": item.reason,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _notification_recipient_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "notification_id": str(item.notification_id),
        "user_id": str(item.user_id),
        "workspace_member_id": str(item.workspace_member_id) if item.workspace_member_id else None,
        "channel": item.channel,
        "status": item.status,
        "attempts": item.attempts,
        "sent_at": item.sent_at.isoformat() if item.sent_at else None,
        "read_at": item.read_at.isoformat() if item.read_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _workspace_invite_usage_data(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "invite_id": str(item.invite_id),
        "user_id": str(item.user_id),
        "workspace_id": str(item.workspace_id),
        "member_id": str(item.member_id) if item.member_id else None,
        "used_at": item.used_at.isoformat(),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


def _generated_image_data(image: Any) -> dict[str, Any]:
    return {
        "id": str(image.id),
        "workspace_id": str(image.workspace_id),
        "design_structure_id": str(image.design_structure_id),
        "signed_url": image.signed_url,
        "size": image.size,
        "resolution": image.resolution,
        "image_ratio": image.image_ratio,
        "status": image.status,
        "created_at": image.created_at.isoformat(),
        "updated_at": image.updated_at.isoformat(),
        "deleted_at": image.deleted_at.isoformat() if image.deleted_at else None,
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


def _agent_workflow_data(run: Any) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "workspace_id": str(run.workspace_id),
        "content_id": str(run.content_id),
        "brand_id": str(run.brand_id),
        "status": run.status.value,
        "human_review": run.human_review.value,
        "max_refinements": run.max_refinements,
        "refinement_count": run.refinement_count,
        "current_step": run.current_step,
        "input": run.input,
        "final_image_ids": run.final_image_ids,
        "failure_code": run.failure_code,
        "failure_message": run.failure_message,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _agent_workflow_step_data(step: Any) -> dict[str, Any]:
    return {
        "id": str(step.id),
        "run_id": str(step.run_id),
        "sequence_number": step.sequence_number,
        "role": step.role.value,
        "status": step.status.value,
        "attempt": step.attempt,
        "input": step.input,
        "output": step.output,
        "prompt": step.prompt,
        "prompt_template_id": step.prompt_template_id,
        "prompt_template_version": step.prompt_template_version,
        "input_hash": step.input_hash,
        "provider": step.provider,
        "model": step.model,
        "decision": step.decision,
        "error_code": step.error_code,
        "error_message": step.error_message,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
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

    @application.get("/api/v1/campaigns", tags=["Campaigns"])
    def list_campaigns(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        campaigns = unit_of_work.campaigns.list_for_user(
            user_id=current_user.id,
            workspace_id=workspace_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(campaigns, _campaign_data), request)

    @application.post("/api/v1/campaigns", tags=["Campaigns"])
    def create_campaign(
        payload: CampaignCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        campaign = unit_of_work.campaigns.add(
            workspace_id=payload.workspace_id,
            created_by=current_user.id,
            name=payload.name,
            description=payload.description,
            target_audience=payload.target_audience,
            objectives=payload.objectives,
            voice=payload.voice,
            start_at=payload.start_at,
            end_at=payload.end_at,
        )
        unit_of_work.commit()
        return success_response(_campaign_data(campaign), request, status_code=201)

    @application.get("/api/v1/campaigns/{id}", tags=["Campaigns"])
    def get_campaign(
        campaign_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        campaign = unit_of_work.campaigns.get_for_user(
            user_id=current_user.id, campaign_id=campaign_id
        )
        if campaign is None:
            raise _not_found("Campaign")
        return success_response(_campaign_data(campaign), request)

    @application.put("/api/v1/campaigns/{id}", tags=["Campaigns"])
    def update_campaign(
        campaign_id: Annotated[UUID, Path(alias="id")],
        payload: CampaignUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.campaigns.get_for_user(
            user_id=current_user.id, campaign_id=campaign_id
        )
        if existing is None:
            raise _not_found("Campaign")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        updated = unit_of_work.campaigns.update(
            campaign_id=campaign_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_campaign_data(updated), request)

    @application.delete("/api/v1/campaigns/{id}", tags=["Campaigns"])
    def delete_campaign(
        campaign_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.campaigns.get_for_user(
            user_id=current_user.id, campaign_id=campaign_id
        )
        if existing is None:
            raise _not_found("Campaign")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        unit_of_work.campaigns.soft_delete(campaign_id=campaign_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/personas", tags=["Personas"])
    def list_personas(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        brand_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        result = unit_of_work.personas.list_for_user(
            user_id=current_user.id,
            brand_id=brand_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(result, _persona_data), request)

    @application.post("/api/v1/personas", tags=["Personas"])
    def create_persona(
        payload: PersonaCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        brand = unit_of_work.brands.get_for_user(user_id=current_user.id, brand_id=payload.brand_id)
        if brand is None:
            raise _not_found("Brand")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=brand.workspace_id
        )
        persona = unit_of_work.personas.add(
            created_by=current_user.id,
            **payload.model_dump(),
        )
        unit_of_work.commit()
        return success_response(_persona_data(persona), request, status_code=201)

    @application.get("/api/v1/personas/{id}", tags=["Personas"])
    def get_persona(
        persona_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        persona = unit_of_work.personas.get_for_user(user_id=current_user.id, persona_id=persona_id)
        if persona is None:
            raise _not_found("Persona")
        return success_response(_persona_data(persona), request)

    @application.put("/api/v1/personas/{id}", tags=["Personas"])
    def update_persona(
        persona_id: Annotated[UUID, Path(alias="id")],
        payload: PersonaUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.personas.get_for_user(
            user_id=current_user.id, persona_id=persona_id
        )
        if existing is None:
            raise _not_found("Persona")
        brand = unit_of_work.brands.get_for_user(
            user_id=current_user.id, brand_id=existing.brand_id
        )
        if brand is None:
            raise _not_found("Persona")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=brand.workspace_id
        )
        updated = unit_of_work.personas.update(
            persona_id=persona_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_persona_data(updated), request)

    @application.delete("/api/v1/personas/{id}", tags=["Personas"])
    def delete_persona(
        persona_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.personas.get_for_user(
            user_id=current_user.id, persona_id=persona_id
        )
        if existing is None:
            raise _not_found("Persona")
        brand = unit_of_work.brands.get_for_user(
            user_id=current_user.id, brand_id=existing.brand_id
        )
        if brand is None:
            raise _not_found("Persona")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=brand.workspace_id
        )
        unit_of_work.personas.soft_delete(persona_id=persona_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/planning", tags=["Planning"])
    def list_planning(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        campaign_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        result = unit_of_work.planning.list_for_user(
            user_id=current_user.id,
            campaign_id=campaign_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(result, _planning_data), request)

    @application.post("/api/v1/planning", tags=["Planning"])
    def create_planning(
        payload: PlanningCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        campaign = unit_of_work.campaigns.get_for_user(
            user_id=current_user.id, campaign_id=payload.campaign_id
        )
        if campaign is None:
            raise _not_found("Campaign")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=campaign.workspace_id
        )
        planning = unit_of_work.planning.add(
            created_by=current_user.id,
            **payload.model_dump(),
        )
        unit_of_work.commit()
        return success_response(_planning_data(planning), request, status_code=201)

    @application.get("/api/v1/planning/{id}", tags=["Planning"])
    def get_planning(
        planning_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        planning = unit_of_work.planning.get_for_user(
            user_id=current_user.id, planning_id=planning_id
        )
        if planning is None:
            raise _not_found("Planning")
        return success_response(_planning_data(planning), request)

    @application.put("/api/v1/planning/{id}", tags=["Planning"])
    def update_planning(
        planning_id: Annotated[UUID, Path(alias="id")],
        payload: PlanningUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.planning.get_for_user(
            user_id=current_user.id, planning_id=planning_id
        )
        if existing is None:
            raise _not_found("Planning")
        campaign = unit_of_work.campaigns.get_for_user(
            user_id=current_user.id, campaign_id=existing.campaign_id
        )
        if campaign is None:
            raise _not_found("Planning")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=campaign.workspace_id
        )
        updated = unit_of_work.planning.update(
            planning_id=planning_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_planning_data(updated), request)

    @application.delete("/api/v1/planning/{id}", tags=["Planning"])
    def delete_planning(
        planning_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.planning.get_for_user(
            user_id=current_user.id, planning_id=planning_id
        )
        if existing is None:
            raise _not_found("Planning")
        campaign = unit_of_work.campaigns.get_for_user(
            user_id=current_user.id, campaign_id=existing.campaign_id
        )
        if campaign is None:
            raise _not_found("Planning")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=campaign.workspace_id
        )
        unit_of_work.planning.soft_delete(planning_id=planning_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/post-structures", tags=["Post Structures"])
    def list_post_structures(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        result = unit_of_work.post_structures.list_for_user(
            user_id=current_user.id,
            workspace_id=workspace_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(result, _post_structure_data), request)

    @application.post("/api/v1/post-structures", tags=["Post Structures"])
    def create_post_structure(
        payload: PostStructureCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        fields = payload.model_dump(exclude={"workspace_id", "planning_id"})
        post_structure = unit_of_work.post_structures.add(
            workspace_id=payload.workspace_id,
            planning_id=payload.planning_id,
            created_by=current_user.id,
            **fields,
        )
        unit_of_work.commit()
        return success_response(_post_structure_data(post_structure), request, status_code=201)

    @application.get("/api/v1/post-structures/{id}", tags=["Post Structures"])
    def get_post_structure(
        post_structure_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        post_structure = unit_of_work.post_structures.get_for_user(
            user_id=current_user.id, post_structure_id=post_structure_id
        )
        if post_structure is None:
            raise _not_found("Post structure")
        return success_response(_post_structure_data(post_structure), request)

    @application.put("/api/v1/post-structures/{id}", tags=["Post Structures"])
    def update_post_structure(
        post_structure_id: Annotated[UUID, Path(alias="id")],
        payload: PostStructureUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.post_structures.get_for_user(
            user_id=current_user.id, post_structure_id=post_structure_id
        )
        if existing is None:
            raise _not_found("Post structure")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        updated = unit_of_work.post_structures.update(
            post_structure_id=post_structure_id,
            fields=payload.model_dump(exclude_unset=True),
        )
        unit_of_work.commit()
        return success_response(_post_structure_data(updated), request)

    @application.delete("/api/v1/post-structures/{id}", tags=["Post Structures"])
    def delete_post_structure(
        post_structure_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.post_structures.get_for_user(
            user_id=current_user.id, post_structure_id=post_structure_id
        )
        if existing is None:
            raise _not_found("Post structure")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        unit_of_work.post_structures.soft_delete(post_structure_id=post_structure_id)
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
        if payload.planning_id is not None:
            post_fields = {
                key: value
                for key, value in payload.payload.items()
                if key
                in {
                    "objective",
                    "big_idea",
                    "main_message",
                    "headline",
                    "image_cta",
                    "art_guiding",
                    "status",
                    "format",
                    "ratio",
                    "resolution",
                }
            }
            post_structure = unit_of_work.post_structures.add(
                workspace_id=payload.workspace_id,
                planning_id=payload.planning_id,
                created_by=current_user.id,
                title=payload.title,
                **cast(dict[str, str | None], post_fields),
            )
            unit_of_work.commit()
            return success_response(_post_structure_data(post_structure), request, status_code=201)
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
        post_structures = getattr(unit_of_work, "post_structures", None)
        post_structure = (
            post_structures.get_for_user(user_id=current_user.id, post_structure_id=content_id)
            if post_structures is not None
            else None
        )
        if post_structure is not None:
            assert post_structures is not None
            return success_response(_post_structure_data(post_structure), request)
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
        post_structures = getattr(unit_of_work, "post_structures", None)
        post_structure = (
            post_structures.get_for_user(user_id=current_user.id, post_structure_id=content_id)
            if post_structures is not None
            else None
        )
        if post_structure is not None:
            assert post_structures is not None
            _require_workspace_write(
                unit_of_work, user_id=current_user.id, workspace_id=post_structure.workspace_id
            )
            allowed_fields = {
                "objective",
                "big_idea",
                "main_message",
                "headline",
                "image_cta",
                "art_guiding",
                "status",
                "format",
                "ratio",
                "resolution",
            }
            fields = {
                key: value
                for key, value in (payload.payload or {}).items()
                if key in allowed_fields
            }
            if payload.title is not None:
                fields["title"] = payload.title
            updated = post_structures.update(
                post_structure_id=content_id,
                fields=cast(dict[str, str | None], fields),
            )
            unit_of_work.commit()
            return success_response(_post_structure_data(updated), request)
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
        post_structures = getattr(unit_of_work, "post_structures", None)
        post_structure = (
            post_structures.get_for_user(user_id=current_user.id, post_structure_id=content_id)
            if post_structures is not None
            else None
        )
        if post_structure is not None:
            assert post_structures is not None
            _require_workspace_write(
                unit_of_work, user_id=current_user.id, workspace_id=post_structure.workspace_id
            )
            post_structures.soft_delete(post_structure_id=content_id)
            unit_of_work.commit()
            return success_response({"deleted": True}, request)
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

    @application.post("/api/v1/generations/image-workflows", tags=["Generations"])
    def create_image_workflow(
        payload: ImageWorkflowRequest,
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
            run = start_image_workflow(
                unit_of_work=unit_of_work,
                queue=queue,
                settings=settings,
                user=current_user,
                command=StartImageWorkflowCommand(
                    brand_id=payload.brand_id,
                    campaign=payload.campaign,
                    persona=payload.persona,
                    quantity=payload.quantity,
                    extra_instructions=payload.extra_instructions,
                    human_review=payload.human_review,
                    max_refinements=payload.max_refinements,
                    extensions=payload.extensions,
                    idempotency_key=idempotency_key,
                    request_id=_request_id(request),
                ),
            )
        except EntityNotFoundError as error:
            raise HTTPException(
                status_code=404, detail={"code": "BRAND_NOT_FOUND", "message": "Brand not found"}
            ) from error
        except AgentWorkflowIdempotencyConflictError as error:
            raise HTTPException(
                status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}
            ) from error
        except AgentWorkflowInputError as error:
            raise HTTPException(
                status_code=422, detail={"code": "WORKFLOW_INPUT_INVALID", "message": str(error)}
            ) from error
        except AgentWorkflowQueueError as error:
            raise HTTPException(
                status_code=503, detail={"code": "QUEUE_ENQUEUE_FAILED", "message": str(error)}
            ) from error
        return success_response(_agent_workflow_data(run), request, status_code=202)

    @application.get("/api/v1/generations/image-workflows/{id}", tags=["Generations"])
    def get_image_workflow(
        workflow_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        run = unit_of_work.agent_workflows.get_for_user(user_id=current_user.id, run_id=workflow_id)
        if run is None:
            raise _not_found("Agent workflow")
        return success_response(_agent_workflow_data(run), request)

    @application.get("/api/v1/generations/image-workflows/{id}/steps", tags=["Generations"])
    def list_image_workflow_steps(
        workflow_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        steps = unit_of_work.agent_workflows.list_steps_for_user(
            user_id=current_user.id, run_id=workflow_id
        )
        if steps is None:
            raise _not_found("Agent workflow")
        return success_response(
            {"items": [_agent_workflow_step_data(step) for step in steps]}, request
        )

    @application.post("/api/v1/generations/image-workflows/{id}/decision", tags=["Generations"])
    def decide_image_workflow_route(
        workflow_id: Annotated[UUID, Path(alias="id")],
        payload: ImageWorkflowDecisionRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        queue: Annotated[GenerationQueue, Depends(get_generation_queue)],
    ) -> JSONResponse:
        try:
            run = decide_image_workflow(
                unit_of_work=unit_of_work,
                queue=queue,
                run_id=workflow_id,
                user=current_user,
                request_id=_request_id(request),
                decision=WorkflowDecision(payload.decision),
                feedback=payload.feedback,
            )
        except EntityNotFoundError as error:
            raise _not_found("Agent workflow") from error
        except AgentWorkflowDecisionError as error:
            raise HTTPException(
                status_code=409, detail={"code": "WORKFLOW_DECISION_INVALID", "message": str(error)}
            ) from error
        except AgentWorkflowQueueError as error:
            raise HTTPException(
                status_code=503, detail={"code": "QUEUE_ENQUEUE_FAILED", "message": str(error)}
            ) from error
        return success_response(_agent_workflow_data(run), request)

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

    @application.get("/api/v1/brand-assets", tags=["Brand Assets"])
    def list_brand_assets(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        brand_id: UUID | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        sort: Annotated[str, Query(pattern="^-?created_at$")] = "-created_at",
    ) -> JSONResponse:
        result = unit_of_work.brand_assets.list_for_user(
            user_id=current_user.id,
            brand_id=brand_id,
            page=_page_request(page, limit, sort),
        )
        return success_response(_page_data(result, _brand_asset_data), request)

    @application.post("/api/v1/brand-assets", tags=["Brand Assets"])
    def create_brand_asset(
        payload: BrandAssetCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        brand = unit_of_work.brands.get_for_user(user_id=current_user.id, brand_id=payload.brand_id)
        if brand is None:
            raise _not_found("Brand")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=brand.workspace_id
        )
        asset = unit_of_work.brand_assets.add(
            brand_id=payload.brand_id,
            type=payload.type,
            file_url=payload.file_url,
            file_name=payload.file_name,
            description=payload.description,
        )
        unit_of_work.commit()
        return success_response(_brand_asset_data(asset), request, status_code=201)

    @application.get("/api/v1/brand-assets/{id}", tags=["Brand Assets"])
    def get_brand_asset(
        asset_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        asset = unit_of_work.brand_assets.get_for_user(user_id=current_user.id, asset_id=asset_id)
        if asset is None:
            raise _not_found("Brand asset")
        return success_response(_brand_asset_data(asset), request)

    @application.put("/api/v1/brand-assets/{id}", tags=["Brand Assets"])
    def update_brand_asset(
        asset_id: Annotated[UUID, Path(alias="id")],
        payload: BrandAssetUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.brand_assets.get_for_user(
            user_id=current_user.id, asset_id=asset_id
        )
        if existing is None:
            raise _not_found("Brand asset")
        brand = unit_of_work.brands.get_for_user(
            user_id=current_user.id, brand_id=existing.brand_id
        )
        if brand is None:
            raise _not_found("Brand asset")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=brand.workspace_id
        )
        updated = unit_of_work.brand_assets.update(
            asset_id=asset_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_brand_asset_data(updated), request)

    @application.delete("/api/v1/brand-assets/{id}", tags=["Brand Assets"])
    def delete_brand_asset(
        asset_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.brand_assets.get_for_user(
            user_id=current_user.id, asset_id=asset_id
        )
        if existing is None:
            raise _not_found("Brand asset")
        brand = unit_of_work.brands.get_for_user(
            user_id=current_user.id, brand_id=existing.brand_id
        )
        if brand is None:
            raise _not_found("Brand asset")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=brand.workspace_id
        )
        unit_of_work.brand_assets.soft_delete(asset_id=asset_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/subscription-history", tags=["Billing"])
    def list_subscription_history(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _subscription_history_data(x)
                    for x in unit_of_work.subscription_history.list_for_user(
                        user_id=current_user.id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/subscription-history", tags=["Billing"])
    def create_subscription_history(
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        subscription_id = payload.get("subscription_id")
        if (
            subscription_id is None
            or unit_of_work.subscriptions.get_for_user(
                user_id=current_user.id, subscription_id=subscription_id
            )
            is None
        ):
            raise _not_found("Subscription")
        item = unit_of_work.subscription_history.add(fields=payload)
        unit_of_work.commit()
        return success_response(_subscription_history_data(item), request, status_code=201)

    @application.get("/api/v1/subscription-history/{id}", tags=["Billing"])
    def get_subscription_history(
        history_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.subscription_history.get_for_user(
            user_id=current_user.id, history_id=history_id
        )
        if item is None:
            raise _not_found("Subscription history")
        return success_response(_subscription_history_data(item), request)

    @application.put("/api/v1/subscription-history/{id}", tags=["Billing"])
    def update_subscription_history(
        history_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.subscription_history.get_for_user(
                user_id=current_user.id, history_id=history_id
            )
            is None
        ):
            raise _not_found("Subscription history")
        item = unit_of_work.subscription_history.update(history_id=history_id, fields=payload)
        unit_of_work.commit()
        return success_response(_subscription_history_data(item), request)

    @application.delete("/api/v1/subscription-history/{id}", tags=["Billing"])
    def delete_subscription_history(
        history_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.subscription_history.get_for_user(
                user_id=current_user.id, history_id=history_id
            )
            is None
        ):
            raise _not_found("Subscription history")
        unit_of_work.subscription_history.soft_delete(history_id=history_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/brand-colors", tags=["Brands"])
    def list_brand_colors(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        brand_id: UUID | None = None,
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _brand_color_data(x)
                    for x in unit_of_work.brand_colors.list_for_user(
                        user_id=current_user.id, brand_id=brand_id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/brand-colors", tags=["Brands"])
    def create_brand_color(
        payload: BrandColorCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        data = payload.model_dump()
        data["created_by"] = current_user.id
        item = unit_of_work.brand_colors.add(fields=data)
        unit_of_work.commit()
        return success_response(_brand_color_data(item), request, status_code=201)

    @application.get("/api/v1/brand-colors/{id}", tags=["Brands"])
    def get_brand_color(
        color_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.brand_colors.get_for_user(user_id=current_user.id, color_id=color_id)
        if item is None:
            raise _not_found("Brand color")
        return success_response(_brand_color_data(item), request)

    @application.put("/api/v1/brand-colors/{id}", tags=["Brands"])
    def update_brand_color(
        color_id: Annotated[UUID, Path(alias="id")],
        payload: BrandColorUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.brand_colors.get_for_user(user_id=current_user.id, color_id=color_id)
            is None
        ):
            raise _not_found("Brand color")
        item = unit_of_work.brand_colors.update(
            color_id=color_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_brand_color_data(item), request)

    @application.delete("/api/v1/brand-colors/{id}", tags=["Brands"])
    def delete_brand_color(
        color_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.brand_colors.get_for_user(user_id=current_user.id, color_id=color_id)
            is None
        ):
            raise _not_found("Brand color")
        unit_of_work.brand_colors.soft_delete(color_id=color_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/design-structures", tags=["Post Structures"])
    def list_design_structures(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _design_structure_data(x)
                    for x in unit_of_work.design_structures.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/design-structures", tags=["Post Structures"])
    def create_design_structure(
        payload: DesignStructureCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.post_structures.get_for_user(
            user_id=current_user.id, post_structure_id=payload.post_structure_id
        )
        if item is None:
            raise _not_found("Post structure")
        result = unit_of_work.design_structures.add(post_structure_id=payload.post_structure_id)
        unit_of_work.commit()
        return success_response(_design_structure_data(result), request, status_code=201)

    @application.get("/api/v1/design-structures/{id}", tags=["Post Structures"])
    def get_design_structure(
        design_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.design_structures.get_for_user(
            user_id=current_user.id, design_id=design_id
        )
        if item is None:
            raise _not_found("Design structure")
        return success_response(_design_structure_data(item), request)

    @application.put("/api/v1/design-structures/{id}", tags=["Post Structures"])
    def update_design_structure(
        design_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.design_structures.get_for_user(
                user_id=current_user.id, design_id=design_id
            )
            is None
        ):
            raise _not_found("Design structure")
        item = unit_of_work.design_structures.update(design_id=design_id, fields=payload)
        unit_of_work.commit()
        return success_response(_design_structure_data(item), request)

    @application.delete("/api/v1/design-structures/{id}", tags=["Post Structures"])
    def delete_design_structure(
        design_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.design_structures.get_for_user(
                user_id=current_user.id, design_id=design_id
            )
            is None
        ):
            raise _not_found("Design structure")
        unit_of_work.design_structures.soft_delete(design_id=design_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/workspace-credit-transactions", tags=["Workspaces"])
    def list_workspace_credit_transactions(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
    ) -> JSONResponse:
        items = unit_of_work.workspace_credit_transactions.list_for_user(
            user_id=current_user.id, workspace_id=workspace_id
        )
        return success_response(
            {"items": [_workspace_credit_transaction_data(x) for x in items]}, request
        )

    @application.post("/api/v1/workspace-credit-transactions", tags=["Workspaces"])
    def create_workspace_credit_transaction(
        payload: WorkspaceCreditTransactionCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        item = unit_of_work.workspace_credit_transactions.add(fields=payload.model_dump())
        unit_of_work.commit()
        return success_response(_workspace_credit_transaction_data(item), request, status_code=201)

    @application.get("/api/v1/workspace-credit-transactions/{id}", tags=["Workspaces"])
    def get_workspace_credit_transaction(
        transaction_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.workspace_credit_transactions.get_for_user(
            user_id=current_user.id, transaction_id=transaction_id
        )
        if item is None:
            raise _not_found("Workspace credit transaction")
        return success_response(_workspace_credit_transaction_data(item), request)

    @application.delete("/api/v1/workspace-credit-transactions/{id}", tags=["Workspaces"])
    def delete_workspace_credit_transaction(
        transaction_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.workspace_credit_transactions.get_for_user(
                user_id=current_user.id, transaction_id=transaction_id
            )
            is None
        ):
            raise _not_found("Workspace credit transaction")
        unit_of_work.workspace_credit_transactions.soft_delete(transaction_id=transaction_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/workspace-invites", tags=["Workspaces"])
    def list_workspace_invites(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _workspace_invite_data(x)
                    for x in unit_of_work.workspace_invites.list_for_user(
                        user_id=current_user.id, workspace_id=workspace_id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/workspace-invites", tags=["Workspaces"])
    def create_workspace_invite(
        payload: WorkspaceInviteCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        item = unit_of_work.workspace_invites.add(
            **payload.model_dump(), created_by=current_user.id, token=uuid4().hex
        )
        unit_of_work.commit()
        return success_response(_workspace_invite_data(item), request, status_code=201)

    @application.get("/api/v1/workspace-invites/{id}", tags=["Workspaces"])
    def get_workspace_invite(
        invite_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.workspace_invites.get_for_user(
            user_id=current_user.id, invite_id=invite_id
        )
        if item is None:
            raise _not_found("Workspace invite")
        return success_response(_workspace_invite_data(item), request)

    @application.put("/api/v1/workspace-invites/{id}", tags=["Workspaces"])
    def update_workspace_invite(
        invite_id: Annotated[UUID, Path(alias="id")],
        payload: WorkspaceInviteUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.workspace_invites.get_for_user(
                user_id=current_user.id, invite_id=invite_id
            )
            is None
        ):
            raise _not_found("Workspace invite")
        item = unit_of_work.workspace_invites.update(
            invite_id=invite_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_workspace_invite_data(item), request)

    @application.delete("/api/v1/workspace-invites/{id}", tags=["Workspaces"])
    def delete_workspace_invite(
        invite_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.workspace_invites.get_for_user(
                user_id=current_user.id, invite_id=invite_id
            )
            is None
        ):
            raise _not_found("Workspace invite")
        unit_of_work.workspace_invites.soft_delete(invite_id=invite_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/billing-addresses", tags=["Billing"])
    def list_billing_addresses(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        billing_account_id: UUID | None = None,
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _billing_address_data(x)
                    for x in unit_of_work.billing_addresses.list_for_user(
                        user_id=current_user.id, account_id=billing_account_id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/billing-addresses", tags=["Billing"])
    def create_billing_address(
        payload: BillingAddressCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        data = payload.model_dump()
        account_id = data.pop("billing_account_id")
        item = unit_of_work.billing_addresses.add(billing_account_id=account_id, fields=data)
        unit_of_work.commit()
        return success_response(_billing_address_data(item), request, status_code=201)

    @application.get("/api/v1/billing-addresses/{id}", tags=["Billing"])
    def get_billing_address(
        address_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.billing_addresses.get_for_user(
            user_id=current_user.id, address_id=address_id
        )
        if item is None:
            raise _not_found("Billing address")
        return success_response(_billing_address_data(item), request)

    @application.put("/api/v1/billing-addresses/{id}", tags=["Billing"])
    def update_billing_address(
        address_id: Annotated[UUID, Path(alias="id")],
        payload: BillingAddressUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_addresses.get_for_user(
                user_id=current_user.id, address_id=address_id
            )
            is None
        ):
            raise _not_found("Billing address")
        item = unit_of_work.billing_addresses.update(
            address_id=address_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_billing_address_data(item), request)

    @application.delete("/api/v1/billing-addresses/{id}", tags=["Billing"])
    def delete_billing_address(
        address_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_addresses.get_for_user(
                user_id=current_user.id, address_id=address_id
            )
            is None
        ):
            raise _not_found("Billing address")
        unit_of_work.billing_addresses.soft_delete(address_id=address_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/billing-payment-methods", tags=["Billing"])
    def list_payment_methods(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        billing_account_id: UUID | None = None,
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _payment_method_data(x)
                    for x in unit_of_work.billing_payment_methods.list_for_user(
                        user_id=current_user.id, account_id=billing_account_id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/billing-payment-methods", tags=["Billing"])
    def create_payment_method(
        payload: PaymentMethodCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        data = payload.model_dump()
        account_id = data.pop("billing_account_id")
        item = unit_of_work.billing_payment_methods.add(billing_account_id=account_id, fields=data)
        unit_of_work.commit()
        return success_response(_payment_method_data(item), request, status_code=201)

    @application.get("/api/v1/billing-payment-methods/{id}", tags=["Billing"])
    def get_payment_method(
        method_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.billing_payment_methods.get_for_user(
            user_id=current_user.id, method_id=method_id
        )
        if item is None:
            raise _not_found("Billing payment method")
        return success_response(_payment_method_data(item), request)

    @application.put("/api/v1/billing-payment-methods/{id}", tags=["Billing"])
    def update_payment_method(
        method_id: Annotated[UUID, Path(alias="id")],
        payload: PaymentMethodUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_payment_methods.get_for_user(
                user_id=current_user.id, method_id=method_id
            )
            is None
        ):
            raise _not_found("Billing payment method")
        item = unit_of_work.billing_payment_methods.update(
            method_id=method_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_payment_method_data(item), request)

    @application.delete("/api/v1/billing-payment-methods/{id}", tags=["Billing"])
    def delete_payment_method(
        method_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_payment_methods.get_for_user(
                user_id=current_user.id, method_id=method_id
            )
            is None
        ):
            raise _not_found("Billing payment method")
        unit_of_work.billing_payment_methods.soft_delete(method_id=method_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/billing-accounts", tags=["Billing"])
    def list_billing_accounts(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        items = unit_of_work.billing_accounts.list_for_user(user_id=current_user.id)
        return success_response({"items": [_billing_account_data(item) for item in items]}, request)

    @application.post("/api/v1/billing-accounts", tags=["Billing"])
    def create_billing_account(
        payload: BillingAccountCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if payload.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Billing account belongs to another Principal"
            )
        item = unit_of_work.billing_accounts.add(
            user_id=current_user.id,
            payer_type=payload.payer_type,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            document=payload.document,
            document_type=payload.document_type,
        )
        unit_of_work.commit()
        return success_response(_billing_account_data(item), request, status_code=201)

    @application.get("/api/v1/billing-accounts/{id}", tags=["Billing"])
    def get_billing_account(
        account_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.billing_accounts.get_for_user(
            user_id=current_user.id, account_id=account_id
        )
        if item is None:
            raise _not_found("Billing account")
        return success_response(_billing_account_data(item), request)

    @application.put("/api/v1/billing-accounts/{id}", tags=["Billing"])
    def update_billing_account(
        account_id: Annotated[UUID, Path(alias="id")],
        payload: BillingAccountUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        item = unit_of_work.billing_accounts.update(
            user_id=current_user.id,
            account_id=account_id,
            fields=payload.model_dump(exclude_unset=True),
        )
        unit_of_work.commit()
        return success_response(_billing_account_data(item), request)

    @application.delete("/api/v1/billing-accounts/{id}", tags=["Billing"])
    def delete_billing_account(
        account_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        unit_of_work.billing_accounts.soft_delete(user_id=current_user.id, account_id=account_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/subscriptions", tags=["Billing"])
    def list_subscriptions(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _subscription_data(x)
                    for x in unit_of_work.subscriptions.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/subscriptions", tags=["Billing"])
    def create_subscription(
        payload: SubscriptionCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        if unit_of_work.plans.get(plan_id=payload.plan_id) is None:
            raise _not_found("Plan")
        item = unit_of_work.subscriptions.add(**payload.model_dump())
        unit_of_work.commit()
        return success_response(_subscription_data(item), request, status_code=201)

    @application.get("/api/v1/subscriptions/{id}", tags=["Billing"])
    def get_subscription(
        subscription_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.subscriptions.get_for_user(
            user_id=current_user.id, subscription_id=subscription_id
        )
        if item is None:
            raise _not_found("Subscription")
        return success_response(_subscription_data(item), request)

    @application.put("/api/v1/subscriptions/{id}", tags=["Billing"])
    def update_subscription(
        subscription_id: Annotated[UUID, Path(alias="id")],
        payload: SubscriptionUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.subscriptions.get_for_user(
                user_id=current_user.id, subscription_id=subscription_id
            )
            is None
        ):
            raise _not_found("Subscription")
        item = unit_of_work.subscriptions.update(
            subscription_id=subscription_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_subscription_data(item), request)

    @application.delete("/api/v1/subscriptions/{id}", tags=["Billing"])
    def delete_subscription(
        subscription_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.subscriptions.get_for_user(
                user_id=current_user.id, subscription_id=subscription_id
            )
            is None
        ):
            raise _not_found("Subscription")
        unit_of_work.subscriptions.soft_delete(subscription_id=subscription_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/invoices", tags=["Billing"])
    def list_invoices(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _invoice_data(x)
                    for x in unit_of_work.invoices.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/invoices", tags=["Billing"])
    def create_invoice(
        payload: InvoiceCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        item = unit_of_work.invoices.add(**payload.model_dump())
        unit_of_work.commit()
        return success_response(_invoice_data(item), request, status_code=201)

    @application.get("/api/v1/invoices/{id}", tags=["Billing"])
    def get_invoice(
        invoice_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.invoices.get_for_user(user_id=current_user.id, invoice_id=invoice_id)
        if item is None:
            raise _not_found("Invoice")
        return success_response(_invoice_data(item), request)

    @application.put("/api/v1/invoices/{id}", tags=["Billing"])
    def update_invoice(
        invoice_id: Annotated[UUID, Path(alias="id")],
        payload: InvoiceUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.invoices.get_for_user(user_id=current_user.id, invoice_id=invoice_id)
            is None
        ):
            raise _not_found("Invoice")
        item = unit_of_work.invoices.update(
            invoice_id=invoice_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_invoice_data(item), request)

    @application.delete("/api/v1/invoices/{id}", tags=["Billing"])
    def delete_invoice(
        invoice_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.invoices.get_for_user(user_id=current_user.id, invoice_id=invoice_id)
            is None
        ):
            raise _not_found("Invoice")
        unit_of_work.invoices.soft_delete(invoice_id=invoice_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/charges", tags=["Billing"])
    def list_charges(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _charge_data(x)
                    for x in unit_of_work.charges.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/charges", tags=["Billing"])
    def create_charge(
        payload: ChargeCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        item = unit_of_work.charges.add(**payload.model_dump())
        unit_of_work.commit()
        return success_response(_charge_data(item), request, status_code=201)

    @application.get("/api/v1/charges/{id}", tags=["Billing"])
    def get_charge(
        charge_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.charges.get_for_user(user_id=current_user.id, charge_id=charge_id)
        if item is None:
            raise _not_found("Charge")
        return success_response(_charge_data(item), request)

    @application.put("/api/v1/charges/{id}", tags=["Billing"])
    def update_charge(
        charge_id: Annotated[UUID, Path(alias="id")],
        payload: ChargeUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if unit_of_work.charges.get_for_user(user_id=current_user.id, charge_id=charge_id) is None:
            raise _not_found("Charge")
        item = unit_of_work.charges.update(
            charge_id=charge_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_charge_data(item), request)

    @application.delete("/api/v1/charges/{id}", tags=["Billing"])
    def delete_charge(
        charge_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if unit_of_work.charges.get_for_user(user_id=current_user.id, charge_id=charge_id) is None:
            raise _not_found("Charge")
        unit_of_work.charges.soft_delete(charge_id=charge_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/orders", tags=["Billing"])
    def list_orders(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _order_data(x)
                    for x in unit_of_work.orders.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/orders", tags=["Billing"])
    def create_order(
        payload: OrderCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        data = payload.model_dump()
        data["status"] = "pending"
        item = unit_of_work.orders.add(fields=data)
        unit_of_work.commit()
        return success_response(_order_data(item), request, status_code=201)

    @application.get("/api/v1/orders/{id}", tags=["Billing"])
    def get_order(
        order_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.orders.get_for_user(user_id=current_user.id, order_id=order_id)
        if item is None:
            raise _not_found("Order")
        return success_response(_order_data(item), request)

    @application.put("/api/v1/orders/{id}", tags=["Billing"])
    def update_order(
        order_id: Annotated[UUID, Path(alias="id")],
        payload: OrderUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if unit_of_work.orders.get_for_user(user_id=current_user.id, order_id=order_id) is None:
            raise _not_found("Order")
        item = unit_of_work.orders.update(
            order_id=order_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_order_data(item), request)

    @application.delete("/api/v1/orders/{id}", tags=["Billing"])
    def delete_order(
        order_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if unit_of_work.orders.get_for_user(user_id=current_user.id, order_id=order_id) is None:
            raise _not_found("Order")
        unit_of_work.orders.soft_delete(order_id=order_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/coupon-redemptions", tags=["Billing"])
    def list_coupon_redemptions(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _coupon_redemption_data(x)
                    for x in unit_of_work.coupon_redemptions.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/coupon-redemptions", tags=["Billing"])
    def create_coupon_redemption(
        payload: CouponRedemptionCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        data = payload.model_dump()
        data["status"] = "applied"
        item = unit_of_work.coupon_redemptions.add(fields=data)
        unit_of_work.commit()
        return success_response(_coupon_redemption_data(item), request, status_code=201)

    @application.get("/api/v1/coupon-redemptions/{id}", tags=["Billing"])
    def get_coupon_redemption(
        redemption_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.coupon_redemptions.get_for_user(
            user_id=current_user.id, redemption_id=redemption_id
        )
        if item is None:
            raise _not_found("Coupon redemption")
        return success_response(_coupon_redemption_data(item), request)

    @application.put("/api/v1/coupon-redemptions/{id}", tags=["Billing"])
    def update_coupon_redemption(
        redemption_id: Annotated[UUID, Path(alias="id")],
        payload: CouponRedemptionUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.coupon_redemptions.get_for_user(
                user_id=current_user.id, redemption_id=redemption_id
            )
            is None
        ):
            raise _not_found("Coupon redemption")
        item = unit_of_work.coupon_redemptions.update(
            redemption_id=redemption_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_coupon_redemption_data(item), request)

    @application.delete("/api/v1/coupon-redemptions/{id}", tags=["Billing"])
    def delete_coupon_redemption(
        redemption_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.coupon_redemptions.get_for_user(
                user_id=current_user.id, redemption_id=redemption_id
            )
            is None
        ):
            raise _not_found("Coupon redemption")
        unit_of_work.coupon_redemptions.soft_delete(redemption_id=redemption_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/provider-customers", tags=["Billing"])
    def list_provider_customers(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _provider_customer_data(x)
                    for x in unit_of_work.provider_customers.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/provider-customers", tags=["Billing"])
    def create_provider_customer(
        payload: ProviderCustomerCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        data = payload.model_dump()
        data["metadata_json"] = data.pop("metadata")
        item = unit_of_work.provider_customers.add(fields=data)
        unit_of_work.commit()
        return success_response(_provider_customer_data(item), request, status_code=201)

    @application.get("/api/v1/provider-customers/{id}", tags=["Billing"])
    def get_provider_customer(
        record_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.provider_customers.get_for_user(
            user_id=current_user.id, record_id=record_id
        )
        if item is None:
            raise _not_found("Provider customer")
        return success_response(_provider_customer_data(item), request)

    @application.delete("/api/v1/provider-customers/{id}", tags=["Billing"])
    def delete_provider_customer(
        record_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.provider_customers.get_for_user(
                user_id=current_user.id, record_id=record_id
            )
            is None
        ):
            raise _not_found("Provider customer")
        unit_of_work.provider_customers.soft_delete(record_id=record_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.put("/api/v1/provider-customers/{id}", tags=["Billing"])
    def update_provider_customer(
        record_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.provider_customers.get_for_user(
                user_id=current_user.id, record_id=record_id
            )
            is None
        ):
            raise _not_found("Provider customer")
        item = unit_of_work.provider_customers.update(record_id=record_id, fields=payload)
        unit_of_work.commit()
        return success_response(_provider_customer_data(item), request)

    @application.get("/api/v1/provider-subscriptions", tags=["Billing"])
    def list_provider_subscriptions(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _provider_subscription_data(x)
                    for x in unit_of_work.provider_subscriptions.list_for_user(
                        user_id=current_user.id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/provider-subscriptions", tags=["Billing"])
    def create_provider_subscription(
        payload: ProviderSubscriptionCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.subscriptions.get_for_user(
                user_id=current_user.id, subscription_id=payload.subscription_id
            )
            is None
        ):
            raise _not_found("Subscription")
        data = payload.model_dump()
        data["payload"] = data.pop("payload")
        item = unit_of_work.provider_subscriptions.add(fields=data)
        unit_of_work.commit()
        return success_response(_provider_subscription_data(item), request, status_code=201)

    @application.get("/api/v1/provider-subscriptions/{id}", tags=["Billing"])
    def get_provider_subscription(
        record_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.provider_subscriptions.get_for_user(
            user_id=current_user.id, record_id=record_id
        )
        if item is None:
            raise _not_found("Provider subscription")
        return success_response(_provider_subscription_data(item), request)

    @application.delete("/api/v1/provider-subscriptions/{id}", tags=["Billing"])
    def delete_provider_subscription(
        record_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.provider_subscriptions.get_for_user(
                user_id=current_user.id, record_id=record_id
            )
            is None
        ):
            raise _not_found("Provider subscription")
        unit_of_work.provider_subscriptions.soft_delete(record_id=record_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/provider-webhook-events", tags=["Billing"])
    def list_provider_webhook_events(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        return success_response(
            {
                "items": [
                    _provider_webhook_event_data(x)
                    for x in unit_of_work.provider_webhook_events.list()
                ]
            },
            request,
        )

    @application.post("/api/v1/provider-webhook-events", tags=["Billing"])
    def create_provider_webhook_event(
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.provider_webhook_events.add(fields=payload)
        unit_of_work.commit()
        return success_response(_provider_webhook_event_data(item), request, status_code=201)

    @application.get("/api/v1/provider-webhook-events/{id}", tags=["Billing"])
    def get_provider_webhook_event(
        event_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.provider_webhook_events.get(event_id=event_id)
        if item is None:
            raise _not_found("Provider webhook event")
        return success_response(_provider_webhook_event_data(item), request)

    @application.put("/api/v1/provider-webhook-events/{id}", tags=["Billing"])
    def update_provider_webhook_event(
        event_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.provider_webhook_events.get(event_id=event_id) is None:
            raise _not_found("Provider webhook event")
        item = unit_of_work.provider_webhook_events.update(event_id=event_id, fields=payload)
        unit_of_work.commit()
        return success_response(_provider_webhook_event_data(item), request)

    @application.delete("/api/v1/provider-webhook-events/{id}", tags=["Billing"])
    def delete_provider_webhook_event(
        event_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.provider_webhook_events.get(event_id=event_id)
        if item is None:
            raise _not_found("Provider webhook event")
        updated = unit_of_work.provider_webhook_events.update(
            event_id=event_id, fields={"status": "deleted"}
        )
        unit_of_work.commit()
        return success_response(_provider_webhook_event_data(updated), request)

    @application.get("/api/v1/provider-idempotency-keys", tags=["Billing"])
    def list_provider_idempotency_keys(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        return success_response(
            {
                "items": [
                    _provider_idempotency_key_data(x)
                    for x in unit_of_work.provider_idempotency_keys.list()
                ]
            },
            request,
        )

    @application.post("/api/v1/provider-idempotency-keys", tags=["Billing"])
    def create_provider_idempotency_key(
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.provider_idempotency_keys.add(fields=payload)
        unit_of_work.commit()
        return success_response(_provider_idempotency_key_data(item), request, status_code=201)

    @application.get("/api/v1/provider-idempotency-keys/{id}", tags=["Billing"])
    def get_provider_idempotency_key(
        key_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.provider_idempotency_keys.get(key_id=key_id)
        if item is None:
            raise _not_found("Provider idempotency key")
        return success_response(_provider_idempotency_key_data(item), request)

    @application.put("/api/v1/provider-idempotency-keys/{id}", tags=["Billing"])
    def update_provider_idempotency_key(
        key_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.provider_idempotency_keys.get(key_id=key_id) is None:
            raise _not_found("Provider idempotency key")
        item = unit_of_work.provider_idempotency_keys.update(key_id=key_id, fields=payload)
        unit_of_work.commit()
        return success_response(_provider_idempotency_key_data(item), request)

    @application.delete("/api/v1/provider-idempotency-keys/{id}", tags=["Billing"])
    def delete_provider_idempotency_key(
        key_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.provider_idempotency_keys.get(key_id=key_id) is None:
            raise _not_found("Provider idempotency key")
        item = unit_of_work.provider_idempotency_keys.update(
            key_id=key_id, fields={"status": "deleted"}
        )
        unit_of_work.commit()
        return success_response(_provider_idempotency_key_data(item), request)

    @application.put("/api/v1/provider-subscriptions/{id}", tags=["Billing"])
    def update_provider_subscription(
        record_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.provider_subscriptions.get_for_user(
                user_id=current_user.id, record_id=record_id
            )
            is None
        ):
            raise _not_found("Provider subscription")
        item = unit_of_work.provider_subscriptions.update(record_id=record_id, fields=payload)
        unit_of_work.commit()
        return success_response(_provider_subscription_data(item), request)

    @application.get("/api/v1/refunds", tags=["Billing"])
    def list_refunds(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _refund_data(x)
                    for x in unit_of_work.refunds.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/refunds", tags=["Billing"])
    def create_refund(
        payload: RefundCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        data = payload.model_dump()
        data["status"] = "pending"
        item = unit_of_work.refunds.add(fields=data)
        unit_of_work.commit()
        return success_response(_refund_data(item), request, status_code=201)

    @application.get("/api/v1/refunds/{id}", tags=["Billing"])
    def get_refund(
        refund_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.refunds.get_for_user(user_id=current_user.id, refund_id=refund_id)
        if item is None:
            raise _not_found("Refund")
        return success_response(_refund_data(item), request)

    @application.put("/api/v1/refunds/{id}", tags=["Billing"])
    def update_refund(
        refund_id: Annotated[UUID, Path(alias="id")],
        payload: RefundUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if unit_of_work.refunds.get_for_user(user_id=current_user.id, refund_id=refund_id) is None:
            raise _not_found("Refund")
        item = unit_of_work.refunds.update(
            refund_id=refund_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_refund_data(item), request)

    @application.delete("/api/v1/refunds/{id}", tags=["Billing"])
    def delete_refund(
        refund_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if unit_of_work.refunds.get_for_user(user_id=current_user.id, refund_id=refund_id) is None:
            raise _not_found("Refund")
        unit_of_work.refunds.soft_delete(refund_id=refund_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/provider-disputes", tags=["Billing"])
    def list_provider_disputes(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _provider_dispute_data(x)
                    for x in unit_of_work.provider_disputes.list_for_user(user_id=current_user.id)
                ]
            },
            request,
        )

    @application.post("/api/v1/provider-disputes", tags=["Billing"])
    def create_provider_dispute(
        payload: ProviderDisputeCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.billing_accounts.get_for_user(
                user_id=current_user.id, account_id=payload.billing_account_id
            )
            is None
        ):
            raise _not_found("Billing account")
        data = payload.model_dump()
        data["status"] = "open"
        data["payload"] = {}
        item = unit_of_work.provider_disputes.add(fields=data)
        unit_of_work.commit()
        return success_response(_provider_dispute_data(item), request, status_code=201)

    @application.get("/api/v1/provider-disputes/{id}", tags=["Billing"])
    def get_provider_dispute(
        dispute_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.provider_disputes.get_for_user(
            user_id=current_user.id, dispute_id=dispute_id
        )
        if item is None:
            raise _not_found("Provider dispute")
        return success_response(_provider_dispute_data(item), request)

    @application.put("/api/v1/provider-disputes/{id}", tags=["Billing"])
    def update_provider_dispute(
        dispute_id: Annotated[UUID, Path(alias="id")],
        payload: ProviderDisputeUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.provider_disputes.get_for_user(
                user_id=current_user.id, dispute_id=dispute_id
            )
            is None
        ):
            raise _not_found("Provider dispute")
        item = unit_of_work.provider_disputes.update(
            dispute_id=dispute_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_provider_dispute_data(item), request)

    @application.delete("/api/v1/provider-disputes/{id}", tags=["Billing"])
    def delete_provider_dispute(
        dispute_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.provider_disputes.get_for_user(
                user_id=current_user.id, dispute_id=dispute_id
            )
            is None
        ):
            raise _not_found("Provider dispute")
        unit_of_work.provider_disputes.soft_delete(dispute_id=dispute_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/coupons", tags=["Billing"])
    def list_coupons(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        return success_response(
            {"items": [_coupon_data(x) for x in unit_of_work.coupons.list()]}, request
        )

    @application.post("/api/v1/coupons", tags=["Billing"])
    def create_coupon(
        payload: CouponCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        data = payload.model_dump()
        data["created_by"] = current_user.id
        item = unit_of_work.coupons.add(fields=data)
        unit_of_work.commit()
        return success_response(_coupon_data(item), request, status_code=201)

    @application.get("/api/v1/coupons/{id}", tags=["Billing"])
    def get_coupon(
        coupon_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.coupons.get(coupon_id=coupon_id)
        if item is None:
            raise _not_found("Coupon")
        return success_response(_coupon_data(item), request)

    @application.put("/api/v1/coupons/{id}", tags=["Billing"])
    def update_coupon(
        coupon_id: Annotated[UUID, Path(alias="id")],
        payload: CouponUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.coupons.get(coupon_id=coupon_id) is None:
            raise _not_found("Coupon")
        item = unit_of_work.coupons.update(
            coupon_id=coupon_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_coupon_data(item), request)

    @application.delete("/api/v1/coupons/{id}", tags=["Billing"])
    def delete_coupon(
        coupon_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.coupons.get(coupon_id=coupon_id) is None:
            raise _not_found("Coupon")
        unit_of_work.coupons.soft_delete(coupon_id=coupon_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/credit-packages", tags=["Billing"])
    def list_credit_packages(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        return success_response(
            {"items": [_credit_package_data(x) for x in unit_of_work.credit_packages.list()]},
            request,
        )

    @application.post("/api/v1/credit-packages", tags=["Billing"])
    def create_credit_package(
        payload: CreditPackageCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.credit_packages.add(fields=payload.model_dump())
        unit_of_work.commit()
        return success_response(_credit_package_data(item), request, status_code=201)

    @application.get("/api/v1/credit-packages/{id}", tags=["Billing"])
    def get_credit_package(
        package_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.credit_packages.get(package_id=package_id)
        if item is None:
            raise _not_found("Credit package")
        return success_response(_credit_package_data(item), request)

    @application.put("/api/v1/credit-packages/{id}", tags=["Billing"])
    def update_credit_package(
        package_id: Annotated[UUID, Path(alias="id")],
        payload: CreditPackageUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.credit_packages.get(package_id=package_id) is None:
            raise _not_found("Credit package")
        item = unit_of_work.credit_packages.update(
            package_id=package_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_credit_package_data(item), request)

    @application.delete("/api/v1/credit-packages/{id}", tags=["Billing"])
    def delete_credit_package(
        package_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.credit_packages.get(package_id=package_id) is None:
            raise _not_found("Credit package")
        unit_of_work.credit_packages.soft_delete(package_id=package_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/plans", tags=["Billing"])
    def list_plans(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        return success_response(
            {"items": [_plan_data(item) for item in unit_of_work.plans.list()]}, request
        )

    @application.post("/api/v1/plans", tags=["Billing"])
    def create_plan(
        payload: PlanCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.plans.add(**payload.model_dump())
        unit_of_work.commit()
        return success_response(_plan_data(item), request, status_code=201)

    @application.get("/api/v1/plans/{id}", tags=["Billing"])
    def get_plan(
        plan_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.plans.get(plan_id=plan_id)
        if item is None:
            raise _not_found("Plan")
        return success_response(_plan_data(item), request)

    @application.put("/api/v1/plans/{id}", tags=["Billing"])
    def update_plan(
        plan_id: Annotated[UUID, Path(alias="id")],
        payload: PlanUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.plans.get(plan_id=plan_id) is None:
            raise _not_found("Plan")
        item = unit_of_work.plans.update(
            plan_id=plan_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_plan_data(item), request)

    @application.delete("/api/v1/plans/{id}", tags=["Billing"])
    def delete_plan(
        plan_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.plans.get(plan_id=plan_id) is None:
            raise _not_found("Plan")
        unit_of_work.plans.soft_delete(plan_id=plan_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/plan-items", tags=["Billing"])
    def list_plan_items(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        plan_id: UUID | None = None,
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        items = unit_of_work.plan_items.list(plan_id=plan_id)
        return success_response({"items": [_plan_item_data(item) for item in items]}, request)

    @application.post("/api/v1/plan-items", tags=["Billing"])
    def create_plan_item(
        payload: PlanItemCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.plans.get(plan_id=payload.plan_id) is None:
            raise _not_found("Plan")
        item = unit_of_work.plan_items.add(**payload.model_dump())
        unit_of_work.commit()
        return success_response(_plan_item_data(item), request, status_code=201)

    @application.get("/api/v1/plan-items/{id}", tags=["Billing"])
    def get_plan_item(
        item_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        item = unit_of_work.plan_items.get(item_id=item_id)
        if item is None:
            raise _not_found("Plan item")
        return success_response(_plan_item_data(item), request)

    @application.put("/api/v1/plan-items/{id}", tags=["Billing"])
    def update_plan_item(
        item_id: Annotated[UUID, Path(alias="id")],
        payload: PlanItemUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.plan_items.get(item_id=item_id) is None:
            raise _not_found("Plan item")
        item = unit_of_work.plan_items.update(
            item_id=item_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_plan_item_data(item), request)

    @application.delete("/api/v1/plan-items/{id}", tags=["Billing"])
    def delete_plan_item(
        item_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_global_billing_admin(current_user)
        if unit_of_work.plan_items.get(item_id=item_id) is None:
            raise _not_found("Plan item")
        unit_of_work.plan_items.soft_delete(item_id=item_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/notification-recipients", tags=["Notifications"])
    def list_notification_recipients(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _notification_recipient_data(x)
                    for x in unit_of_work.notification_recipients.list_for_user(
                        user_id=current_user.id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/notification-recipients", tags=["Notifications"])
    def create_notification_recipient(
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        payload["user_id"] = current_user.id
        item = unit_of_work.notification_recipients.add(fields=payload)
        unit_of_work.commit()
        return success_response(_notification_recipient_data(item), request, status_code=201)

    @application.get("/api/v1/notification-recipients/{id}", tags=["Notifications"])
    def get_notification_recipient(
        recipient_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.notification_recipients.get_for_user(
            user_id=current_user.id, recipient_id=recipient_id
        )
        if item is None:
            raise _not_found("Notification recipient")
        return success_response(_notification_recipient_data(item), request)

    @application.put("/api/v1/notification-recipients/{id}", tags=["Notifications"])
    def update_notification_recipient(
        recipient_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.notification_recipients.get_for_user(
                user_id=current_user.id, recipient_id=recipient_id
            )
            is None
        ):
            raise _not_found("Notification recipient")
        item = unit_of_work.notification_recipients.update(
            recipient_id=recipient_id, fields=payload
        )
        unit_of_work.commit()
        return success_response(_notification_recipient_data(item), request)

    @application.delete("/api/v1/notification-recipients/{id}", tags=["Notifications"])
    def delete_notification_recipient(
        recipient_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.notification_recipients.get_for_user(
                user_id=current_user.id, recipient_id=recipient_id
            )
            is None
        ):
            raise _not_found("Notification recipient")
        unit_of_work.notification_recipients.soft_delete(recipient_id=recipient_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/workspace-invite-usages", tags=["Workspaces"])
    def list_workspace_invite_usages(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
    ) -> JSONResponse:
        return success_response(
            {
                "items": [
                    _workspace_invite_usage_data(x)
                    for x in unit_of_work.workspace_invite_usages.list_for_user(
                        user_id=current_user.id, workspace_id=workspace_id
                    )
                ]
            },
            request,
        )

    @application.post("/api/v1/workspace-invite-usages", tags=["Workspaces"])
    def create_workspace_invite_usage(
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        payload["user_id"] = current_user.id
        item = unit_of_work.workspace_invite_usages.add(fields=payload)
        unit_of_work.commit()
        return success_response(_workspace_invite_usage_data(item), request, status_code=201)

    @application.get("/api/v1/workspace-invite-usages/{id}", tags=["Workspaces"])
    def get_workspace_invite_usage(
        usage_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.workspace_invite_usages.get_for_user(
            user_id=current_user.id, usage_id=usage_id
        )
        if item is None:
            raise _not_found("Workspace invite usage")
        return success_response(_workspace_invite_usage_data(item), request)

    @application.put("/api/v1/workspace-invite-usages/{id}", tags=["Workspaces"])
    def update_workspace_invite_usage(
        usage_id: Annotated[UUID, Path(alias="id")],
        payload: dict[str, Any],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.workspace_invite_usages.get_for_user(
                user_id=current_user.id, usage_id=usage_id
            )
            is None
        ):
            raise _not_found("Workspace invite usage")
        item = unit_of_work.workspace_invite_usages.update(usage_id=usage_id, fields=payload)
        unit_of_work.commit()
        return success_response(_workspace_invite_usage_data(item), request)

    @application.delete("/api/v1/workspace-invite-usages/{id}", tags=["Workspaces"])
    def delete_workspace_invite_usage(
        usage_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.workspace_invite_usages.get_for_user(
                user_id=current_user.id, usage_id=usage_id
            )
            is None
        ):
            raise _not_found("Workspace invite usage")
        unit_of_work.workspace_invite_usages.soft_delete(usage_id=usage_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/notifications", tags=["Notifications"])
    def list_notifications(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
        workspace_id: UUID | None = None,
    ) -> JSONResponse:
        items = unit_of_work.notifications.list_for_user(
            user_id=current_user.id, workspace_id=workspace_id
        )
        return success_response({"items": [_notification_data(item) for item in items]}, request)

    @application.post("/api/v1/notifications", tags=["Notifications"])
    def create_notification(
        payload: NotificationCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=payload.workspace_id
        )
        item = unit_of_work.notifications.add(
            workspace_id=payload.workspace_id,
            created_by=current_user.id,
            type=payload.type,
            title=payload.title,
            body=payload.body,
            payload=payload.payload,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
        )
        unit_of_work.commit()
        return success_response(_notification_data(item), request, status_code=201)

    @application.get("/api/v1/notifications/{id}", tags=["Notifications"])
    def get_notification(
        notification_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.notifications.get_for_user(
            user_id=current_user.id, notification_id=notification_id
        )
        if item is None:
            raise _not_found("Notification")
        return success_response(_notification_data(item), request)

    @application.put("/api/v1/notifications/{id}", tags=["Notifications"])
    def update_notification(
        notification_id: Annotated[UUID, Path(alias="id")],
        payload: NotificationUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.notifications.get_for_user(
            user_id=current_user.id, notification_id=notification_id
        )
        if existing is None:
            raise _not_found("Notification")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        item = unit_of_work.notifications.update(
            notification_id=notification_id, fields=payload.model_dump(exclude_unset=True)
        )
        unit_of_work.commit()
        return success_response(_notification_data(item), request)

    @application.delete("/api/v1/notifications/{id}", tags=["Notifications"])
    def delete_notification(
        notification_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        existing = unit_of_work.notifications.get_for_user(
            user_id=current_user.id, notification_id=notification_id
        )
        if existing is None:
            raise _not_found("Notification")
        _require_workspace_write(
            unit_of_work, user_id=current_user.id, workspace_id=existing.workspace_id
        )
        unit_of_work.notifications.soft_delete(notification_id=notification_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/user-devices", tags=["Notifications"])
    def list_user_devices(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        items = unit_of_work.user_devices.list_for_user(user_id=current_user.id)
        return success_response({"items": [_user_device_data(item) for item in items]}, request)

    @application.post("/api/v1/user-devices", tags=["Notifications"])
    def create_user_device(
        payload: UserDeviceCreateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.user_devices.add(
            user_id=current_user.id, platform=payload.platform, fcm_token=payload.fcm_token
        )
        unit_of_work.commit()
        return success_response(_user_device_data(item), request, status_code=201)

    @application.get("/api/v1/user-devices/{id}", tags=["Notifications"])
    def get_user_device(
        device_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.user_devices.get_for_user(user_id=current_user.id, device_id=device_id)
        if item is None:
            raise _not_found("User device")
        return success_response(_user_device_data(item), request)

    @application.put("/api/v1/user-devices/{id}", tags=["Notifications"])
    def update_user_device(
        device_id: Annotated[UUID, Path(alias="id")],
        payload: UserDeviceUpdateRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.user_devices.get_for_user(user_id=current_user.id, device_id=device_id)
            is None
        ):
            raise _not_found("User device")
        item = unit_of_work.user_devices.update(
            user_id=current_user.id,
            device_id=device_id,
            fields=payload.model_dump(exclude_unset=True),
        )
        unit_of_work.commit()
        return success_response(_user_device_data(item), request)

    @application.delete("/api/v1/user-devices/{id}", tags=["Notifications"])
    def delete_user_device(
        device_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.user_devices.get_for_user(user_id=current_user.id, device_id=device_id)
            is None
        ):
            raise _not_found("User device")
        unit_of_work.user_devices.soft_delete(user_id=current_user.id, device_id=device_id)
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/notification-preferences", tags=["Notifications"])
    def list_notification_preferences(
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        items = unit_of_work.notification_preferences.list_for_user(user_id=current_user.id)
        return success_response(
            {"items": [_notification_preference_data(item) for item in items]}, request
        )

    @application.post("/api/v1/notification-preferences", tags=["Notifications"])
    def create_notification_preference(
        payload: NotificationPreferenceRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.notification_preferences.add(
            user_id=current_user.id,
            type=payload.type,
            channel=payload.channel,
            is_enabled=payload.is_enabled,
        )
        unit_of_work.commit()
        return success_response(_notification_preference_data(item), request, status_code=201)

    @application.get("/api/v1/notification-preferences/{id}", tags=["Notifications"])
    def get_notification_preference(
        preference_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        item = unit_of_work.notification_preferences.get_for_user(
            user_id=current_user.id, preference_id=preference_id
        )
        if item is None:
            raise _not_found("Notification preference")
        return success_response(_notification_preference_data(item), request)

    @application.put("/api/v1/notification-preferences/{id}", tags=["Notifications"])
    def update_notification_preference(
        preference_id: Annotated[UUID, Path(alias="id")],
        payload: NotificationPreferenceRequest,
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.notification_preferences.get_for_user(
                user_id=current_user.id, preference_id=preference_id
            )
            is None
        ):
            raise _not_found("Notification preference")
        item = unit_of_work.notification_preferences.update(
            user_id=current_user.id,
            preference_id=preference_id,
            fields=payload.model_dump(exclude_unset=True),
        )
        unit_of_work.commit()
        return success_response(_notification_preference_data(item), request)

    @application.delete("/api/v1/notification-preferences/{id}", tags=["Notifications"])
    def delete_notification_preference(
        preference_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        if (
            unit_of_work.notification_preferences.get_for_user(
                user_id=current_user.id, preference_id=preference_id
            )
            is None
        ):
            raise _not_found("Notification preference")
        unit_of_work.notification_preferences.soft_delete(
            user_id=current_user.id, preference_id=preference_id
        )
        unit_of_work.commit()
        return success_response({"deleted": True}, request)

    @application.get("/api/v1/generated-images/{id}", tags=["Images"])
    def get_generated_image(
        image_id: Annotated[UUID, Path(alias="id")],
        request: Request,
        current_user: Annotated[UserRecord, Depends(get_current_user)],
        unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
    ) -> JSONResponse:
        image = unit_of_work.generated_images.get_for_user(
            user_id=current_user.id, image_id=image_id
        )
        if image is None:
            raise _not_found("Generated image")
        return success_response(_generated_image_data(image), request)

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
        brand_assets = getattr(unit_of_work, "brand_assets", None)
        brand_asset = (
            brand_assets.get_for_user(user_id=current_user.id, asset_id=asset_id)
            if brand_assets is not None
            else None
        )
        if brand_asset is not None:
            return success_response(_brand_asset_data(brand_asset), request)
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
        generated_images = getattr(unit_of_work, "generated_images", None)
        generated_image = (
            generated_images.get_for_user(user_id=current_user.id, image_id=job_id)
            if generated_images is not None
            else None
        )
        if generated_image is not None:
            return success_response(_generated_image_data(generated_image), request)
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
        planning_id: UUID | None = None,
        q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        content_type: Annotated[
            str | None,
            Query(alias="type", pattern="^(IMAGE|TEXT)$"),
        ] = None,
    ) -> JSONResponse:
        if planning_id is not None:
            structures = unit_of_work.post_structures.list_for_user(
                user_id=current_user.id,
                planning_id=planning_id,
                page=_page_request(page, limit, sort),
            )
            return success_response(_page_data(structures, _post_structure_data), request)
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
