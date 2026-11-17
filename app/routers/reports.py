from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from app.security import require_permission
from app.services import inventory, report_daily, report_loans, report_purchases, report_sales, report_summary


router = APIRouter(prefix="/api/reports", tags=["报表"])


@router.get("/summary")
def summary(start_date: date | None = None, end_date: date | None = None, _user: dict = Depends(require_permission("inventory.read"))):
    return report_summary(start_date, end_date)


@router.get("/sales")
def sales(start_date: date | None = None, end_date: date | None = None, _user: dict = Depends(require_permission("sales.read"))):
    return report_sales(start_date, end_date)


@router.get("/purchases")
def purchases(start_date: date | None = None, end_date: date | None = None, _user: dict = Depends(require_permission("purchases.read"))):
    return report_purchases(start_date, end_date)


@router.get("/inventory")
def inventory_report(_user: dict = Depends(require_permission("inventory.read"))):
    return inventory()


@router.get("/loans")
def loans_report(start_date: date | None = None, end_date: date | None = None, _user: dict = Depends(require_permission("inventory.read"))):
    return report_loans(start_date, end_date)


@router.get("/daily")
def daily(start_date: date | None = None, end_date: date | None = None, _user: dict = Depends(require_permission("inventory.read"))):
    return report_daily(start_date, end_date)

