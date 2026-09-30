"""HTTP DTO facade; definitions live in bounded-context packages."""

from .auth import AuthLoginRequest, AuthSignupRequest
from .billing import (
    BillingAccountCreateRequest,
    InvoiceCreateRequest,
    PlanCreateRequest,
    SubscriptionCreateRequest,
)
from .content import (
    ContentCreateRequest,
    ContentUpdateRequest,
    GenerateContentRequest,
    GenerateImageRequest,
    GenerateTextRequest,
    ImproveContentRequest,
    RegenerateImageRequest,
)
from .core import (
    AssetCreateRequest,
    AssetUpdateRequest,
    BrandAssetCreateRequest,
    BrandAssetUpdateRequest,
    BrandCreateRequest,
    BrandSettingsUpdateRequest,
    BrandSettingsUpsertRequest,
    BrandUpdateRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    SettingsUpdateRequest,
    UserCreateRequest,
    UserUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
)
from .generation import GenerationCreateRequest, GenerationUpdateRequest
from .marketing import (
    CampaignCreateRequest,
    PersonaCreateRequest,
    PlanningCreateRequest,
    PostStructureCreateRequest,
    PostStructureUpdateRequest,
)
from .notifications import (
    NotificationCreateRequest,
    NotificationPreferenceRequest,
    UserDeviceCreateRequest,
)
from .workflow import ImageWorkflowDecisionRequest, ImageWorkflowRequest

__all__ = [
    "AssetCreateRequest",
    "AssetUpdateRequest",
    "BrandAssetCreateRequest",
    "BrandAssetUpdateRequest",
    "AuthLoginRequest",
    "AuthSignupRequest",
    "BillingAccountCreateRequest",
    "BrandCreateRequest",
    "BrandSettingsUpdateRequest",
    "BrandSettingsUpsertRequest",
    "BrandUpdateRequest",
    "CampaignCreateRequest",
    "ContentCreateRequest",
    "ContentUpdateRequest",
    "GenerateContentRequest",
    "GenerateImageRequest",
    "GenerateTextRequest",
    "GenerationCreateRequest",
    "GenerationUpdateRequest",
    "ImproveContentRequest",
    "ImageWorkflowDecisionRequest",
    "ImageWorkflowRequest",
    "InvoiceCreateRequest",
    "NotificationCreateRequest",
    "NotificationPreferenceRequest",
    "PersonaCreateRequest",
    "PlanCreateRequest",
    "PlanningCreateRequest",
    "PostStructureCreateRequest",
    "PostStructureUpdateRequest",
    "ProjectCreateRequest",
    "ProjectUpdateRequest",
    "RegenerateImageRequest",
    "SettingsUpdateRequest",
    "SubscriptionCreateRequest",
    "UserCreateRequest",
    "UserDeviceCreateRequest",
    "UserUpdateRequest",
    "WorkspaceCreateRequest",
    "WorkspaceUpdateRequest",
]
