from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas import LoanInput, ReturnInput
from app.security import require_permission
from app.services import create_loan, get_loan, list_loans, return_loan


router = APIRouter(prefix="/api/loans", tags=["借还管理"])


@router.post("", status_code=201)
def post_loan(payload: LoanInput, user: dict = Depends(require_permission("inventory.write"))):
    return create_loan(payload, user["id"])


@router.get("")
def get_loans(_user: dict = Depends(require_permission("inventory.read"))):
    return list_loans()


@router.get("/{doc_no}")
def read_loan(doc_no: str, _user: dict = Depends(require_permission("inventory.read"))):
    return get_loan(doc_no)


@router.post("/{doc_no}/return")
def post_loan_return(doc_no: str, payload: ReturnInput, user: dict = Depends(require_permission("inventory.write"))):
    return return_loan(doc_no, payload, user["id"])

