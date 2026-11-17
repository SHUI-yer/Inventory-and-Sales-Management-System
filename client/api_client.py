from __future__ import annotations

from typing import Any

import httpx


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self.client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self.client.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self.client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as error:
            raise ApiError(f"无法连接服务器：{error}") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(str(detail))
        return response.json()

    def login(self, username: str, password: str) -> dict:
        result = self.request("POST", "/api/auth/login", json={"username": username, "password": password})
        self.token = result["access_token"]
        return result["user"]

    def products(self) -> list[dict]:
        return self.request("GET", "/api/products")

    def suppliers(self) -> list[dict]:
        return self.request("GET", "/api/suppliers")

    def customers(self) -> list[dict]:
        return self.request("GET", "/api/customers")

    def inventory(self) -> list[dict]:
        return self.request("GET", "/api/inventory")

    def backup(self) -> dict:
        return self.request("POST", "/api/system/backup")

    def create_product(self, payload: dict) -> dict:
        return self.request("POST", "/api/products", json=payload)

    def create_supplier(self, payload: dict) -> dict:
        return self.request("POST", "/api/suppliers", json=payload)

    def create_customer(self, payload: dict) -> dict:
        return self.request("POST", "/api/customers", json=payload)

    def create_purchase(self, payload: dict) -> dict:
        return self.request("POST", "/api/purchases", json=payload)

    def post_purchase(self, doc_no: str) -> dict:
        return self.request("POST", f"/api/purchases/{doc_no}/post")

    def create_sale(self, payload: dict) -> dict:
        return self.request("POST", "/api/sales", json=payload)

    def post_sale(self, doc_no: str) -> dict:
        return self.request("POST", f"/api/sales/{doc_no}/post")

    def purchases(self) -> list[dict]:
        return self.request("GET", "/api/purchases")

    def purchase(self, doc_no: str) -> dict:
        return self.request("GET", f"/api/purchases/{doc_no}")

    def create_purchase_return(self, payload: dict) -> dict:
        return self.request("POST", "/api/purchase-returns", json=payload)

    def post_purchase_return(self, doc_no: str) -> dict:
        return self.request("POST", f"/api/purchase-returns/{doc_no}/post")

    def purchase_returns(self) -> list[dict]:
        return self.request("GET", "/api/purchase-returns")

    def sales(self) -> list[dict]:
        return self.request("GET", "/api/sales")

    def sale(self, doc_no: str) -> dict:
        return self.request("GET", f"/api/sales/{doc_no}")

    def create_sale_return(self, payload: dict) -> dict:
        return self.request("POST", "/api/sales-returns", json=payload)

    def post_sale_return(self, doc_no: str) -> dict:
        return self.request("POST", f"/api/sales-returns/{doc_no}/post")

    def sales_returns(self) -> list[dict]:
        return self.request("GET", "/api/sales-returns")

    def loans(self) -> list[dict]:
        return self.request("GET", "/api/loans")

    def loan(self, doc_no: str) -> dict:
        return self.request("GET", f"/api/loans/{doc_no}")

    def create_loan(self, payload: dict) -> dict:
        return self.request("POST", "/api/loans", json=payload)

    def return_loan(self, doc_no: str, payload: dict) -> dict:
        return self.request("POST", f"/api/loans/{doc_no}/return", json=payload)

    def roles(self) -> list[dict]:
        return self.request("GET", "/api/admin/roles")

    def permissions(self) -> list[dict]:
        return self.request("GET", "/api/admin/permissions")

    def users(self) -> list[dict]:
        return self.request("GET", "/api/admin/users")

    def create_role(self, payload: dict) -> dict:
        return self.request("POST", "/api/admin/roles", json=payload)

    def update_role_permissions(self, role_id: int, permission_codes: list[str]) -> dict:
        return self.request("PUT", f"/api/admin/roles/{role_id}/permissions", json={"permission_codes": permission_codes})

    def create_user(self, payload: dict) -> dict:
        return self.request("POST", "/api/admin/users", json=payload)

    def set_user_active(self, user_id: int, active: bool) -> dict:
        return self.request("PATCH", f"/api/admin/users/{user_id}/active", json={"active": active})

    def update_user_role(self, user_id: int, role_id: int) -> dict:
        return self.request("PATCH", f"/api/admin/users/{user_id}/role", json={"role_id": role_id})

    def reset_user_password(self, user_id: int, new_password: str) -> dict:
        return self.request("POST", f"/api/admin/users/{user_id}/reset-password", json={"new_password": new_password})

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self.request("POST", "/api/auth/password", json={"old_password": old_password, "new_password": new_password})

    def _report_params(self, start_date: str, end_date: str) -> dict[str, str]:
        return {key: value for key, value in (("start_date", start_date), ("end_date", end_date)) if value}

    def report_summary(self, start_date: str = "", end_date: str = "") -> dict:
        return self.request("GET", "/api/reports/summary", params=self._report_params(start_date, end_date))

    def report_sales(self, start_date: str = "", end_date: str = "") -> list[dict]:
        return self.request("GET", "/api/reports/sales", params=self._report_params(start_date, end_date))

    def report_purchases(self, start_date: str = "", end_date: str = "") -> list[dict]:
        return self.request("GET", "/api/reports/purchases", params=self._report_params(start_date, end_date))

    def report_inventory(self) -> list[dict]:
        return self.request("GET", "/api/reports/inventory")

    def report_loans(self, start_date: str = "", end_date: str = "") -> list[dict]:
        return self.request("GET", "/api/reports/loans", params=self._report_params(start_date, end_date))

    def report_daily(self, start_date: str = "", end_date: str = "") -> list[dict]:
        return self.request("GET", "/api/reports/daily", params=self._report_params(start_date, end_date))

    def backups(self) -> list[dict]:
        return self.request("GET", "/api/system/backups")

    def restore(self, path: str) -> dict:
        return self.request("POST", "/api/system/restore", json={"path": path})

