from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: dict


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    role_id: int = Field(gt=0)


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=50)
    permission_codes: list[str] = Field(default_factory=list)


class RolePermissionsUpdate(BaseModel):
    permission_codes: list[str]


class UserActiveUpdate(BaseModel):
    active: bool


class UserRoleUpdate(BaseModel):
    role_id: int = Field(gt=0)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=100)


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=8, max_length=100)


class ContactInput(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    contact: str = Field(default="", max_length=50)
    phone: str = Field(default="", max_length=50)

    @field_validator("code", "name")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class ProductInput(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="", max_length=50)
    unit: str = Field(default="件", max_length=20)
    purchase_price: float = Field(default=0, ge=0)
    sale_price: float = Field(default=0, ge=0)
    warning_stock: int = Field(default=0, ge=0)

    @field_validator("sku", "name", "unit")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class OrderItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)


class ReturnItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class PurchaseInput(BaseModel):
    supplier_id: int = Field(gt=0)
    items: list[OrderItemInput] = Field(min_length=1)


class SaleInput(BaseModel):
    customer_id: int = Field(gt=0)
    items: list[OrderItemInput] = Field(min_length=1)


class LoanInput(BaseModel):
    borrower: str = Field(min_length=1, max_length=100)
    expected_return_date: date | None = None
    items: list[OrderItemInput] = Field(min_length=1)


class ReturnInput(BaseModel):
    items: list[ReturnItemInput] = Field(min_length=1)


class ReturnCreateInput(BaseModel):
    source_doc_no: str = Field(min_length=1, max_length=60)
    items: list[ReturnItemInput] = Field(min_length=1)


class LoanReturnInput(BaseModel):
    items: list[ReturnItemInput] = Field(min_length=1)


class RestoreRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)


def cents(value: float) -> int:
    return int(round(value * 100))

