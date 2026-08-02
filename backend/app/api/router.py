from fastapi import APIRouter

from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.clients.router import router as clients_router
from app.api.imports.router import router as imports_router
from app.api.users.router import router as users_router
from app.core.constants import API_PREFIX

api_router = APIRouter(
    prefix=API_PREFIX,
)

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(clients_router)
api_router.include_router(imports_router)
api_router.include_router(ai_router)