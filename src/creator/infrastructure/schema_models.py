"""Models for the relational schema represented by Creator DB.pdf.

This module contains the billing, marketing-planning and notification slices.
The generation models remain in ``models.py`` because their repositories are
already part of the application boundary.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from creator.infrastructure.db import Base

uuid_pk = PGUUID(as_uuid=True)
timestamp = DateTime(timezone=True)


class WorkspaceMembersRole(StrEnum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class InviteType(StrEnum):
    EMAIL = "EMAIL"
    LINK = "LINK"


class InviteStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"


class SubscriptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    TRIALING = "TRIALING"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class ProviderSubscriptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELED = "CANCELED"
    FUTURE = "FUTURE"


class PaymentMethodType(StrEnum):
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    BOLETO = "BOLETO"
    PIX = "PIX"


class PlanType(StrEnum):
    FREE = "FREE"
    STARTER = "STARTER"
    PRO = "PRO"
    STUDIO = "STUDIO"
    ENTERPRISE = "ENTERPRISE"


class CampaignVoice(StrEnum):
    INSPIRATIONAL = "INSPIRATIONAL"
    MOTIVATIONAL = "MOTIVATIONAL"
    PROFESSIONAL = "PROFESSIONAL"
    CASUAL = "CASUAL"
    ELEGANT = "ELEGANT"
    MODERN = "MODERN"
    TRADITIONAL = "TRADITIONAL"
    FUN = "FUN"
    SERIOUS = "SERIOUS"


class PostStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ContentFormat(StrEnum):
    IMAGE = "IMAGE"
    CAROUSEL = "CAROUSEL"
    STORIES = "STORIES"


class ArtRatio(StrEnum):
    RATIO_4_5 = "RATIO_4_5"
    RATIO_1_1 = "RATIO_1_1"
    RATIO_9_16 = "RATIO_9_16"
    RATIO_16_9 = "RATIO_16_9"


class ArtResolution(StrEnum):
    HD_1080X1080 = "HD_1080X1080"
    HD_1080X1350 = "HD_1080X1350"
    FULL_HD_1080X1920 = "FULL_HD_1080X1920"
    FULL_HD_1920X1080 = "FULL_HD_1920X1080"


class ImageStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class SchemaRow:
    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        timestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        timestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(timestamp)


class Plan(SchemaRow, Base):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))


class PlanItem(SchemaRow, Base):
    __tablename__ = "plan_items"
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    gateway_id: Mapped[str | None] = mapped_column(String(128))
    provider_plan_item_id: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    cycles: Mapped[int | None] = mapped_column(Integer)
    pricing_scheme_type: Mapped[str | None] = mapped_column(String(20))
    price_cents: Mapped[int] = mapped_column(nullable=False)
    price_brackets: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str | None] = mapped_column(String(20))


class BillingAccount(SchemaRow, Base):
    __tablename__ = "billing_accounts"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    payer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    document: Mapped[str | None] = mapped_column(String(50))
    document_type: Mapped[str | None] = mapped_column(String(10))
    company_name: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(20))
    provider_customer_id: Mapped[str | None] = mapped_column(String(64))
    provider_customer_code: Mapped[str | None] = mapped_column(String(52))
    delinquent: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Subscription(SchemaRow, Base):
    __tablename__ = "subscriptions"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_status: Mapped[str | None] = mapped_column(String(20))
    provider_subscription_id: Mapped[str | None] = mapped_column(String(64))
    provider_code: Mapped[str | None] = mapped_column(String(52))
    payment_method: Mapped[str | None] = mapped_column(String(20))
    provider_card_id: Mapped[str | None] = mapped_column(String(64))
    billing_type: Mapped[str | None] = mapped_column(String(20))
    billing_day: Mapped[int | None] = mapped_column(Integer)
    interval: Mapped[str | None] = mapped_column(String(10))
    interval_count: Mapped[int | None] = mapped_column(Integer)
    installments: Mapped[int | None] = mapped_column(Integer)
    minimum_price_cents: Mapped[int | None] = mapped_column()
    statement_descriptor: Mapped[str | None] = mapped_column(String(22))
    trial_period_days: Mapped[int | None] = mapped_column(Integer)
    current_period_start: Mapped[datetime | None] = mapped_column(timestamp)
    current_period_end: Mapped[datetime | None] = mapped_column(timestamp)
    next_billing_at: Mapped[datetime | None] = mapped_column(timestamp)
    start_at: Mapped[datetime | None] = mapped_column(timestamp)
    canceled_at: Mapped[datetime | None] = mapped_column(timestamp)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Invoice(SchemaRow, Base):
    __tablename__ = "invoices"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    subscription_id: Mapped[UUID | None] = mapped_column(ForeignKey("subscriptions.id"))
    provider_invoice_id: Mapped[str | None] = mapped_column(String(64))
    provider_charge_id: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(2048))
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    total_discount_cents: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    total_increment_cents: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(20))
    installments: Mapped[int | None] = mapped_column(Integer)
    billing_at: Mapped[datetime | None] = mapped_column(timestamp)
    seen_at: Mapped[datetime | None] = mapped_column(timestamp)
    due_at: Mapped[datetime | None] = mapped_column(timestamp)
    period_start: Mapped[datetime | None] = mapped_column(timestamp)
    period_end: Mapped[datetime | None] = mapped_column(timestamp)
    canceled_at: Mapped[datetime | None] = mapped_column(timestamp)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Charge(SchemaRow, Base):
    __tablename__ = "charges"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id"))
    provider_charge_id: Mapped[str | None] = mapped_column(String(64))
    provider_card_id: Mapped[str | None] = mapped_column(String(64))
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Campaign(SchemaRow, Base):
    __tablename__ = "campaigns"
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    target_audience: Mapped[str | None] = mapped_column(String(300))
    objectives: Mapped[str | None] = mapped_column(String(400))
    voice: Mapped[str | None] = mapped_column(String(20))
    start_at: Mapped[datetime | None] = mapped_column(timestamp)
    end_at: Mapped[datetime | None] = mapped_column(timestamp)


class Persona(SchemaRow, Base):
    __tablename__ = "personas"
    brand_id: Mapped[UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(10))
    main_goal: Mapped[str | None] = mapped_column(String(60))
    challenge: Mapped[str | None] = mapped_column(String(50))
    interest: Mapped[str | None] = mapped_column(String(200))
    routine: Mapped[str | None] = mapped_column(String(300))
    journey: Mapped[str | None] = mapped_column(String(250))
    trigger: Mapped[str | None] = mapped_column(String(200))


class Planning(SchemaRow, Base):
    __tablename__ = "planning"
    brand_id: Mapped[UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    persona_id: Mapped[UUID] = mapped_column(ForeignKey("personas.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    persona_name: Mapped[str | None] = mapped_column(String(30))
    persona_age: Mapped[int | None] = mapped_column(Integer)
    persona_gender: Mapped[str | None] = mapped_column(String(10))
    persona_main_goal: Mapped[str | None] = mapped_column(String(60))
    persona_challenge: Mapped[str | None] = mapped_column(String(50))
    persona_interest: Mapped[str | None] = mapped_column(String(200))
    persona_routine: Mapped[str | None] = mapped_column(String(300))
    persona_journey: Mapped[str | None] = mapped_column(String(250))
    persona_trigger: Mapped[str | None] = mapped_column(String(200))
    planning_info: Mapped[str | None] = mapped_column(String(400))
    planning_static_amount: Mapped[int | None] = mapped_column(Integer)
    planning_carousel_amount: Mapped[int | None] = mapped_column(Integer)
    planning_stories_amount: Mapped[int | None] = mapped_column(Integer)
    planning_special_dates: Mapped[str | None] = mapped_column(String(50))
    planning_start_period: Mapped[datetime | None] = mapped_column(timestamp)
    planning_end_period: Mapped[datetime | None] = mapped_column(timestamp)


class PostStructure(SchemaRow, Base):
    __tablename__ = "post_structure"
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    planning_id: Mapped[UUID] = mapped_column(ForeignKey("planning.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    post_title: Mapped[str | None] = mapped_column(String(100))
    post_objective: Mapped[str | None] = mapped_column(String(300))
    post_big_idea: Mapped[str | None] = mapped_column(String(150))
    post_main_message: Mapped[str | None] = mapped_column(String(150))
    post_headline: Mapped[str | None] = mapped_column(String(50))
    image_cta: Mapped[str | None] = mapped_column(String(30))
    art_guiding: Mapped[str | None] = mapped_column(String(1000))
    post_status: Mapped[str | None] = mapped_column(String(20))
    content_format: Mapped[str | None] = mapped_column(String(20))
    art_ratio: Mapped[str | None] = mapped_column(String(20))
    art_resolution: Mapped[str | None] = mapped_column(String(30))


class DesignStructure(SchemaRow, Base):
    __tablename__ = "design_structure"
    post_structure_id: Mapped[UUID] = mapped_column(ForeignKey("post_structure.id"), nullable=False)


class GeneratedImage(SchemaRow, Base):
    __tablename__ = "generated_image"
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    design_structure_id: Mapped[UUID] = mapped_column(
        ForeignKey("design_structure.id"), nullable=False
    )
    signed_url: Mapped[str | None] = mapped_column(String(2048))
    size: Mapped[str | None] = mapped_column(String(10))
    resolution: Mapped[str | None] = mapped_column(String(30))
    image_ratio: Mapped[str | None] = mapped_column(String(20))
    image_status: Mapped[str | None] = mapped_column(String(20))


class Notification(SchemaRow, Base):
    __tablename__ = "notifications"
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[UUID | None] = mapped_column(uuid_pk)
    dedupe_key: Mapped[str | None] = mapped_column(String(128))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class NotificationRecipient(SchemaRow, Base):
    __tablename__ = "notification_recipients"
    notification_id: Mapped[UUID] = mapped_column(ForeignKey("notifications.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_member_id: Mapped[UUID | None] = mapped_column(ForeignKey("workspace_memberships.id"))
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sent_at: Mapped[datetime | None] = mapped_column(timestamp)
    read_at: Mapped[datetime | None] = mapped_column(timestamp)


class UserDevice(SchemaRow, Base):
    __tablename__ = "user_devices"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(10), nullable=False)
    fcm_token: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    last_seen_at: Mapped[datetime | None] = mapped_column(timestamp)


class NotificationPreference(SchemaRow, Base):
    __tablename__ = "notification_preferences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))


class WorkspaceInvite(SchemaRow, Base):
    __tablename__ = "workspace_invites"
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    max_uses: Mapped[int | None] = mapped_column(Integer)
    uses_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(timestamp)
    last_used_at: Mapped[datetime | None] = mapped_column(timestamp)
    revoked_at: Mapped[datetime | None] = mapped_column(timestamp)


class WorkspaceInviteUsage(SchemaRow, Base):
    __tablename__ = "workspace_invite_usages"
    invite_id: Mapped[UUID] = mapped_column(ForeignKey("workspace_invites.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    member_id: Mapped[UUID | None] = mapped_column(ForeignKey("workspace_memberships.id"))
    used_at: Mapped[datetime] = mapped_column(timestamp, nullable=False, server_default=func.now())


class BrandColor(SchemaRow, Base):
    __tablename__ = "brand_colors"
    brand_id: Mapped[UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    brand_name: Mapped[str | None] = mapped_column(String(30))
    brand_segment: Mapped[str | None] = mapped_column(String(30))
    brand_promise: Mapped[str | None] = mapped_column(String(250))
    brand_values: Mapped[str | None] = mapped_column(String(100))
    brand_main_hashtags: Mapped[str | None] = mapped_column(String(200))
    brand_goals: Mapped[str | None] = mapped_column(String(1800))
    brand_indicators: Mapped[str | None] = mapped_column(String(250))
    brand_inspirations: Mapped[str | None] = mapped_column(String(1500))
    brand_restrictions: Mapped[str | None] = mapped_column(String(200))
    color_name: Mapped[str | None] = mapped_column(String(50))
    hex_code: Mapped[str | None] = mapped_column(String(7))


class BrandAsset(SchemaRow, Base):
    __tablename__ = "brand_assets"
    brand_id: Mapped[UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500))


class Coupon(SchemaRow, Base):
    __tablename__ = "coupons"
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    credits_amount: Mapped[int | None] = mapped_column(Integer)
    applies_to: Mapped[str] = mapped_column(String(30), nullable=False)
    min_purchase_cents: Mapped[int | None] = mapped_column()
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    once_per_workspace: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    redemptions_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    expires_at: Mapped[datetime | None] = mapped_column(timestamp)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    internal_note: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class CreditPackage(SchemaRow, Base):
    __tablename__ = "credit_packages"
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    credits_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))


class Order(SchemaRow, Base):
    __tablename__ = "orders"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    credit_package_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_packages.id"))
    provider_order_id: Mapped[str | None] = mapped_column(String(64))
    subtotal_cents: Mapped[int] = mapped_column(nullable=False)
    discount_cents: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    closed: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class CouponRedemption(SchemaRow, Base):
    __tablename__ = "coupon_redemptions"
    coupon_id: Mapped[UUID] = mapped_column(ForeignKey("coupons.id"), nullable=False)
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id"))
    subscription_id: Mapped[UUID | None] = mapped_column(ForeignKey("subscriptions.id"))
    provider_discount_id: Mapped[str | None] = mapped_column(String(64))
    discount_percent_applied: Mapped[float | None] = mapped_column(Numeric(5, 2))
    discount_amount_cents: Mapped[int | None] = mapped_column()
    credits_applied: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class WorkspaceCreditTransaction(SchemaRow, Base):
    __tablename__ = "workspace_credit_transactions"
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[UUID | None] = mapped_column(uuid_pk)


class BillingAddress(SchemaRow, Base):
    __tablename__ = "billing_addresses"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    street: Mapped[str | None] = mapped_column(String(128))
    number: Mapped[str | None] = mapped_column(String(16))
    complement: Mapped[str | None] = mapped_column(String(64))
    neighborhood: Mapped[str | None] = mapped_column(String(64))
    zip_code: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str | None] = mapped_column(String(16))


class BillingPaymentMethod(SchemaRow, Base):
    __tablename__ = "billing_payment_methods"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    provider_card_id: Mapped[str | None] = mapped_column(String(64))
    holder_name: Mapped[str | None] = mapped_column(String(64))
    holder_document: Mapped[str | None] = mapped_column(String(16))
    card_brand: Mapped[str | None] = mapped_column(String(20))
    card_last_four: Mapped[str | None] = mapped_column(String(4))
    exp_month: Mapped[int | None] = mapped_column(Integer)
    exp_year: Mapped[int | None] = mapped_column(Integer)
    card_type: Mapped[str | None] = mapped_column(String(20))
    card_status: Mapped[str | None] = mapped_column(String(20))
    is_default: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))


class SubscriptionHistory(SchemaRow, Base):
    __tablename__ = "subscription_history"
    subscription_id: Mapped[UUID] = mapped_column(ForeignKey("subscriptions.id"), nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("plans.id"))
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("plans.id"))
    previous_status: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)


class ProviderCustomer(SchemaRow, Base):
    __tablename__ = "provider_customers"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_code: Mapped[str | None] = mapped_column(String(52))
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class ProviderSubscription(SchemaRow, Base):
    __tablename__ = "provider_subscriptions"
    subscription_id: Mapped[UUID] = mapped_column(ForeignKey("subscriptions.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_status: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class ProviderWebhookEvent(SchemaRow, Base):
    __tablename__ = "provider_webhook_events"
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature_verified: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        timestamp, nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(timestamp)


class ProviderIdempotencyKey(SchemaRow, Base):
    __tablename__ = "provider_idempotency_keys"
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_hash: Mapped[str | None] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class Refund(SchemaRow, Base):
    __tablename__ = "refunds"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id"))
    provider_charge_id: Mapped[str | None] = mapped_column(String(64))
    provider_refund_id: Mapped[str | None] = mapped_column(String(64))
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class ProviderDispute(SchemaRow, Base):
    __tablename__ = "provider_disputes"
    billing_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_accounts.id"), nullable=False
    )
    charge_id: Mapped[UUID | None] = mapped_column(ForeignKey("charges.id"))
    provider_dispute_id: Mapped[str | None] = mapped_column(String(64))
    code: Mapped[str | None] = mapped_column(String(52))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(timestamp)
    deadline_at: Mapped[datetime | None] = mapped_column(timestamp)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
