import pytest

from creator.api.dtos import (
    CampaignCreateRequest,
    NotificationCreateRequest,
    PlanCreateRequest,
)
from creator.infrastructure import models
from creator.infrastructure.schema_manifest import LEGACY_TABLES, PDF_TABLES

EXPECTED_DIAGRAM_TABLES = {
    "plans",
    "plan_items",
    "billing_accounts",
    "billing_addresses",
    "billing_payment_methods",
    "subscriptions",
    "subscription_history",
    "invoices",
    "charges",
    "refunds",
    "provider_customers",
    "provider_subscriptions",
    "provider_webhook_events",
    "provider_idempotency_keys",
    "provider_disputes",
    "campaigns",
    "personas",
    "planning",
    "post_structure",
    "design_structure",
    "generated_image",
    "notifications",
    "notification_recipients",
    "user_devices",
    "notification_preferences",
    "workspace_invites",
    "workspace_invite_usages",
    "brand_colors",
    "brand_assets",
    "coupons",
    "credit_packages",
    "orders",
    "coupon_redemptions",
    "workspace_credit_transactions",
}


def test_pdf_schema_tables_are_registered_in_metadata() -> None:
    assert EXPECTED_DIAGRAM_TABLES <= set(models.Base.metadata.tables)
    assert PDF_TABLES <= set(models.Base.metadata.tables)
    assert LEGACY_TABLES <= set(models.Base.metadata.tables)


def test_core_columns_match_pdf_lengths() -> None:
    users = models.Base.metadata.tables["users"]
    workspaces = models.Base.metadata.tables["workspaces"]
    assert users.c.email.type.length == 50
    assert users.c.display_name.type.length == 50
    assert workspaces.c.name.type.length == 50


def test_marketing_columns_match_pdf_names() -> None:
    planning = models.Base.metadata.tables["planning"]
    post_structure = models.Base.metadata.tables["post_structure"]
    brand_colors = models.Base.metadata.tables["brand_colors"]
    assert {"persona_name", "planning_info", "planning_start_period"} <= set(planning.c.keys())
    assert {
        "post_title",
        "post_objective",
        "content_format",
        "art_ratio",
        "art_resolution",
    } <= set(post_structure.c.keys())
    assert "title" not in post_structure.c
    assert "format" not in post_structure.c
    generated_image = models.Base.metadata.tables["generated_image"]
    assert "image_status" in generated_image.c
    assert "status" not in generated_image.c
    assert {
        "brand_segment",
        "brand_promise",
        "brand_values",
        "brand_main_hashtags",
        "brand_goals",
        "brand_indicators",
        "brand_inspirations",
        "brand_restrictions",
    } <= set(brand_colors.c.keys())


def test_new_dtos_reject_unknown_fields() -> None:
    assert PlanCreateRequest(code="pro", type="PRO", name="Pro").is_active is True
    assert (
        CampaignCreateRequest(
            workspace_id="00000000-0000-0000-0000-000000000001",
            name="Launch",
        ).name
        == "Launch"
    )
    assert (
        NotificationCreateRequest(
            workspace_id="00000000-0000-0000-0000-000000000001",
            type="SYSTEM",
            title="Hi",
            body="Hello",
        ).payload
        == {}
    )
    with pytest.raises(ValueError):
        CampaignCreateRequest(
            workspace_id="00000000-0000-0000-0000-000000000001",
            name="Launch",
            unexpected=True,
        )
    with pytest.raises(ValueError):
        NotificationCreateRequest(
            workspace_id="00000000-0000-0000-0000-000000000001",
            type="SYSTEM",
            title="Hi",
            body="Hello",
            created_by="00000000-0000-0000-0000-000000000002",
        )
