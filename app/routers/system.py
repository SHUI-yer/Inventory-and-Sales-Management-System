from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas import RestoreRequest
from app.security import require_permission
from app.services import backup_database, list_backups, restore_database


router = APIRouter(prefix="/api/system", tags=["系统管理"])


@router.post("/backup")
def create_backup(_user: dict = Depends(require_permission("system.manage"))):
    return backup_database()


@router.get("/backups")
def backups(_user: dict = Depends(require_permission("system.manage"))):
    return list_backups()


@router.post("/restore")
def restore(payload: RestoreRequest, _user: dict = Depends(require_permission("system.manage"))):
    return restore_database(payload)

