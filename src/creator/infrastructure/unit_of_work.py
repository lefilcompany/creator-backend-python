from __future__ import annotations

from collections.abc import Callable, Generator
from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from creator.domain.exceptions import PersistenceError
from creator.infrastructure.billing_lifecycle_repositories import (
    SqlAlchemyChargeRepository,
    SqlAlchemyInvoiceRepository,
    SqlAlchemySubscriptionRepository,
)
from creator.infrastructure.billing_profile_repositories import (
    SqlAlchemyBillingAddressRepository,
    SqlAlchemyBillingPaymentMethodRepository,
)
from creator.infrastructure.billing_repositories import (
    SqlAlchemyBillingAccountRepository,
    SqlAlchemyPlanItemRepository,
    SqlAlchemyPlanRepository,
)
from creator.infrastructure.brand_color_repositories import SqlAlchemyBrandColorRepository
from creator.infrastructure.catalog_repositories import (
    SqlAlchemyCouponRepository,
    SqlAlchemyCreditPackageRepository,
)
from creator.infrastructure.commerce_repositories import (
    SqlAlchemyCouponRedemptionRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyWorkspaceCreditTransactionRepository,
)
from creator.infrastructure.db import SessionLocal
from creator.infrastructure.design_repositories import SqlAlchemyDesignStructureRepository
from creator.infrastructure.dtos import (
    SqlAlchemyAgentWorkflowRepository,
    SqlAlchemyAssetRepository,
    SqlAlchemyBrandRepository,
    SqlAlchemyBrandSettingsRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGenerationRepository,
    SqlAlchemyImageGenerationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
    map_sqlalchemy_error,
)
from creator.infrastructure.invite_usage_repositories import (
    SqlAlchemyWorkspaceInviteUsageRepository,
)
from creator.infrastructure.notification_repositories import (
    SqlAlchemyNotificationPreferenceRepository,
    SqlAlchemyNotificationRecipientRepository,
    SqlAlchemyNotificationRepository,
    SqlAlchemyUserDeviceRepository,
)
from creator.infrastructure.outbox import SqlAlchemyOutboxRepository
from creator.infrastructure.provider_audit_repositories import (
    SqlAlchemyProviderIdempotencyKeyRepository,
    SqlAlchemyProviderWebhookEventRepository,
)
from creator.infrastructure.provider_repositories import (
    SqlAlchemyProviderDisputeRepository,
    SqlAlchemyRefundRepository,
)
from creator.infrastructure.provider_sync_repositories import (
    SqlAlchemyProviderCustomerRepository,
    SqlAlchemyProviderSubscriptionRepository,
)
from creator.infrastructure.schema_repositories import (
    SqlAlchemyBrandAssetRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyGeneratedImageRepository,
    SqlAlchemyPersonaRepository,
    SqlAlchemyPlanningRepository,
    SqlAlchemyPostStructureRepository,
)
from creator.infrastructure.subscription_history_repositories import (
    SqlAlchemySubscriptionHistoryRepository,
)
from creator.infrastructure.workspace_invite_repositories import SqlAlchemyWorkspaceInviteRepository
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

SessionFactory = Callable[[], Session]


class SqlAlchemyUnitOfWork:
    users: UserRepository
    settings: SettingsRepository
    workspaces: WorkspaceRepository
    brands: BrandRepository
    projects: ProjectRepository
    contents: ContentRepository
    generations: GenerationRepository
    assets: AssetRepository
    campaigns: CampaignRepository
    post_structures: PostStructureRepository
    planning: PlanningRepository
    personas: PersonaRepository
    generated_images: GeneratedImageRepository
    brand_assets: BrandAssetRepository
    brand_settings: BrandSettingsRepository
    image_generations: ImageGenerationRepository
    agent_workflows: AgentWorkflowRepository
    outbox: OutboxRepository
    user_devices: UserDeviceRepository
    notification_preferences: NotificationPreferenceRepository
    notifications: NotificationRepository
    notification_recipients: NotificationRecipientRepository
    plans: PlanRepository
    billing_accounts: BillingAccountRepository
    plan_items: PlanItemRepository
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

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._committed = False

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        session = self._session_factory()
        self._session = session
        self.users = SqlAlchemyUserRepository(session)
        self.settings = SqlAlchemySettingsRepository(session)
        self.workspaces = SqlAlchemyWorkspaceRepository(session)
        self.brands = SqlAlchemyBrandRepository(session)
        self.projects = SqlAlchemyProjectRepository(session)
        self.contents = SqlAlchemyContentRepository(session)
        self.generations = SqlAlchemyGenerationRepository(session)
        self.assets = SqlAlchemyAssetRepository(session)
        self.brand_assets = SqlAlchemyBrandAssetRepository(session)
        self.campaigns = SqlAlchemyCampaignRepository(session)
        self.post_structures = SqlAlchemyPostStructureRepository(session)
        self.planning = SqlAlchemyPlanningRepository(session)
        self.personas = SqlAlchemyPersonaRepository(session)
        self.generated_images = SqlAlchemyGeneratedImageRepository(session)
        self.brand_settings = SqlAlchemyBrandSettingsRepository(session)
        self.image_generations = SqlAlchemyImageGenerationRepository(session)
        self.agent_workflows = SqlAlchemyAgentWorkflowRepository(session)
        self.outbox = SqlAlchemyOutboxRepository(session)
        self.user_devices = SqlAlchemyUserDeviceRepository(session)
        self.notification_preferences = SqlAlchemyNotificationPreferenceRepository(session)
        self.notifications = SqlAlchemyNotificationRepository(session)
        self.notification_recipients = SqlAlchemyNotificationRecipientRepository(session)
        self.plans = SqlAlchemyPlanRepository(session)
        self.billing_accounts = SqlAlchemyBillingAccountRepository(session)
        self.plan_items = SqlAlchemyPlanItemRepository(session)
        self.subscriptions = SqlAlchemySubscriptionRepository(session)
        self.invoices = SqlAlchemyInvoiceRepository(session)
        self.charges = SqlAlchemyChargeRepository(session)
        self.workspace_invites = SqlAlchemyWorkspaceInviteRepository(session)
        self.billing_addresses = SqlAlchemyBillingAddressRepository(session)
        self.billing_payment_methods = SqlAlchemyBillingPaymentMethodRepository(session)
        self.coupons = SqlAlchemyCouponRepository(session)
        self.credit_packages = SqlAlchemyCreditPackageRepository(session)
        self.orders = SqlAlchemyOrderRepository(session)
        self.coupon_redemptions = SqlAlchemyCouponRedemptionRepository(session)
        self.workspace_credit_transactions = SqlAlchemyWorkspaceCreditTransactionRepository(session)
        self.refunds = SqlAlchemyRefundRepository(session)
        self.provider_disputes = SqlAlchemyProviderDisputeRepository(session)
        self.provider_customers = SqlAlchemyProviderCustomerRepository(session)
        self.provider_subscriptions = SqlAlchemyProviderSubscriptionRepository(session)
        self.provider_webhook_events = SqlAlchemyProviderWebhookEventRepository(session)
        self.provider_idempotency_keys = SqlAlchemyProviderIdempotencyKeyRepository(session)
        self.design_structures = SqlAlchemyDesignStructureRepository(session)
        self.brand_colors = SqlAlchemyBrandColorRepository(session)
        self.subscription_history = SqlAlchemySubscriptionHistoryRepository(session)
        self.workspace_invite_usages = SqlAlchemyWorkspaceInviteUsageRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if exc_type is not None or not self._committed:
                session.rollback()
        finally:
            session.close()

    def commit(self) -> None:
        session = self._require_session()
        try:
            session.commit()
        except SQLAlchemyError as error:
            session.rollback()
            raise map_sqlalchemy_error(error) from error
        self._committed = True

    def rollback(self) -> None:
        self._require_session().rollback()
        self._committed = False

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("Unit of Work is not active")
        return self._session


def get_unit_of_work() -> Generator[SqlAlchemyUnitOfWork, None, None]:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        yield unit_of_work
