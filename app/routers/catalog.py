from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas import ContactInput, ProductInput
from app.security import require_permission
from app.services import create_contact, create_product, list_contacts, list_products


router = APIRouter(prefix="/api", tags=["基础资料"])


@router.get("/products")
def get_products(_user: dict = Depends(require_permission("products.read"))):
    return list_products()


@router.post("/products", status_code=201)
def post_product(payload: ProductInput, _user: dict = Depends(require_permission("products.write"))):
    return create_product(payload)


@router.get("/suppliers")
def get_suppliers(_user: dict = Depends(require_permission("suppliers.read"))):
    return list_contacts("supplier")


@router.post("/suppliers", status_code=201)
def post_supplier(payload: ContactInput, _user: dict = Depends(require_permission("suppliers.write"))):
    return create_contact("supplier", payload)


@router.get("/customers")
def get_customers(_user: dict = Depends(require_permission("customers.read"))):
    return list_contacts("customer")


@router.post("/customers", status_code=201)
def post_customer(payload: ContactInput, _user: dict = Depends(require_permission("customers.write"))):
    return create_contact("customer", payload)

