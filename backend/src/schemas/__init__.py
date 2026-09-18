"""
Pydantic schemas for request/response validation
"""

from .user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    MeResponse,
)
from .auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    LogoutResponse,
)
from .token import (
    TokenResponse,
    InviteTokenCreate,
    InviteTokenResponse,
    InviteTokenListResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetResponse,
)
from .comment import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentListResponse,
    CommentUploadResponse,
    CommentStatusResponse,
)
from .classification import (
    ClassificationResponse,
    ClassificationListResponse,
    ClassificationStatsResponse,
)
from .dashboard import (
    DashboardStatsResponse,
    DashboardSummaryResponse,
    CategoryDistributionResponse,
    StatusDistributionResponse,
)
from .csv import CSVUploadResponse
from .pagination import PageParams, PageResponse
from .account import (
    ExternalAccountCreate,
    ExternalAccountUpdate,
    ExternalAccountResponse,
    ExternalAccountListResponse,
)
from .cluster import (
    ClusterCreate,
    ClusterUpdate,
    ClusterResponse,
    ClusterListResponse,
    ClusterGraphResponse,
    ClusterGraphNode,
    ClusterGraphLink,
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponse,
    ConnectionListResponse,
)
from .ai import (
    AIChatRequest,
    AIChatResponse,
    AIToolResult,
    AIConversationResponse,
    AIConversationListResponse,
    AIStatsResponse,
    AISearchRequest,
    AISearchResponse,
    AIAnalyzeRequest,
    AIAnalyzeResponse,
)

__all__ = [
    # User schemas
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "MeResponse",
    # Auth schemas
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    "LogoutResponse",
    # Token schemas
    "TokenResponse",
    "InviteTokenCreate",
    "InviteTokenResponse",
    "InviteTokenListResponse",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "PasswordResetResponse",
    # Comment schemas
    "CommentCreate",
    "CommentUpdate",
    "CommentResponse",
    "CommentListResponse",
    "CommentUploadResponse",
    "CommentStatusResponse",
    # Classification schemas
    "ClassificationResponse",
    "ClassificationListResponse",
    "ClassificationStatsResponse",
    # Dashboard schemas
    "DashboardStatsResponse",
    "DashboardSummaryResponse",
    "CategoryDistributionResponse",
    "StatusDistributionResponse",
    # CSV schemas
    "CSVUploadResponse",
    # Pagination
    "PageParams",
    "PageResponse",
    # External Account schemas
    "ExternalAccountCreate",
    "ExternalAccountUpdate",
    "ExternalAccountResponse",
    "ExternalAccountListResponse",
    # Cluster schemas
    "ClusterCreate",
    "ClusterUpdate",
    "ClusterResponse",
    "ClusterListResponse",
    "ClusterGraphResponse",
    "ClusterGraphNode",
    "ClusterGraphLink",
    # Connection schemas
    "ConnectionCreate",
    "ConnectionUpdate",
    "ConnectionResponse",
    "ConnectionListResponse",
    # AI schemas
    "AIChatRequest",
    "AIChatResponse",
    "AIToolResult",
    "AIConversationResponse",
    "AIConversationListResponse",
    "AIStatsResponse",
    "AISearchRequest",
    "AISearchResponse",
    "AIAnalyzeRequest",
    "AIAnalyzeResponse",
]
