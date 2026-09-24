"""
Pydantic schemas for request/response validation
"""

from .user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    MeResponse,
)
from .auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    LogoutResponse,
)
from .comment import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentListResponse,
    CommentMentionResponse,
    CommentStatusResponse,
    CommentSearchResponse,
    CommentVoteResponse,
)
from .classification import (
    ClassificationCreate,
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
    AIConversationResponse,
    AIConversationListResponse,
    AIStatsResponse,
)

__all__ = [
    # User schemas
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "MeResponse",
    # Auth schemas
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    "LogoutResponse",
    # Comment schemas
    "CommentCreate",
    "CommentUpdate",
    "CommentResponse",
    "CommentListResponse",
    "CommentMentionResponse",
    "CommentStatusResponse",
    "CommentSearchResponse",
    "CommentVoteResponse",
    # Classification schemas
    "ClassificationCreate",
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
    "AIConversationResponse",
    "AIConversationListResponse",
    "AIStatsResponse",
]
