from __future__ import annotations

from fastapi import APIRouter, Depends

from app.security import require_permission
from app.services import inventory, inventory_transactions


router = APIRouter(prefix="/api/inventory", tags=["库存"])


@router.get("")
def get_inventory(_user: dict = Depends(require_permission("inventory.read"))):
    return inventory()


@router.get("/transactions")
def get_inventory_transactions(_user: dict = Depends(require_permission("inventory.read"))):
    return inventory_transactions()

