from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path


TEST_DATA = tempfile.TemporaryDirectory(prefix="ims-test-")
os.environ["IMS_DATA_DIR"] = TEST_DATA.name
os.environ["IMS_MODE"] = "local"

import httpx

from app.db import get_db, init_db
from app.main import app
from app.security import hash_password


class InventoryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        TEST_DATA.cleanup()

    async def request(self, method: str, path: str, **kwargs):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    def login(self) -> str:
        response = asyncio.run(self.request("POST", "/api/auth/login", json={"username": "admin", "password": "admin123"}))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def post(self, path: str, token: str, payload: dict):
        return asyncio.run(self.request("POST", path, headers={"Authorization": f"Bearer {token}"}, json=payload))

    def get(self, path: str, token: str):
        return asyncio.run(self.request("GET", path, headers={"Authorization": f"Bearer {token}"}))

    def test_purchase_sale_and_inventory_rules(self):
        token = self.login()
        supplier = self.post("/api/suppliers", token, {"code": "SUP-TEST", "name": "测试供应商"})
        self.assertEqual(supplier.status_code, 201, supplier.text)
        customer = self.post("/api/customers", token, {"code": "CUS-TEST", "name": "测试客户"})
        self.assertEqual(customer.status_code, 201, customer.text)
        product = self.post(
            "/api/products",
            token,
            {"sku": "SKU-TEST", "name": "测试商品", "category": "测试", "unit": "件", "purchase_price": 10, "sale_price": 15},
        )
        self.assertEqual(product.status_code, 201, product.text)
        supplier_id = supplier.json()["id"]
        customer_id = customer.json()["id"]
        product_id = product.json()["id"]

        purchase = self.post("/api/purchases", token, {"supplier_id": supplier_id, "items": [{"product_id": product_id, "quantity": 5, "unit_price": 10}]})
        self.assertEqual(purchase.status_code, 201, purchase.text)
        doc_no = purchase.json()["doc_no"]
        posted = self.post(f"/api/purchases/{doc_no}/post", token, {})
        self.assertEqual(posted.status_code, 200, posted.text)
        duplicate = self.post(f"/api/purchases/{doc_no}/post", token, {})
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

        sale = self.post("/api/sales", token, {"customer_id": customer_id, "items": [{"product_id": product_id, "quantity": 3, "unit_price": 15}]})
        sale_doc = sale.json()["doc_no"]
        self.assertEqual(self.post(f"/api/sales/{sale_doc}/post", token, {}).status_code, 200)
        inventory = self.get("/api/inventory", token)
        self.assertEqual(inventory.json()[0]["available_stock"], 2)

        too_large = self.post("/api/sales", token, {"customer_id": customer_id, "items": [{"product_id": product_id, "quantity": 3, "unit_price": 15}]})
        too_large_doc = too_large.json()["doc_no"]
        failed = self.post(f"/api/sales/{too_large_doc}/post", token, {})
        self.assertEqual(failed.status_code, 409, failed.text)
        inventory_after = self.get("/api/inventory", token)
        self.assertEqual(inventory_after.json()[0]["available_stock"], 2)

        with get_db() as connection:
            connection.execute("UPDATE purchases SET posted_at = '2020-01-01 00:00:00' WHERE doc_no = ?", (doc_no,))
        purchase_return = self.post(
            "/api/purchase-returns",
            token,
            {"source_doc_no": doc_no, "items": [{"product_id": product_id, "quantity": 1}]},
        )
        self.assertEqual(purchase_return.status_code, 201, purchase_return.text)
        self.assertEqual(self.post(f"/api/purchase-returns/{purchase_return.json()['doc_no']}/post", token, {}).status_code, 200)
        purchase_detail = self.get(f"/api/purchases/{doc_no}", token).json()
        self.assertEqual(purchase_detail["items"][0]["returned_quantity"], 1)
        self.assertEqual(purchase_detail["items"][0]["remaining_return_quantity"], 4)
        self.assertEqual(self.get("/api/purchase-returns", token).json()[0]["source_doc_no"], doc_no)
        today = date.today().isoformat()
        purchase_rows = self.get(f"/api/reports/purchases?start_date={today}&end_date={today}", token).json()
        purchase_row = next(row for row in purchase_rows if row["sku"] == "SKU-TEST")
        self.assertEqual((purchase_row["quantity"], purchase_row["returned_quantity"], purchase_row["net_quantity"]), (0, 1, -1))
        duplicate_lines = self.post(
            "/api/purchase-returns",
            token,
            {"source_doc_no": doc_no, "items": [{"product_id": product_id, "quantity": 1}, {"product_id": product_id, "quantity": 1}]},
        )
        self.assertEqual(duplicate_lines.status_code, 400, duplicate_lines.text)

        with get_db() as connection:
            connection.execute("UPDATE sales SET posted_at = '2020-01-01 00:00:00' WHERE doc_no = ?", (sale_doc,))
        sales_return = self.post(
            "/api/sales-returns",
            token,
            {"source_doc_no": sale_doc, "items": [{"product_id": product_id, "quantity": 1}]},
        )
        self.assertEqual(sales_return.status_code, 201, sales_return.text)
        self.assertEqual(self.post(f"/api/sales-returns/{sales_return.json()['doc_no']}/post", token, {}).status_code, 200)
        self.assertEqual(self.get(f"/api/sales/{sale_doc}", token).json()["items"][0]["remaining_return_quantity"], 2)
        self.assertEqual(self.get("/api/sales-returns", token).json()[0]["source_doc_no"], sale_doc)
        sales_rows = self.get(f"/api/reports/sales?start_date={today}&end_date={today}", token).json()
        sales_row = next(row for row in sales_rows if row["sku"] == "SKU-TEST")
        self.assertEqual((sales_row["quantity"], sales_row["returned_quantity"], sales_row["net_quantity"]), (0, 1, -1))

        loan = self.post(
            "/api/loans",
            token,
            {"borrower": "测试借用人", "expected_return_date": "2020-01-01", "items": [{"product_id": product_id, "quantity": 1, "unit_price": 0}]},
        )
        self.assertEqual(loan.status_code, 201, loan.text)
        after_loan = self.get("/api/inventory", token).json()[0]
        self.assertEqual(after_loan["available_stock"], 1)
        self.assertEqual(after_loan["loaned_quantity"], 1)
        loan_report = self.get("/api/reports/loans", token).json()
        self.assertEqual(loan_report[0]["remaining_quantity"], 1)
        self.assertTrue(loan_report[0]["overdue"])
        self.assertEqual(self.get("/api/reports/loans?start_date=2025-01-01&end_date=2025-12-31", token).json(), [])
        loan_return = self.post(
            f"/api/loans/{loan.json()['doc_no']}/return",
            token,
            {"items": [{"product_id": product_id, "quantity": 1}]},
        )
        self.assertEqual(loan_return.status_code, 200, loan_return.text)
        after_return = self.get("/api/inventory", token).json()[0]
        self.assertEqual(after_return["available_stock"], 2)
        self.assertEqual(after_return["loaned_quantity"], 0)

    def test_permission_is_enforced(self):
        token = self.login()
        response = self.get("/api/system/backup", token)
        self.assertIn(response.status_code, {405, 404})
        response = asyncio.run(self.request("POST", "/api/system/backup", headers={"Authorization": f"Bearer {token}"}))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(Path(response.json()["path"]).exists())

    def test_role_permission_is_enforced_on_api(self):
        with get_db() as connection:
            role = connection.execute("SELECT id FROM roles WHERE code = 'sales'").fetchone()
            connection.execute(
                "INSERT INTO users(username, password_hash, display_name, role_id) VALUES (?, ?, ?, ?)",
                ("sales-test", hash_password("sales-pass-123"), "测试销售员", role["id"]),
            )
        response = asyncio.run(self.request(
            "POST",
            "/api/auth/login",
            json={"username": "sales-test", "password": "sales-pass-123"},
        ))
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["access_token"]
        denied = self.post("/api/products", token, {"sku": "FORBIDDEN", "name": "越权商品"})
        self.assertEqual(denied.status_code, 403, denied.text)

    def test_report_endpoints(self):
        token = self.login()
        summary = self.get("/api/reports/summary", token)
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertIn("sales_net_amount", summary.json())
        for path in ("/api/reports/sales", "/api/reports/purchases", "/api/reports/inventory", "/api/reports/loans", "/api/reports/daily"):
            response = self.get(path, token)
            self.assertEqual(response.status_code, 200, f"{path}: {response.text}")
        invalid_range = asyncio.run(self.request("GET", "/api/reports/summary?start_date=2026-12-01&end_date=2026-01-01", headers={"Authorization": f"Bearer {token}"}))
        self.assertEqual(invalid_range.status_code, 400, invalid_range.text)

    def test_admin_can_create_role_and_user(self):
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        role = self.post("/api/admin/roles", token, {"code": "stock_reader", "name": "库存查询员", "permission_codes": ["inventory.read"]})
        self.assertEqual(role.status_code, 201, role.text)
        created = self.post(
            "/api/admin/users",
            token,
            {"username": "stock-user", "password": "stock-pass-123", "display_name": "库存查询员", "role_id": role.json()["id"]},
        )
        self.assertEqual(created.status_code, 201, created.text)
        login = asyncio.run(self.request("POST", "/api/auth/login", json={"username": "stock-user", "password": "stock-pass-123"}))
        self.assertEqual(login.status_code, 200, login.text)
        limited_token = login.json()["access_token"]
        self.assertEqual(self.get("/api/inventory", limited_token).status_code, 200)
        denied = self.post("/api/products", limited_token, {"sku": "NOPE", "name": "无权商品"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(asyncio.run(self.request("GET", "/api/admin/users", headers=headers)).status_code, 200)
        with get_db() as connection:
            sales_role_id = connection.execute("SELECT id FROM roles WHERE code = 'sales'").fetchone()["id"]
        reassigned = asyncio.run(self.request(
            "PATCH",
            f"/api/admin/users/{created.json()['id']}/role",
            headers=headers,
            json={"role_id": sales_role_id},
        ))
        self.assertEqual(reassigned.status_code, 200, reassigned.text)
        self.assertEqual(self.get("/api/inventory", limited_token).status_code, 401)
        relogin = asyncio.run(self.request("POST", "/api/auth/login", json={"username": "stock-user", "password": "stock-pass-123"}))
        self.assertEqual(relogin.status_code, 200, relogin.text)
        self.assertEqual(relogin.json()["user"]["role_code"], "sales")

    def test_backup_restore_round_trip(self):
        token = self.login()
        backup = self.post("/api/system/backup", token, {})
        self.assertEqual(backup.status_code, 200, backup.text)
        temporary = self.post("/api/suppliers", token, {"code": "SUP-RESTORE", "name": "恢复测试供应商"})
        self.assertEqual(temporary.status_code, 201, temporary.text)
        restored = self.post("/api/system/restore", token, {"path": backup.json()["path"]})
        self.assertEqual(restored.status_code, 200, restored.text)
        supplier_codes = {row["code"] for row in self.get("/api/suppliers", token).json()}
        self.assertNotIn("SUP-RESTORE", supplier_codes)
        self.assertTrue(Path(restored.json()["before_restore_backup"]).exists())


if __name__ == "__main__":
    unittest.main()

