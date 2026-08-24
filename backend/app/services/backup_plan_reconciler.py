from __future__ import annotations

import asyncio
import logging

from app.database.session import SessionLocal
from app.services.backup_restore_service import BackupRestoreService


logger = logging.getLogger("ai_lab.backup_plan_reconciler")
RECONCILE_INTERVAL_SECONDS = 60


def _reconcile_once() -> None:
    with SessionLocal() as db:
        result = BackupRestoreService(db).reconcile_pending()
        if result["processed"]:
            logger.info(
                "Backup plan reconciliation processed=%s succeeded=%s failed=%s superseded=%s",
                result["processed"],
                result["succeeded"],
                result["failed"],
                result["superseded"],
            )


async def _run() -> None:
    while True:
        try:
            await asyncio.to_thread(_reconcile_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Backup plan reconciliation cycle failed.")
        await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)


def start_backup_plan_reconciler() -> asyncio.Task:
    return asyncio.create_task(_run(), name="backup-plan-reconciler")
