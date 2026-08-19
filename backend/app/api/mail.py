from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.global_mail import GlobalMailDetail, GlobalMailPage, GlobalMailThread
from app.services.global_mail_service import GlobalMailNotFoundError, GlobalMailService
from app.schemas.mail_send import MailForwardRequest, MailReplyRequest, MailSendRequest, MailSendResponse
from app.services.mail_send_service import MailSendConflictError, MailSendNotFoundError, MailSendService, MailSendValidationError
from app.schemas.mail_send import MailForwardRequest, MailReplyRequest, MailSendRequest, MailSendResponse
from app.services.mail_send_service import MailSendConflictError, MailSendNotFoundError, MailSendService, MailSendValidationError


router = APIRouter(prefix="/mail", tags=["Mail"])


def _send_error(exc: Exception) -> None:
    if isinstance(exc, MailSendConflictError):
        raise HTTPException(status_code=409, detail={"code": str(exc)}) from exc
    if isinstance(exc, MailSendNotFoundError):
        raise HTTPException(status_code=404, detail={"code": "mail_not_found"}) from exc
    raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/send", response_model=MailSendResponse)
def send_mail(request: MailSendRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailSendResponse:
    try: return MailSendService(db).compose(actor, request)
    except (MailSendConflictError, MailSendNotFoundError, MailSendValidationError) as exc: _send_error(exc)


@router.post("/{source_id}/reply", response_model=MailSendResponse)
def reply_mail(source_id: int, request: MailReplyRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailSendResponse:
    try: return MailSendService(db).reply(source_id, actor, request)
    except (MailSendConflictError, MailSendNotFoundError, MailSendValidationError) as exc: _send_error(exc)


@router.post("/{source_id}/forward", response_model=MailSendResponse)
def forward_mail(source_id: int, request: MailForwardRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailSendResponse:
    try: return MailSendService(db).forward(source_id, actor, request)
    except (MailSendConflictError, MailSendNotFoundError, MailSendValidationError) as exc: _send_error(exc)


def _send_error(exc: Exception) -> None:
    if isinstance(exc, MailSendConflictError):
        raise HTTPException(status_code=409, detail={"code": str(exc)}) from exc
    if isinstance(exc, MailSendNotFoundError):
        raise HTTPException(status_code=404, detail={"code": "mail_not_found"}) from exc
    raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc


@router.post("/send", response_model=MailSendResponse)
def send_mail(request: MailSendRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailSendResponse:
    try: return MailSendService(db).compose(actor, request)
    except (MailSendConflictError, MailSendNotFoundError, MailSendValidationError) as exc: _send_error(exc)


@router.post("/{source_id}/reply", response_model=MailSendResponse)
def reply_mail(source_id: int, request: MailReplyRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailSendResponse:
    try: return MailSendService(db).reply(source_id, actor, request)
    except (MailSendConflictError, MailSendNotFoundError, MailSendValidationError) as exc: _send_error(exc)


@router.post("/{source_id}/forward", response_model=MailSendResponse)
def forward_mail(source_id: int, request: MailForwardRequest, actor: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailSendResponse:
    try: return MailSendService(db).forward(source_id, actor, request)
    except (MailSendConflictError, MailSendNotFoundError, MailSendValidationError) as exc: _send_error(exc)


@router.get("", response_model=GlobalMailPage)
def list_mail(
    search: str | None = Query(default=None, min_length=1, max_length=200),
    client_id: int | None = Query(default=None, ge=1),
    direction: Literal["received", "sent", "unknown"] | None = None,
    linked: bool | None = None,
    has_attachments: bool | None = None,
    read_state: Literal["read", "unread", "unknown"] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    thread_id: str | None = Query(default=None, min_length=1, max_length=1000),
    skip: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GlobalMailPage:
    return GlobalMailService(db).get_page(
        search=search, client_id=client_id, direction=direction, linked=linked,
        has_attachments=has_attachments, read_state=read_state,
        date_from=date_from, date_to=date_to, thread_id=thread_id,
        skip=skip, limit=limit,
    )


@router.get("/threads/{thread_id}", response_model=GlobalMailThread)
def get_mail_thread(
    thread_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GlobalMailThread:
    if not thread_id.strip() or len(thread_id) > 1000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        return GlobalMailService(db).get_thread(thread_id)
    except GlobalMailNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.get("/{source_id}", response_model=GlobalMailDetail)
def get_mail_detail(
    source_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GlobalMailDetail:
    try:
        return GlobalMailService(db).get_detail(source_id)
    except GlobalMailNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
