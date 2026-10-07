from types import TracebackType
from typing import Protocol, Self

from creator.repositories import (
    AgentWorkflowRepository,
    AssetRepository,
    BillingAccountRepository,
    BillingAddressRepository,
    BillingPaymentMethodRepository,
    BrandAssetRepository,
    BrandColorRepository,
    BrandRepository,
    BrandSettingsRepository,
    CampaignRepository,
    ChargeRepository,
    ContentRepository,
    CouponRedemptionRepository,
    CouponRepository,
    CreditPackageRepository,
    DesignStructureRepository,
    GeneratedImageRepository,
    GenerationRepository,
    ImageGenerationRepository,
    InvoiceRepository,
    NotificationPreferenceRepository,
    NotificationRecipientRepository,
    NotificationRepository,
    OrderRepository,
    OutboxRepository,
    PersonaRepository,
    PlanItemRepository,
    PlanningRepository,
    PlanRepository,
    PostStructureRepository,
    ProjectRepository,
    ProviderCustomerRepository,
    ProviderDisputeRepository,
    ProviderIdempotencyKeyRepository,
    ProviderSubscriptionRepository,
    ProviderWebhookEventRepository,
    RefundRepository,
    SettingsRepository,
    SubscriptionHistoryRepository,
    SubscriptionRepository,
    UserDeviceRepository,
    UserRepository,
    WorkspaceCreditTransactionRepository,
    WorkspaceInviteRepository,
    WorkspaceInviteUsageRepository,
    WorkspaceRepository,
)


class UnitOfWork(Protocol):
    users: UserRepository
    settings: SettingsRepository
    workspaces: WorkspaceRepository
    brands: BrandRepository
    projects: ProjectRepository
    contents: ContentRepository
    generations: GenerationRepository
    assets: AssetRepository
    brand_settings: BrandSettingsRepository
    image_generations: ImageGenerationRepository
    agent_workflows: AgentWorkflowRepository
    campaigns: CampaignRepository
    post_structures: PostStructureRepository
    planning: PlanningRepository
    personas: PersonaRepository
    generated_images: GeneratedImageRepository
    brand_assets: BrandAssetRepository
    outbox: OutboxRepository
    user_devices: UserDeviceRepository
    notification_preferences: NotificationPreferenceRepository
    notifications: NotificationRepository
    notification_recipients: NotificationRecipientRepository
    plans: PlanRepository
    plan_items: PlanItemRepository
    billing_accounts: BillingAccountRepository
    subscriptions: SubscriptionRepository
    invoices: InvoiceRepository
    charges: ChargeRepository
    workspace_invites: WorkspaceInviteRepository
    billing_addresses: BillingAddressRepository
    billing_payment_methods: BillingPaymentMethodRepository
    coupons: CouponRepository
    credit_packages: CreditPackageRepository
    orders: OrderRepository
    coupon_redemptions: CouponRedemptionRepository
    workspace_credit_transactions: WorkspaceCreditTransactionRepository
    refunds: RefundRepository
    provider_disputes: ProviderDisputeRepository
    provider_customers: ProviderCustomerRepository
    provider_subscriptions: ProviderSubscriptionRepository
    provider_webhook_events: ProviderWebhookEventRepository
    provider_idempotency_keys: ProviderIdempotencyKeyRepository
    design_structures: DesignStructureRepository
    brand_colors: BrandColorRepository
    subscription_history: SubscriptionHistoryRepository
    workspace_invite_usages: WorkspaceInviteUsageRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
