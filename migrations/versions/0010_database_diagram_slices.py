"""Add the billing, planning and notification tables from Creator DB.pdf."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from creator.infrastructure import schema_models

revision: str = "0010_database_diagram_slices"
down_revision: str | None = "0009_agent_image_workflows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = schema_models.Base.metadata.tables
    for table_name in (
        "plans",
        "plan_items",
        "billing_accounts",
        "subscriptions",
        "invoices",
        "charges",
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
        "billing_addresses",
        "billing_payment_methods",
        "subscription_history",
        "provider_customers",
        "provider_subscriptions",
        "provider_webhook_events",
        "provider_idempotency_keys",
        "refunds",
        "provider_disputes",
    ):
        tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in (
        "provider_disputes",
        "refunds",
        "provider_idempotency_keys",
        "provider_webhook_events",
        "provider_subscriptions",
        "provider_customers",
        "subscription_history",
        "billing_payment_methods",
        "billing_addresses",
        "workspace_credit_transactions",
        "coupon_redemptions",
        "orders",
        "credit_packages",
        "coupons",
        "brand_assets",
        "brand_colors",
        "workspace_invite_usages",
        "workspace_invites",
        "notification_preferences",
        "user_devices",
        "notification_recipients",
        "notifications",
        "generated_image",
        "design_structure",
        "post_structure",
        "planning",
        "personas",
        "campaigns",
        "charges",
        "invoices",
        "subscriptions",
        "billing_accounts",
        "plan_items",
        "plans",
    ):
        sa.Table(table_name, sa.MetaData()).drop(bind=bind, checkfirst=True)
