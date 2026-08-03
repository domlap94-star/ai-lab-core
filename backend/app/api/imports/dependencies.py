from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_import_api_key(
    x_import_api_key: str | None = Header(
        default=None,
        alias="X-Import-Api-Key",
    ),
) -> None:
    expected_key = settings.n8n_ingest_api_key

    if not x_import_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing import API key",
        )

    if not secrets.compare_digest(
        x_import_api_key,
        expected_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid import API key",
        )