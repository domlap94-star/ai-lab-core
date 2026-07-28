from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users.router import router as users_router
from app.core.constants import API_PREFIX

api_router = APIRouter(
    prefix=API_PREFIX,
)

api_router.include_router(auth_router)
api_router.include_router(users_router)