from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.admin_users import require_admin
from app.models.user import User
from app.services.runtime_system_status_service import (
    RuntimeSystemStatusService,
    get_runtime_system_status_service,
)
from app.services.runtime_system_control_service import (
    RuntimeSystemControlService,
    SystemControlUnavailable,
    SystemControlValidation,
    get_runtime_system_control_service,
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


ControlCommand = Literal["start", "stop", "restart"]


class ControlPreflightRequest(BaseModel):
    command: ControlCommand


class ControlPreflightResponse(BaseModel):
    command: ControlCommand
    command_id: str
    token: str
    expires_at: datetime


class ControlExecuteRequest(BaseModel):
    command: ControlCommand
    token: str = Field(min_length=32, max_length=4096)


def _control_error(error: Exception) -> HTTPException:
    code = str(error)
    status_code = 503 if isinstance(error, SystemControlUnavailable) else 409
    return HTTPException(status_code=status_code, detail={"code": code})


@router.post("/control/preflight", response_model=ControlPreflightResponse)
def control_preflight(
    payload: ControlPreflightRequest,
    request: Request,
    actor: User = Depends(require_admin),
    service: RuntimeSystemControlService = Depends(
        get_runtime_system_control_service
    ),
) -> ControlPreflightResponse:
    try:
        token, expires, command_id = service.issue_token(
            command=payload.command,
            actor=actor,
            authorization=request.headers.get("Authorization", ""),
        )
        return ControlPreflightResponse(
            command=payload.command,
            command_id=command_id,
            token=token,
            expires_at=expires,
        )
    except (SystemControlValidation, SystemControlUnavailable) as error:
        raise _control_error(error) from error


@router.post("/control/execute")
def control_execute(
    payload: ControlExecuteRequest,
    request: Request,
    actor: User = Depends(require_admin),
    service: RuntimeSystemControlService = Depends(
        get_runtime_system_control_service
    ),
) -> dict:
    try:
        return service.execute(
            token=payload.token,
            command=payload.command,
            actor=actor,
            authorization=request.headers.get("Authorization", ""),
        )
    except (SystemControlValidation, SystemControlUnavailable) as error:
        raise _control_error(error) from error
