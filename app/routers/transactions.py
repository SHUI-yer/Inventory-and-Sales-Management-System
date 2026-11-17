from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas import PurchaseInput, ReturnCreateInput, SaleInput
from app.security import get_current_user, require_permission
from app.services import _create_return, create_purchase, create_sale, get_purchase, get_return, get_sale, list_purchases, list_returns, list_sales, post_purchase, post_return, post_sale


router = APIRouter(prefix="/api", tags=["采购与销售"])


@router.post("/purchases", status_code=201)
def post_purchase_draft(payload: PurchaseInput, user: dict = Depends(require_permission("purchases.write"))):
    return create_purchase(payload, user["id"])


@router.get("/purchases")
def purchases(_user: dict = Depends(require_permission("purchases.read"))):
    return list_purchases()


@router.get("/purchases/{doc_no}")
def read_purchase(doc_no: str, _user: dict = Depends(require_permission("purchases.read"))):
    return get_purchase(doc_no)


@router.post("/purchases/{doc_no}/post")
def complete_purchase(doc_no: str, user: dict = Depends(require_permission("purchases.write"))):
    return post_purchase(doc_no, user["id"])


@router.post("/sales", status_code=201)
def post_sale_draft(payload: SaleInput, user: dict = Depends(require_permission("sales.write"))):
    return create_sale(payload, user["id"])


@router.get("/sales")
def sales(_user: dict = Depends(require_permission("sales.read"))):
    return list_sales()


@router.get("/sales/{doc_no}")
def read_sale(doc_no: str, _user: dict = Depends(require_permission("sales.read"))):
    return get_sale(doc_no)


@router.post("/sales/{doc_no}/post")
def complete_sale(doc_no: str, user: dict = Depends(require_permission("sales.write"))):
    return post_sale(doc_no, user["id"])


@router.post("/purchase-returns", status_code=201)
def post_purchase_return(payload: ReturnCreateInput, user: dict = Depends(require_permission("purchases.write"))):
    return _create_return(payload, user["id"], "purchase")


@router.get("/purchase-returns")
def purchase_returns(_user: dict = Depends(require_permission("purchases.read"))):
    return list_returns("purchase")


@router.get("/purchase-returns/{doc_no}")
def read_purchase_return(doc_no: str, _user: dict = Depends(require_permission("purchases.read"))):
    return get_return(doc_no, "purchase")


@router.post("/purchase-returns/{doc_no}/post")
def complete_purchase_return(doc_no: str, user: dict = Depends(require_permission("purchases.write"))):
    return post_return(doc_no, user["id"], "purchase")


@router.post("/sales-returns", status_code=201)
def post_sales_return(payload: ReturnCreateInput, user: dict = Depends(require_permission("sales.write"))):
    return _create_return(payload, user["id"], "sale")


@router.get("/sales-returns")
def sales_returns(_user: dict = Depends(require_permission("sales.read"))):
    return list_returns("sale")


@router.get("/sales-returns/{doc_no}")
def read_sales_return(doc_no: str, _user: dict = Depends(require_permission("sales.read"))):
    return get_return(doc_no, "sale")


@router.post("/sales-returns/{doc_no}/post")
def complete_sales_return(doc_no: str, user: dict = Depends(require_permission("sales.write"))):
    return post_return(doc_no, user["id"], "sale")

