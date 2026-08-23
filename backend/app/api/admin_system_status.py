from fastapi import APIRouter, Depends, Request

from app.api.admin_users import require_admin
from app.models.user import User
from app.services.runtime_system_status_service import (
    RuntimeSystemStatusService,
    get_runtime_system_status_service,
)


router = APIRouter(
    prefix="/admin/system-status",
    tags=["Admin System Status"],
)


@router.get("")
def system_status(
    request: Request,
    _: User = Depends(require_admin),
    service: RuntimeSystemStatusService = Depends(
        get_runtime_system_status_service
    ),
) -> dict:
    return service.read(request.headers.get("Authorization", ""))
