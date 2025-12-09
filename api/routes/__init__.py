"""
API маршруты
"""
from api.routes.auth import router as auth_router
from api.routes.pcs import router as pcs_router
from api.routes.events import router as events_router
from api.routes.stats import router as stats_router

__all__ = [
    'auth_router',
    'pcs_router',
    'events_router',
    'stats_router',
]



