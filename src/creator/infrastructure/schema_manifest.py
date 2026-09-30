"""Explicit schema inventory used during the PDF-to-code migration."""

PDF_TABLES = frozenset(
    {
        "users",
        "workspaces",
        "workspace_memberships",
        "workspace_invites",
        "workspace_invite_usages",
        "brands",
        "brand_colors",
        "brand_assets",
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
        "coupons",
        "coupon_redemptions",
        "credit_packages",
        "orders",
        "workspace_credit_transactions",
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
    }
)

# These tables are still required by the current generation repositories. They
# must not be silently dropped until those repositories are migrated to the
# post_structure/design_structure/generated_image workflow.
LEGACY_TABLES = frozenset(
    {
        "settings",
        "brand_settings",
        "projects",
        "contents",
        "generations",
        "assets",
        "generation_jobs",
        "generation_job_status_events",
        "images",
        "agent_workflow_runs",
        "agent_workflow_steps",
    }
)
