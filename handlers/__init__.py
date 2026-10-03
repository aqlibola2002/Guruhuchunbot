from .admin import router as admin_router
from .group_events import router as events_router
from .stats import router as stats_router
from .faq import router as faq_router
from .common import router as common_router
from .moderation import router as moderation_router

__all__ = [
    "admin_router",
    "events_router",
    "stats_router",
    "faq_router",
    "common_router",
    "moderation_router",
]
