from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.db import get_db
from app.schemas import ContactInput, LoanInput, ProductInput, PurchaseInput, ReturnCreateInput, ReturnInput, RestoreRequest, SaleInput, cents
from app.settings import get_data_dir, get_database_path


def _doc_no(prefix: str) -> str:
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:6].upper()}"


def _handle_integrity_error(error: Exception) -> None:
    message = str(error)
    if "UNIQUE" in message:
        raise HTTPException(status_code=409, detail="编码或单号已存在") from error
    raise HTTPException(status_code=400, detail="数据保存失败") from error


def list_contacts(kind: str, active_only: bool = False) -> list[dict]:
    table = "suppliers" if kind == "supplier" else "customers"
    where = "WHERE active = 1" if active_only else ""
    with get_db() as connection:
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table} {where} ORDER BY id DESC")]


def create_contact(kind: str, payload: ContactInput) -> dict:
    table = "suppliers" if kind == "supplier" else "customers"
    try:
        with get_db() as connection:
            cursor = connection.execute(
                f"INSERT INTO {table}(code, name, contact, phone) VALUES (?, ?, ?, ?)",
                (payload.code.strip(), payload.name.strip(), payload.contact.strip(), payload.phone.strip()),
            )
            row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
    except Exception as error:
        _handle_integrity_error(error)
    raise AssertionError("unreachable")


def list_products(active_only: bool = False) -> list[dict]:
    where = "WHERE active = 1" if active_only else ""
    with get_db() as connection:
        rows = connection.execute(
            f"""SELECT p.*, COALESCE(SUM(it.quantity_change), 0) AS available_stock
                FROM products p LEFT JOIN inventory_transactions it ON it.product_id = p.id
                {where} GROUP BY p.id ORDER BY p.id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def create_product(payload: ProductInput) -> dict:
    try:
        with get_db() as connection:
            cursor = connection.execute(
                """INSERT INTO products(sku, name, category, unit, purchase_price_cents,
                   sale_price_cents, warning_stock) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    payload.sku.strip(),
                    payload.name.strip(),
                    payload.category.strip(),
                    payload.unit.strip(),
                    cents(payload.purchase_price),
                    cents(payload.sale_price),
                    payload.warning_stock,
                ),
            )
            row = connection.execute("SELECT * FROM products WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
    except Exception as error:
        _handle_integrity_error(error)
    raise AssertionError("unreachable")


def _product_snapshots(connection, items: list) -> list[tuple]:
    if not items:
        raise HTTPException(status_code=400, detail="单据至少需要一条明细")
    snapshots = []
    seen: set[int] = set()
    for item in items:
        if item.product_id in seen:
            raise HTTPException(status_code=400, detail="同一单据不能重复添加同一商品")
        seen.add(item.product_id)
        product = connection.execute("SELECT * FROM products WHERE id = ? AND active = 1", (item.product_id,)).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail=f"商品 {item.product_id} 不存在或已停用")
        snapshots.append((product, item.quantity, cents(item.unit_price)))
    return snapshots


def create_purchase(payload: PurchaseInput, user_id: int) -> dict:
    with get_db() as connection:
        supplier = connection.execute("SELECT id FROM suppliers WHERE id = ? AND active = 1", (payload.supplier_id,)).fetchone()
        if supplier is None:
            raise HTTPException(status_code=404, detail="供应商不存在或已停用")
        snapshots = _product_snapshots(connection, payload.items)
        total = sum(quantity * price for _, quantity, price in snapshots)
        doc_no = _doc_no("CG")
        connection.execute("BEGIN")
        try:
            cursor = connection.execute(
                "INSERT INTO purchases(doc_no, supplier_id, amount_cents, created_by) VALUES (?, ?, ?, ?)",
                (doc_no, payload.supplier_id, total, user_id),
            )
            for product, quantity, price in snapshots:
                connection.execute(
                    """INSERT INTO purchase_items(purchase_id, product_id, product_sku, product_name,
                       quantity, unit_price_cents, amount_cents) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cursor.lastrowid, product["id"], product["sku"], product["name"], quantity, price, quantity * price),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_purchase(doc_no)


def post_purchase(doc_no: str, user_id: int) -> dict:
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            purchase = connection.execute("SELECT * FROM purchases WHERE doc_no = ?", (doc_no,)).fetchone()
            if purchase is None:
                raise HTTPException(status_code=404, detail="采购单不存在")
            if purchase["status"] == "posted":
                raise HTTPException(status_code=409, detail="采购单已过账，不能重复操作")
            items = connection.execute("SELECT * FROM purchase_items WHERE purchase_id = ?", (purchase["id"],)).fetchall()
            for item in items:
                connection.execute(
                    "INSERT INTO inventory_transactions(product_id, transaction_type, document_no, quantity_change, user_id) VALUES (?, 'purchase', ?, ?, ?)",
                    (item["product_id"], doc_no, item["quantity"], user_id),
                )
            connection.execute(
                "UPDATE purchases SET status = 'posted', posted_at = CURRENT_TIMESTAMP WHERE id = ?",
                (purchase["id"],),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_purchase(doc_no)


def get_purchase(doc_no: str) -> dict:
    with get_db() as connection:
        row = connection.execute("SELECT * FROM purchases WHERE doc_no = ?", (doc_no,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="采购单不存在")
        result = dict(row)
        items = [dict(item) for item in connection.execute("SELECT * FROM purchase_items WHERE purchase_id = ?", (row["id"],))]
        returned = {
            item["product_id"]: item["quantity"]
            for item in connection.execute(
                """SELECT ri.product_id, SUM(ri.quantity) AS quantity
                   FROM purchase_returns r JOIN purchase_return_items ri ON ri.return_id = r.id
                   WHERE r.source_doc_no = ? AND r.status = 'posted' GROUP BY ri.product_id""",
                (doc_no,),
            )
        }
        result["items"] = [
            {**item, "returned_quantity": returned.get(item["product_id"], 0), "remaining_return_quantity": item["quantity"] - returned.get(item["product_id"], 0)}
            for item in items
        ]
        return result


def list_purchases() -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            """SELECT p.*, s.code AS supplier_code, s.name AS supplier_name
               FROM purchases p JOIN suppliers s ON s.id = p.supplier_id ORDER BY p.id DESC LIMIT 500"""
        ).fetchall()
    return [dict(row) for row in rows]


def create_sale(payload: SaleInput, user_id: int) -> dict:
    with get_db() as connection:
        customer = connection.execute("SELECT id FROM customers WHERE id = ? AND active = 1", (payload.customer_id,)).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="客户不存在或已停用")
        snapshots = _product_snapshots(connection, payload.items)
        total = sum(quantity * price for _, quantity, price in snapshots)
        doc_no = _doc_no("XS")
        connection.execute("BEGIN")
        try:
            cursor = connection.execute(
                "INSERT INTO sales(doc_no, customer_id, amount_cents, created_by) VALUES (?, ?, ?, ?)",
                (doc_no, payload.customer_id, total, user_id),
            )
            for product, quantity, price in snapshots:
                connection.execute(
                    """INSERT INTO sale_items(sale_id, product_id, product_sku, product_name,
                       quantity, unit_price_cents, amount_cents) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cursor.lastrowid, product["id"], product["sku"], product["name"], quantity, price, quantity * price),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_sale(doc_no)


def post_sale(doc_no: str, user_id: int) -> dict:
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            sale = connection.execute("SELECT * FROM sales WHERE doc_no = ?", (doc_no,)).fetchone()
            if sale is None:
                raise HTTPException(status_code=404, detail="销售单不存在")
            if sale["status"] == "posted":
                raise HTTPException(status_code=409, detail="销售单已过账，不能重复操作")
            items = connection.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale["id"],)).fetchall()
            for item in items:
                stock = connection.execute(
                    "SELECT COALESCE(SUM(quantity_change), 0) AS stock FROM inventory_transactions WHERE product_id = ?",
                    (item["product_id"],),
                ).fetchone()["stock"]
                if stock < item["quantity"]:
                    raise HTTPException(status_code=409, detail=f"商品 {item['product_name']} 库存不足，当前库存 {stock}")
            for item in items:
                connection.execute(
                    "INSERT INTO inventory_transactions(product_id, transaction_type, document_no, quantity_change, user_id) VALUES (?, 'sale', ?, ?, ?)",
                    (item["product_id"], doc_no, -item["quantity"], user_id),
                )
            connection.execute("UPDATE sales SET status = 'posted', posted_at = CURRENT_TIMESTAMP WHERE id = ?", (sale["id"],))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_sale(doc_no)


def get_sale(doc_no: str) -> dict:
    with get_db() as connection:
        row = connection.execute("SELECT * FROM sales WHERE doc_no = ?", (doc_no,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="销售单不存在")
        result = dict(row)
        items = [dict(item) for item in connection.execute("SELECT * FROM sale_items WHERE sale_id = ?", (row["id"],))]
        returned = {
            item["product_id"]: item["quantity"]
            for item in connection.execute(
                """SELECT ri.product_id, SUM(ri.quantity) AS quantity
                   FROM sales_returns r JOIN sales_return_items ri ON ri.return_id = r.id
                   WHERE r.source_doc_no = ? AND r.status = 'posted' GROUP BY ri.product_id""",
                (doc_no,),
            )
        }
        result["items"] = [
            {**item, "returned_quantity": returned.get(item["product_id"], 0), "remaining_return_quantity": item["quantity"] - returned.get(item["product_id"], 0)}
            for item in items
        ]
        return result


def list_sales() -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            """SELECT s.*, c.code AS customer_code, c.name AS customer_name
               FROM sales s JOIN customers c ON c.id = s.customer_id ORDER BY s.id DESC LIMIT 500"""
        ).fetchall()
    return [dict(row) for row in rows]


def _create_return(payload: ReturnCreateInput, user_id: int, source_kind: str) -> dict:
    is_purchase = source_kind == "purchase"
    source_table = "purchases" if is_purchase else "sales"
    source_items_table = "purchase_items" if is_purchase else "sale_items"
    returns_table = "purchase_returns" if is_purchase else "sales_returns"
    return_items_table = "purchase_return_items" if is_purchase else "sales_return_items"
    prefix = "CGTH" if is_purchase else "XSTH"
    with get_db() as connection:
        source = connection.execute(
            f"SELECT * FROM {source_table} WHERE doc_no = ? AND status = 'posted'",
            (payload.source_doc_no,),
        ).fetchone()
        if source is None:
            raise HTTPException(status_code=404, detail="原单据不存在或尚未过账")
        source_items = {
            row["product_id"]: row
            for row in connection.execute(
                f"SELECT * FROM {source_items_table} WHERE {source_items_table[:-6]}_id = ?",
                (source["id"],),
            ).fetchall()
        }
        product_ids = [item.product_id for item in payload.items]
        if len(product_ids) != len(set(product_ids)):
            raise HTTPException(status_code=400, detail="退货明细不能重复商品")
        existing_rows = connection.execute(
            f"""SELECT ri.product_id, COALESCE(SUM(ri.quantity), 0) AS returned
                FROM {returns_table} r JOIN {return_items_table} ri ON ri.return_id = r.id
                WHERE r.source_doc_no = ? AND r.status = 'posted' GROUP BY ri.product_id""",
            (payload.source_doc_no,),
        ).fetchall()
        already_returned = {row["product_id"]: row["returned"] for row in existing_rows}
        rows = []
        for item in payload.items:
            source_item = source_items.get(item.product_id)
            if source_item is None:
                raise HTTPException(status_code=400, detail="退货商品不在原单据中")
            remaining = source_item["quantity"] - already_returned.get(item.product_id, 0)
            if item.quantity > remaining:
                raise HTTPException(status_code=409, detail=f"商品 {source_item['product_name']} 最多可退 {remaining}")
            rows.append((source_item, item.quantity))
        doc_no = _doc_no(prefix)
        connection.execute("BEGIN")
        try:
            cursor = connection.execute(
                f"INSERT INTO {returns_table}(doc_no, source_doc_no, created_by) VALUES (?, ?, ?)",
                (doc_no, payload.source_doc_no, user_id),
            )
            for source_item, quantity in rows:
                price = source_item["unit_price_cents"]
                connection.execute(
                    f"""INSERT INTO {return_items_table}(return_id, product_id, product_sku, product_name,
                       quantity, unit_price_cents, amount_cents) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cursor.lastrowid, source_item["product_id"], source_item["product_sku"], source_item["product_name"], quantity, price, quantity * price),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_return(doc_no, source_kind)


def get_return(doc_no: str, source_kind: str) -> dict:
    is_purchase = source_kind == "purchase"
    returns_table = "purchase_returns" if is_purchase else "sales_returns"
    return_items_table = "purchase_return_items" if is_purchase else "sales_return_items"
    with get_db() as connection:
        row = connection.execute(f"SELECT * FROM {returns_table} WHERE doc_no = ?", (doc_no,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="退货单不存在")
        result = dict(row)
        result["items"] = [dict(item) for item in connection.execute(f"SELECT * FROM {return_items_table} WHERE return_id = ?", (row["id"],))]
        return result


def list_returns(source_kind: str) -> list[dict]:
    """Return posted/draft return documents with their source party and totals."""
    is_purchase = source_kind == "purchase"
    returns_table = "purchase_returns" if is_purchase else "sales_returns"
    return_items_table = "purchase_return_items" if is_purchase else "sales_return_items"
    source_table = "purchases" if is_purchase else "sales"
    party_table = "suppliers" if is_purchase else "customers"
    party_key = "supplier_id" if is_purchase else "customer_id"
    party_name = "supplier_name" if is_purchase else "customer_name"
    with get_db() as connection:
        rows = connection.execute(
            f"""SELECT r.doc_no, r.source_doc_no, r.status, r.created_at, r.posted_at,
                       s.{party_key} AS party_id, p.name AS {party_name},
                       COALESCE(SUM(ri.quantity), 0) AS total_quantity,
                       COALESCE(SUM(ri.amount_cents), 0) AS amount_cents
                FROM {returns_table} r
                JOIN {source_table} s ON s.doc_no = r.source_doc_no
                JOIN {party_table} p ON p.id = s.{party_key}
                LEFT JOIN {return_items_table} ri ON ri.return_id = r.id
                GROUP BY r.id
                ORDER BY r.id DESC LIMIT 500"""
        ).fetchall()
    return [{**dict(row), "amount": row["amount_cents"] / 100} for row in rows]


def post_return(doc_no: str, user_id: int, source_kind: str) -> dict:
    is_purchase = source_kind == "purchase"
    returns_table = "purchase_returns" if is_purchase else "sales_returns"
    return_items_table = "purchase_return_items" if is_purchase else "sales_return_items"
    source_table = "purchases" if is_purchase else "sales"
    source_items_table = "purchase_items" if is_purchase else "sale_items"
    movement = -1 if is_purchase else 1
    transaction_type = "purchase_return" if is_purchase else "sale_return"
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(f"SELECT * FROM {returns_table} WHERE doc_no = ?", (doc_no,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="退货单不存在")
            if row["status"] == "posted":
                raise HTTPException(status_code=409, detail="退货单已过账，不能重复操作")
            items = connection.execute(f"SELECT * FROM {return_items_table} WHERE return_id = ?", (row["id"],)).fetchall()
            source = connection.execute(f"SELECT * FROM {source_table} WHERE doc_no = ? AND status = 'posted'", (row["source_doc_no"],)).fetchone()
            if source is None:
                raise HTTPException(status_code=409, detail="原单据状态无效")
            for item in items:
                source_item = connection.execute(
                    f"SELECT quantity FROM {source_items_table} WHERE {source_items_table[:-6]}_id = ? AND product_id = ?",
                    (source["id"], item["product_id"]),
                ).fetchone()
                returned = connection.execute(
                    f"""SELECT COALESCE(SUM(ri.quantity), 0) FROM {returns_table} r
                        JOIN {return_items_table} ri ON ri.return_id = r.id
                        WHERE r.source_doc_no = ? AND r.status = 'posted' AND ri.product_id = ?""",
                    (row["source_doc_no"], item["product_id"]),
                ).fetchone()[0]
                if source_item is None or returned + item["quantity"] > source_item["quantity"]:
                    raise HTTPException(status_code=409, detail=f"商品 {item['product_name']} 的累计退货量超过原单数量")
                if is_purchase:
                    stock = connection.execute(
                        "SELECT COALESCE(SUM(quantity_change), 0) AS stock FROM inventory_transactions WHERE product_id = ?",
                        (item["product_id"],),
                    ).fetchone()["stock"]
                    if stock < item["quantity"]:
                        raise HTTPException(status_code=409, detail=f"商品 {item['product_name']} 当前库存不足，无法退货")
            for item in items:
                connection.execute(
                    "INSERT INTO inventory_transactions(product_id, transaction_type, document_no, quantity_change, user_id) VALUES (?, ?, ?, ?, ?)",
                    (item["product_id"], transaction_type, doc_no, movement * item["quantity"], user_id),
                )
            connection.execute(f"UPDATE {returns_table} SET status = 'posted', posted_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_return(doc_no, source_kind)


def create_loan(payload: LoanInput, user_id: int) -> dict:
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            snapshots = _product_snapshots(connection, payload.items)
            for product, quantity, _price in snapshots:
                stock = connection.execute(
                    "SELECT COALESCE(SUM(quantity_change), 0) AS stock FROM inventory_transactions WHERE product_id = ?",
                    (product["id"],),
                ).fetchone()["stock"]
                if stock < quantity:
                    raise HTTPException(status_code=409, detail=f"商品 {product['name']} 当前库存不足")
            doc_no = _doc_no("JK")
            cursor = connection.execute(
                "INSERT INTO loans(doc_no, borrower, expected_return_date, created_by) VALUES (?, ?, ?, ?)",
                (doc_no, payload.borrower.strip(), payload.expected_return_date.isoformat() if payload.expected_return_date else None, user_id),
            )
            for product, quantity, _price in snapshots:
                connection.execute(
                    "INSERT INTO loan_items(loan_id, product_id, product_sku, product_name, quantity) VALUES (?, ?, ?, ?, ?)",
                    (cursor.lastrowid, product["id"], product["sku"], product["name"], quantity),
                )
                connection.execute(
                    "INSERT INTO inventory_transactions(product_id, transaction_type, document_no, quantity_change, user_id) VALUES (?, 'loan', ?, ?, ?)",
                    (product["id"], doc_no, -quantity, user_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_loan(doc_no)


def get_loan(doc_no: str) -> dict:
    with get_db() as connection:
        row = connection.execute("SELECT * FROM loans WHERE doc_no = ?", (doc_no,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="借出单不存在")
        result = dict(row)
        result["items"] = [dict(item) for item in connection.execute("SELECT * FROM loan_items WHERE loan_id = ?", (row["id"],))]
        return result


def return_loan(doc_no: str, payload: ReturnInput, user_id: int) -> dict:
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            loan = connection.execute("SELECT * FROM loans WHERE doc_no = ?", (doc_no,)).fetchone()
            if loan is None:
                raise HTTPException(status_code=404, detail="借出单不存在")
            loan_items = {row["product_id"]: row for row in connection.execute("SELECT * FROM loan_items WHERE loan_id = ?", (loan["id"],)).fetchall()}
            for item in payload.items:
                loan_item = loan_items.get(item.product_id)
                if loan_item is None:
                    raise HTTPException(status_code=400, detail="归还商品不在借出单中")
                remaining = loan_item["quantity"] - loan_item["returned_quantity"]
                if item.quantity > remaining:
                    raise HTTPException(status_code=409, detail=f"商品 {loan_item['product_name']} 最多可归还 {remaining}")
                connection.execute("UPDATE loan_items SET returned_quantity = returned_quantity + ? WHERE id = ?", (item.quantity, loan_item["id"]))
                connection.execute(
                    "INSERT INTO inventory_transactions(product_id, transaction_type, document_no, quantity_change, user_id) VALUES (?, 'loan_return', ?, ?, ?)",
                    (item.product_id, doc_no, item.quantity, user_id),
                )
            remaining_count = connection.execute("SELECT COUNT(*) FROM loan_items WHERE loan_id = ? AND returned_quantity < quantity", (loan["id"],)).fetchone()[0]
            status_value = "partial" if remaining_count else "returned"
            connection.execute("UPDATE loans SET status = ? WHERE id = ?", (status_value, loan["id"]))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return get_loan(doc_no)


def inventory() -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            """SELECT p.id, p.sku, p.name, p.category, p.unit, p.warning_stock,
                      COALESCE((SELECT SUM(it.quantity_change) FROM inventory_transactions it WHERE it.product_id = p.id), 0) AS available_stock,
                      COALESCE((SELECT SUM(li.quantity - li.returned_quantity)
                                FROM loan_items li JOIN loans l ON l.id = li.loan_id
                                WHERE li.product_id = p.id AND l.status != 'returned'), 0) AS loaned_quantity
               FROM products p WHERE p.active = 1 ORDER BY p.name"""
        ).fetchall()
    return [dict(row) for row in rows]


def inventory_transactions() -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            """SELECT it.*, p.sku, p.name, u.username FROM inventory_transactions it
               JOIN products p ON p.id = it.product_id JOIN users u ON u.id = it.user_id
               ORDER BY it.id DESC LIMIT 500"""
        ).fetchall()
    return [dict(row) for row in rows]


def list_loans() -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            """SELECT l.*, u.username,
                      COALESCE(SUM(li.quantity), 0) AS total_quantity,
                      COALESCE(SUM(li.returned_quantity), 0) AS returned_quantity
               FROM loans l JOIN users u ON u.id = l.created_by
               LEFT JOIN loan_items li ON li.loan_id = l.id
               GROUP BY l.id ORDER BY l.id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def backup_database() -> dict:
    source = get_database_path()
    if not source.exists():
        raise HTTPException(status_code=404, detail="数据库尚未初始化")
    backup_dir = get_data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"inventory_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db"
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        source_connection.close()
        target_connection.close()
    return {"path": str(target), "created_at": datetime.now(timezone.utc).isoformat()}


def list_backups() -> list[dict]:
    backup_dir = get_data_dir() / "backups"
    if not backup_dir.exists():
        return []
    return [
        {"name": path.name, "path": str(path), "size_bytes": path.stat().st_size}
        for path in sorted(backup_dir.glob("inventory_*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file()
    ]


def _date_predicate(column: str, start_date: date | None, end_date: date | None) -> tuple[str, list[str]]:
    clauses = []
    values = []
    if start_date is not None:
        clauses.append(f"date({column}) >= ?")
        values.append(start_date.isoformat())
    if end_date is not None:
        clauses.append(f"date({column}) <= ?")
        values.append(end_date.isoformat())
    return (" AND ".join(clauses) if clauses else "1 = 1", values)


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")


def report_loans(start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    _validate_date_range(start_date, end_date)
    where, values = _date_predicate("l.created_at", start_date, end_date)
    with get_db() as connection:
        rows = connection.execute(
            f"""SELECT l.*, u.username,
                      COALESCE(SUM(li.quantity), 0) AS total_quantity,
                      COALESCE(SUM(li.returned_quantity), 0) AS returned_quantity
               FROM loans l JOIN users u ON u.id = l.created_by
               LEFT JOIN loan_items li ON li.loan_id = l.id
               WHERE {where}
               GROUP BY l.id ORDER BY l.id DESC""",
            values,
        ).fetchall()
    today = date.today().isoformat()
    return [
        {
            **dict(row),
            "remaining_quantity": row["total_quantity"] - row["returned_quantity"],
            "overdue": bool(row["expected_return_date"] and row["expected_return_date"] < today and row["status"] != "returned"),
        }
        for row in rows
    ]


def report_summary(start_date: date | None = None, end_date: date | None = None) -> dict:
    _validate_date_range(start_date, end_date)
    purchase_filter, purchase_values = _date_predicate("p.posted_at", start_date, end_date)
    purchase_return_filter, purchase_return_values = _date_predicate("r.posted_at", start_date, end_date)
    sales_filter, sales_values = _date_predicate("s.posted_at", start_date, end_date)
    sales_return_filter, sales_return_values = _date_predicate("r.posted_at", start_date, end_date)
    with get_db() as connection:
        values = connection.execute(
            f"""SELECT
                 (SELECT COUNT(*) FROM products WHERE active = 1) AS product_count,
                 (SELECT COUNT(*) FROM suppliers WHERE active = 1) AS supplier_count,
                 (SELECT COUNT(*) FROM customers WHERE active = 1) AS customer_count,
                 (SELECT COUNT(*) FROM purchases p WHERE p.status = 'posted' AND {purchase_filter}) AS purchase_count,
                 (SELECT COALESCE(SUM(p.amount_cents), 0) FROM purchases p WHERE p.status = 'posted' AND {purchase_filter}) AS purchase_amount_cents,
                 (SELECT COUNT(*) FROM purchase_returns r WHERE r.status = 'posted' AND {purchase_return_filter}) AS purchase_return_count,
                 (SELECT COALESCE(SUM(ri.amount_cents), 0) FROM purchase_returns r JOIN purchase_return_items ri ON ri.return_id = r.id WHERE r.status = 'posted' AND {purchase_return_filter}) AS purchase_return_cents,
                 (SELECT COUNT(*) FROM sales s WHERE s.status = 'posted' AND {sales_filter}) AS sale_count,
                 (SELECT COALESCE(SUM(s.amount_cents), 0) FROM sales s WHERE s.status = 'posted' AND {sales_filter}) AS sale_amount_cents,
                 (SELECT COUNT(*) FROM sales_returns r WHERE r.status = 'posted' AND {sales_return_filter}) AS sales_return_count,
                 (SELECT COALESCE(SUM(ri.amount_cents), 0) FROM sales_returns r JOIN sales_return_items ri ON ri.return_id = r.id WHERE r.status = 'posted' AND {sales_return_filter}) AS sales_return_cents,
                 (SELECT COUNT(*) FROM loans WHERE status != 'returned') AS open_loan_count"""
            , purchase_values + purchase_values + purchase_return_values + purchase_return_values + sales_values + sales_values + sales_return_values + sales_return_values
        ).fetchone()
        inventory_rows = connection.execute(
            """SELECT p.sku, p.name, p.category, p.warning_stock,
                      COALESCE(SUM(it.quantity_change), 0) AS available_stock,
                      COALESCE((SELECT SUM(li.quantity - li.returned_quantity) FROM loan_items li JOIN loans l ON l.id = li.loan_id WHERE li.product_id = p.id AND l.status != 'returned'), 0) AS loaned_quantity
               FROM products p LEFT JOIN inventory_transactions it ON it.product_id = p.id
               WHERE p.active = 1 GROUP BY p.id ORDER BY available_stock ASC, p.name"""
        ).fetchall()
    purchase_net_cents = values["purchase_amount_cents"] - values["purchase_return_cents"]
    sales_net_cents = values["sale_amount_cents"] - values["sales_return_cents"]
    return {
        **dict(values),
        "purchase_amount": values["purchase_amount_cents"] / 100,
        "purchase_return_amount": values["purchase_return_cents"] / 100,
        "purchase_net_cents": purchase_net_cents,
        "purchase_net_amount": purchase_net_cents / 100,
        "sale_amount": values["sale_amount_cents"] / 100,
        "sales_return_amount": values["sales_return_cents"] / 100,
        "sales_net_cents": sales_net_cents,
        "sales_net_amount": sales_net_cents / 100,
        "low_stock": [dict(row) for row in inventory_rows if row["available_stock"] <= row["warning_stock"]],
    }


def report_sales(start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    _validate_date_range(start_date, end_date)
    sales_filter, sales_values = _date_predicate("s.posted_at", start_date, end_date)
    returns_filter, returns_values = _date_predicate("r.posted_at", start_date, end_date)
    with get_db() as connection:
        rows = connection.execute(
            f"""WITH sold AS (
                   SELECT si.product_id, si.product_sku AS sku, si.product_name AS name,
                          SUM(si.quantity) AS quantity, SUM(si.amount_cents) AS amount_cents
                   FROM sales s JOIN sale_items si ON si.sale_id = s.id
                   WHERE s.status = 'posted' AND {sales_filter}
                   GROUP BY si.product_id, si.product_sku, si.product_name
               ), returned AS (
                   SELECT ri.product_id, ri.product_sku AS sku, ri.product_name AS name,
                          SUM(ri.quantity) AS quantity, SUM(ri.amount_cents) AS amount_cents
                   FROM sales_returns r JOIN sales_return_items ri ON ri.return_id = r.id
                   WHERE r.status = 'posted' AND {returns_filter}
                   GROUP BY ri.product_id, ri.product_sku, ri.product_name
               ), products AS (
                   SELECT product_id FROM sold UNION SELECT product_id FROM returned
               )
               SELECT COALESCE(sold.sku, returned.sku) AS sku,
                      COALESCE(sold.name, returned.name) AS name,
                      COALESCE(sold.quantity, 0) AS quantity,
                      COALESCE(returned.quantity, 0) AS returned_quantity,
                      COALESCE(sold.quantity, 0) - COALESCE(returned.quantity, 0) AS net_quantity,
                      COALESCE(sold.amount_cents, 0) AS amount_cents,
                      COALESCE(returned.amount_cents, 0) AS returned_cents,
                      COALESCE(sold.amount_cents, 0) - COALESCE(returned.amount_cents, 0) AS net_cents
               FROM products k
               LEFT JOIN sold ON sold.product_id = k.product_id
               LEFT JOIN returned ON returned.product_id = k.product_id
               ORDER BY net_quantity DESC, net_cents DESC""",
            sales_values + returns_values,
        ).fetchall()
    return [
        {**dict(row), "amount": row["amount_cents"] / 100, "returned_amount": row["returned_cents"] / 100, "net_amount": row["net_cents"] / 100}
        for row in rows
    ]


def report_purchases(start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    _validate_date_range(start_date, end_date)
    purchase_filter, purchase_values = _date_predicate("p.posted_at", start_date, end_date)
    returns_filter, returns_values = _date_predicate("r.posted_at", start_date, end_date)
    with get_db() as connection:
        rows = connection.execute(
            f"""WITH bought AS (
                   SELECT pi.product_id, pi.product_sku AS sku, pi.product_name AS name,
                          SUM(pi.quantity) AS quantity, SUM(pi.amount_cents) AS amount_cents
                   FROM purchases p JOIN purchase_items pi ON pi.purchase_id = p.id
                   WHERE p.status = 'posted' AND {purchase_filter}
                   GROUP BY pi.product_id, pi.product_sku, pi.product_name
               ), returned AS (
                   SELECT ri.product_id, ri.product_sku AS sku, ri.product_name AS name,
                          SUM(ri.quantity) AS quantity, SUM(ri.amount_cents) AS amount_cents
                   FROM purchase_returns r JOIN purchase_return_items ri ON ri.return_id = r.id
                   WHERE r.status = 'posted' AND {returns_filter}
                   GROUP BY ri.product_id, ri.product_sku, ri.product_name
               ), products AS (
                   SELECT product_id FROM bought UNION SELECT product_id FROM returned
               )
               SELECT COALESCE(bought.sku, returned.sku) AS sku,
                      COALESCE(bought.name, returned.name) AS name,
                      COALESCE(bought.quantity, 0) AS quantity,
                      COALESCE(returned.quantity, 0) AS returned_quantity,
                      COALESCE(bought.quantity, 0) - COALESCE(returned.quantity, 0) AS net_quantity,
                      COALESCE(bought.amount_cents, 0) AS amount_cents,
                      COALESCE(returned.amount_cents, 0) AS returned_cents,
                      COALESCE(bought.amount_cents, 0) - COALESCE(returned.amount_cents, 0) AS net_cents
               FROM products k
               LEFT JOIN bought ON bought.product_id = k.product_id
               LEFT JOIN returned ON returned.product_id = k.product_id
               ORDER BY net_quantity DESC, net_cents DESC""",
            purchase_values + returns_values,
        ).fetchall()
    return [
        {**dict(row), "amount": row["amount_cents"] / 100, "returned_amount": row["returned_cents"] / 100, "net_amount": row["net_cents"] / 100}
        for row in rows
    ]


def report_daily(start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    _validate_date_range(start_date, end_date)
    queries = [
        ("purchase", "purchases p", "p.amount_cents", "p.posted_at", "p.status = 'posted'", 1),
        ("purchase_return", "purchase_returns r JOIN purchase_return_items ri ON ri.return_id = r.id", "ri.amount_cents", "r.posted_at", "r.status = 'posted'", -1),
        ("sale", "sales s", "s.amount_cents", "s.posted_at", "s.status = 'posted'", 1),
        ("sale_return", "sales_returns r JOIN sales_return_items ri ON ri.return_id = r.id", "ri.amount_cents", "r.posted_at", "r.status = 'posted'", -1),
    ]
    parts, params = [], []
    for kind, table, amount, date_column, condition, sign in queries:
        where, values = _date_predicate(date_column, start_date, end_date)
        parts.append(f"SELECT date({date_column}) AS day, '{kind}' AS kind, {amount} * {sign} AS amount_cents FROM {table} WHERE {condition} AND {where}")
        params.extend(values)
    with get_db() as connection:
        rows = connection.execute(
            f"""WITH events AS ({' UNION ALL '.join(parts)})
                SELECT day,
                       SUM(CASE WHEN kind IN ('purchase', 'purchase_return') THEN amount_cents ELSE 0 END) AS purchase_net_cents,
                       SUM(CASE WHEN kind IN ('sale', 'sale_return') THEN amount_cents ELSE 0 END) AS sales_net_cents
                FROM events GROUP BY day ORDER BY day""",
            params,
        ).fetchall()
    return [{**dict(row), "purchase_net": row["purchase_net_cents"] / 100, "sales_net": row["sales_net_cents"] / 100} for row in rows]


def restore_database(payload: RestoreRequest) -> dict:
    source = Path(payload.path).expanduser().resolve()
    backup_dir = (get_data_dir() / "backups").resolve()
    if not source.is_file() or not source.is_relative_to(backup_dir) or source.suffix.lower() != ".db":
        raise HTTPException(status_code=400, detail="只能恢复当前应用备份目录中的 .db 文件")
    target = get_database_path().resolve()
    if source == target:
        raise HTTPException(status_code=400, detail="不能把当前数据库作为恢复源")
    before_restore = backup_database()
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    except sqlite3.DatabaseError as error:
        target_connection.rollback()
        raise HTTPException(status_code=400, detail="备份文件无效，恢复失败") from error
    finally:
        source_connection.close()
        target_connection.close()
    return {"restored_from": str(source), "before_restore_backup": before_restore["path"]}

