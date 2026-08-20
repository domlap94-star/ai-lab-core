from fastapi import APIRouter

from app.api.admin_users import router as admin_users_router
from app.api.admin_ignored_mail_sources import router as admin_ignored_mail_sources_router
from app.api.admin_change_history import router as admin_change_history_router
from app.api.admin_trash import router as admin_trash_router
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.client_candidates.router import (
    router as client_candidates_router,
)
from app.api.clients.router import router as clients_router
from app.api.documents.router import router as documents_router
from app.api.imports.router import router as imports_router
from app.api.inspections.router import router as inspections_router
from app.api.users.router import router as users_router
from app.api.projects.router import router as projects_router
from app.api.search.router import router as search_router
from app.api.mail import router as mail_router
from app.api.work_items import router as work_items_router
from app.api.absences import router as absences_router
from app.api.calendar import router as calendar_router
from app.api.activity import router as activity_router
from app.core.constants import API_PREFIX


api_router = APIRouter(
    prefix=API_PREFIX,
)

api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_ignored_mail_sources_router)
api_router.include_router(admin_change_history_router)
api_router.include_router(admin_trash_router)
api_router.include_router(users_router)
api_router.include_router(clients_router)
api_router.include_router(client_candidates_router)
api_router.include_router(imports_router)
api_router.include_router(documents_router)
api_router.include_router(projects_router)
api_router.include_router(inspections_router)
api_router.include_router(search_router)
api_router.include_router(mail_router)
api_router.include_router(ai_router)
api_router.include_router(work_items_router)
api_router.include_router(absences_router)
api_router.include_router(calendar_router)
api_router.include_router(activity_router)
