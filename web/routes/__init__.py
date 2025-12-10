"""
Веб-маршруты
"""
from web.routes.dashboard import router as dashboard_router
from web.routes.pc_detail import router as pc_detail_router
from web.routes.events import router as events_router

__all__ = [
    'dashboard_router',
    'pc_detail_router',
    'events_router',
]




