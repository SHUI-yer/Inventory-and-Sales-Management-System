from __future__ import annotations

import argparse
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from client.api_client import ApiClient, ApiError


def configure_styles(root: tk.Misc) -> None:
    """Use consistent spacing and readable table rows across Windows DPI modes."""
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    style.configure("App.TButton", padding=(10, 7), font=("Microsoft YaHei UI", 10))
    style.configure("Nav.TButton", padding=(10, 8), font=("Microsoft YaHei UI", 10))
    style.configure("Toolbar.TButton", padding=(9, 6), font=("Microsoft YaHei UI", 10))
    style.configure("Treeview", rowheight=30, font=("Microsoft YaHei UI", 10))
    style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), padding=(6, 7))


def set_window_size(root: tk.Tk, width: int, height: int, min_width: int, min_height: int) -> None:
    """Fit a sensible window size to the current monitor instead of clipping it."""
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    actual_width = min(width, max(min_width, screen_width - 80))
    actual_height = min(height, max(min_height, screen_height - 90))
    root.geometry(f"{actual_width}x{actual_height}")
    root.minsize(min(min_width, actual_width), min(min_height, actual_height))


class LoginWindow:
    def __init__(self, root: tk.Tk, api_url: str):
        self.root = root
        self.api_url = api_url
        self.api = ApiClient(api_url)
        configure_styles(root)
        self.root.title("进销存管理系统 - 登录")
        # Keep enough vertical room for the form, status text and login button
        # on Windows with 125%/150% display scaling.
        self.root.geometry("560x410")
        self.root.minsize(520, 380)
        self.root.resizable(True, True)

        frame = ttk.Frame(root, padding=(36, 30, 36, 28))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="进销存管理系统", font=("Microsoft YaHei UI", 20, "bold")).pack(pady=(0, 22))
        form = ttk.Frame(frame)
        form.pack(fill="x")
        ttk.Label(form, text="服务器地址").grid(row=0, column=0, sticky="w", padx=(0, 14), pady=8)
        self.url_var = tk.StringVar(value=api_url)
        ttk.Entry(form, textvariable=self.url_var).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Label(form, text="账号").grid(row=1, column=0, sticky="w", padx=(0, 14), pady=8)
        self.username = ttk.Entry(form, width=32)
        self.username.insert(0, "admin")
        self.username.grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Label(form, text="密码").grid(row=2, column=0, sticky="w", padx=(0, 14), pady=8)
        self.password = ttk.Entry(form, show="*", width=32)
        self.password.insert(0, "admin123")
        self.password.grid(row=2, column=1, sticky="ew", pady=8)
        form.columnconfigure(1, weight=1)
        self.status = ttk.Label(frame, text="默认账号：admin / admin123", foreground="#666666")
        self.status.pack(anchor="w", pady=(14, 18))
        self.login_button = ttk.Button(frame, text="登录", command=self.login)
        self.login_button.pack(fill="x", ipady=4)
        self.password.bind("<Return>", lambda _event: self.login())
        self.username.focus_set()

    def login(self) -> None:
        self.login_button.configure(state="disabled")
        self.status.configure(text="正在连接……")
        self.root.update_idletasks()
        try:
            if self.url_var.get().rstrip("/") != self.api.base_url:
                self.api.close()
                self.api = ApiClient(self.url_var.get().strip())
            user = self.api.login(self.username.get().strip(), self.password.get())
        except ApiError as error:
            self.status.configure(text=str(error))
            messagebox.showerror("登录失败", str(error), parent=self.root)
            self.login_button.configure(state="normal")
            return
        self.root.destroy()
        open_dashboard(self.api, user)


class Dashboard:
    def __init__(self, root: tk.Tk, api: ApiClient, user: dict):
        self.root = root
        self.api = api
        self.user = user
        configure_styles(root)
        self.root.title(f"进销存管理系统 - {user['display_name']}")
        set_window_size(self.root, 1200, 760, 1000, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        top = ttk.Frame(root, padding=(22, 16, 22, 12))
        top.pack(fill="x")
        ttk.Label(top, text="进销存管理系统", font=("Microsoft YaHei UI", 20, "bold")).pack(side="left")
        ttk.Label(top, text=f"用户：{user['username']} | 角色：{user['role_name']}", foreground="#555555", font=("Microsoft YaHei UI", 10)).pack(side="right", pady=(5, 0))
        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=22)
        body = ttk.Frame(root, padding=(22, 14, 22, 20))
        body.pack(fill="both", expand=True)
        nav_shell = ttk.Frame(body, width=220, padding=(0, 0, 16, 0))
        nav_shell.pack(side="left", fill="y")
        nav_shell.pack_propagate(False)
        nav_shell.rowconfigure(0, weight=1)
        nav_shell.columnconfigure(0, weight=1)
        nav_canvas = tk.Canvas(nav_shell, highlightthickness=0, borderwidth=0)
        nav_canvas.grid(row=0, column=0, sticky="nsew")
        nav_scroll = ttk.Scrollbar(nav_shell, orient="vertical", command=nav_canvas.yview)
        nav_scroll.grid(row=0, column=1, sticky="ns")
        nav_canvas.configure(yscrollcommand=nav_scroll.set)
        nav = ttk.Frame(nav_canvas, relief="groove", padding=10)
        nav_window = nav_canvas.create_window((0, 0), window=nav, anchor="nw")

        def refresh_navigation(_event=None):
            nav_canvas.configure(scrollregion=nav_canvas.bbox("all"))
            nav_canvas.itemconfigure(nav_window, width=max(nav_canvas.winfo_width(), 1))

        nav.bind("<Configure>", refresh_navigation)
        nav_canvas.bind("<Configure>", refresh_navigation)

        def scroll_navigation(event):
            if nav_canvas.winfo_height() < nav.winfo_reqheight():
                nav_canvas.yview_scroll(int(-event.delta / 120), "units")

        nav_canvas.bind("<MouseWheel>", scroll_navigation)
        nav.bind("<MouseWheel>", scroll_navigation)
        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)
        self.content = content
        ttk.Label(nav, text="功能菜单", font=("Microsoft YaHei UI", 11, "bold")).pack(fill="x", pady=(0, 8))
        navigation = [
            ("库存查询", self.show_inventory),
            ("商品资料", self.show_products),
            ("供应商", self.show_suppliers),
            ("客户", self.show_customers),
            ("采购入库", lambda: self.create_document("purchase")),
            ("销售出库", lambda: self.create_document("sale")),
            ("采购退货", lambda: self.show_returns("purchase")),
            ("客户退货", lambda: self.show_returns("sale")),
            ("借还管理", self.show_loans),
            ("经营报表", self.show_reports),
            ("修改密码", self.change_password),
        ]
        if user["role_code"] == "admin":
            navigation.extend([("用户角色", self.show_admin), ("系统管理", self.show_system)])
        for text, command in navigation:
            button = ttk.Button(nav, text=text, command=command, style="Nav.TButton")
            button.pack(fill="x", pady=3)
            button.bind("<MouseWheel>", scroll_navigation)
        self.show_inventory()

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def page_header(self, title: str, actions=()):
        header = ttk.Frame(self.content)
        header.pack(fill="x", pady=(0, 12))
        title_row = ttk.Frame(header)
        title_row.pack(fill="x")
        ttk.Label(title_row, text=title, font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        if actions:
            action_bar = ttk.Frame(header)
            action_bar.pack(fill="x", pady=(10, 0))
            for label, command in actions:
                ttk.Button(action_bar, text=label, command=command, style="Toolbar.TButton").pack(side="left", padx=(0, 8))
        return header

    def show_table(self, title: str, columns: list[tuple[str, str]], rows: list[dict], actions=()):
        self.clear_content()
        self.page_header(title, actions)
        table_frame = ttk.Frame(self.content)
        table_frame.pack(fill="both", expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(table_frame, columns=[key for key, _ in columns], show="headings")
        for key, label in columns:
            table.heading(key, text=label)
            width = 110
            if key in {"path", "permission_summary"}:
                width = 220
            elif key in {"doc_no", "source_doc_no", "created_at", "posted_at"}:
                width = 140
            table.column(key, width=width, minwidth=86, anchor="center", stretch=True)
        for row in rows:
            table.insert("", "end", values=[row.get(key, "") for key, _ in columns])
        table.grid(row=0, column=0, sticky="nsew")
        self.current_tree = table
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

    def load_table(self, title: str, columns: list[tuple[str, str]], loader):
        try:
            rows = loader()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        self.show_table(title, columns, rows)

    def show_inventory(self):
        self.load_table(
            "库存查询",
            [("sku", "商品编码"), ("name", "商品名称"), ("category", "分类"), ("unit", "单位"), ("available_stock", "可用库存"), ("loaned_quantity", "借出中"), ("warning_stock", "预警值")],
            self.api.inventory,
        )

    def show_products(self):
        try:
            rows = self.api.products()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        self.show_table("商品资料", [("sku", "商品编码"), ("name", "商品名称"), ("category", "分类"), ("unit", "单位"), ("active", "状态")], rows, [("新增商品", self.add_product)])

    def show_suppliers(self):
        try:
            rows = self.api.suppliers()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        self.show_table("供应商", [("code", "编码"), ("name", "名称"), ("contact", "联系人"), ("phone", "电话"), ("active", "状态")], rows, [("新增供应商", lambda: self.add_contact("supplier"))])

    def show_customers(self):
        try:
            rows = self.api.customers()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        self.show_table("客户", [("code", "编码"), ("name", "名称"), ("contact", "联系人"), ("phone", "电话"), ("active", "状态")], rows, [("新增客户", lambda: self.add_contact("customer"))])

    def form_dialog(self, title: str, fields: list[tuple[str, str, str]], on_save):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry(f"620x{max(360, 190 + len(fields) * 42)}")
        dialog.minsize(560, 340)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        inputs = {}
        for row, (key, label, default) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=6)
            entry = ttk.Entry(frame, width=34)
            entry.insert(0, default)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            inputs[key] = entry
        frame.columnconfigure(1, weight=1)

        def save():
            values = {key: widget.get().strip() for key, widget in inputs.items()}
            try:
                on_save(values)
            except (ApiError, ValueError) as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存", command=save).pack(side="right")

    def add_product(self):
        def save(values):
            self.api.create_product({
                "sku": values["sku"],
                "name": values["name"],
                "category": values["category"],
                "unit": values["unit"],
                "purchase_price": float(values["purchase_price"]),
                "sale_price": float(values["sale_price"]),
                "warning_stock": int(values["warning_stock"]),
            })
            self.show_products()

        self.form_dialog("新增商品", [
            ("sku", "商品编码", ""),
            ("name", "商品名称", ""),
            ("category", "分类", ""),
            ("unit", "单位", "件"),
            ("purchase_price", "参考进价（元）", "0"),
            ("sale_price", "参考售价（元）", "0"),
            ("warning_stock", "库存预警值", "0"),
        ], save)

    def add_contact(self, kind: str):
        label = "供应商" if kind == "supplier" else "客户"
        creator = self.api.create_supplier if kind == "supplier" else self.api.create_customer
        refresher = self.show_suppliers if kind == "supplier" else self.show_customers

        def save(values):
            creator(values)
            refresher()

        self.form_dialog(f"新增{label}", [
            ("code", "编码", ""),
            ("name", "名称", ""),
            ("contact", "联系人", ""),
            ("phone", "电话", ""),
        ], save)

    def create_document(self, kind: str):
        try:
            parties = self.api.suppliers() if kind == "purchase" else self.api.customers()
            products = self.api.products()
        except ApiError as error:
            messagebox.showerror("无法新建单据", str(error), parent=self.root)
            return
        if not parties:
            messagebox.showwarning("缺少基础资料", "请先新增供应商或客户。", parent=self.root)
            return
        if not products:
            messagebox.showwarning("缺少基础资料", "请先新增商品。", parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        title = "采购入库" if kind == "purchase" else "销售出库"
        dialog.title(title)
        dialog.geometry("680x430")
        dialog.minsize(620, 400)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        party_label = "供应商" if kind == "purchase" else "客户"
        party_var = tk.StringVar()
        party_values = [f"{item['id']} | {item['code']} | {item['name']}" for item in parties if item["active"]]
        product_var = tk.StringVar()
        product_values = [f"{item['id']} | {item['sku']} | {item['name']}" for item in products if item["active"]]
        for row, label, variable, values in [
            (0, party_label, party_var, party_values),
            (1, "商品", product_var, product_values),
        ]:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=7)
            ttk.Combobox(frame, textvariable=variable, values=values, state="readonly", width=38).grid(row=row, column=1, pady=7)
        party_var.set(party_values[0])
        product_var.set(product_values[0])
        ttk.Label(frame, text="数量").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=7)
        quantity = ttk.Entry(frame, width=40)
        quantity.insert(0, "1")
        quantity.grid(row=2, column=1, pady=7)
        ttk.Label(frame, text="成交单价（元）").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=7)
        price = ttk.Entry(frame, width=40)
        selected = products[0]
        default_price = selected["purchase_price_cents"] if kind == "purchase" else selected["sale_price_cents"]
        price.insert(0, f"{default_price / 100:.2f}")
        price.grid(row=3, column=1, pady=7)

        def update_price(_event=None):
            value = product_var.get().split(" | ", 1)[0]
            item = next((product for product in products if str(product["id"]) == value), selected)
            amount = item["purchase_price_cents"] if kind == "purchase" else item["sale_price_cents"]
            price.delete(0, "end")
            price.insert(0, f"{amount / 100:.2f}")

        product_combo = frame.grid_slaves(row=1, column=1)[0]
        product_combo.bind("<<ComboboxSelected>>", update_price)

        def save():
            try:
                party_id = int(party_var.get().split(" | ", 1)[0])
                product_id = int(product_var.get().split(" | ", 1)[0])
                payload = {
                    "items": [{"product_id": product_id, "quantity": int(quantity.get()), "unit_price": float(price.get())}]
                }
                if kind == "purchase":
                    payload["supplier_id"] = party_id
                    document = self.api.create_purchase(payload)
                    post = self.api.post_purchase
                else:
                    payload["customer_id"] = party_id
                    document = self.api.create_sale(payload)
                    post = self.api.post_sale
            except (ValueError, ApiError) as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()
            if messagebox.askyesno("单据已保存", f"单号：{document['doc_no']}\n是否立即过账并更新库存？", parent=self.root):
                try:
                    posted = post(document["doc_no"])
                    messagebox.showinfo("过账完成", f"单据 {posted['doc_no']} 已过账。", parent=self.root)
                except ApiError as error:
                    messagebox.showerror("过账失败", str(error), parent=self.root)
            self.show_inventory()

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存单据", command=save).pack(side="right")

    def show_returns(self, kind: str):
        try:
            documents = self.api.purchases() if kind == "purchase" else self.api.sales()
            returns = self.api.purchase_returns() if kind == "purchase" else self.api.sales_returns()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        documents = [row for row in documents if row["status"] == "posted"]
        party_key = "supplier_name" if kind == "purchase" else "customer_name"
        title = "采购退货" if kind == "purchase" else "客户退货"
        rows = [{**row, "return_count": sum(1 for item in returns if item["source_doc_no"] == row["doc_no"])} for row in documents]
        self.show_table(
            title,
            [("doc_no", "原单号"), (party_key, "往来单位"), ("amount_cents", "原单金额（分）"), ("posted_at", "过账时间"), ("return_count", "退货单数")],
            rows,
            [("查看退货记录", lambda: self.show_return_history(kind, returns)), ("办理退货", lambda: self.create_return(kind, documents))],
        )

    def show_return_history(self, kind: str, returns: list[dict] | None = None):
        if returns is None:
            try:
                returns = self.api.purchase_returns() if kind == "purchase" else self.api.sales_returns()
            except ApiError as error:
                messagebox.showerror("请求失败", str(error), parent=self.root)
                return
        party_key = "supplier_name" if kind == "purchase" else "customer_name"
        self.show_table(
            "采购退货记录" if kind == "purchase" else "客户退货记录",
            [("doc_no", "退货单号"), ("source_doc_no", "原单号"), (party_key, "往来单位"), ("total_quantity", "退货数量"), ("amount", "退货金额"), ("status", "状态"), ("posted_at", "过账时间")],
            returns,
            [("返回原单", lambda: self.show_returns(kind))],
        )

    def create_return(self, kind: str, documents: list[dict]):
        if not documents:
            messagebox.showinfo("暂无可退单据", "请先完成并过账采购单或销售单。", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("采购退货" if kind == "purchase" else "客户退货")
        dialog.geometry("820x560")
        dialog.minsize(720, 460)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        doc_var = tk.StringVar()
        party_key = "supplier_name" if kind == "purchase" else "customer_name"
        doc_values = [f"{row['doc_no']} | {row[party_key]}" for row in documents]
        ttk.Label(frame, text="原单据").grid(row=0, column=0, sticky="w", pady=7, padx=(0, 12))
        doc_combo = ttk.Combobox(frame, textvariable=doc_var, values=doc_values, state="readonly", width=36)
        doc_combo.grid(row=0, column=1, columnspan=4, sticky="ew", pady=7)
        lines = ttk.Frame(frame)
        lines.grid(row=1, column=0, columnspan=5, sticky="nsew", pady=(8, 0))
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)
        quantity_inputs = {}

        def refresh_items(_event=None):
            if not doc_var.get():
                return
            doc_no = doc_var.get().split(" | ", 1)[0]
            try:
                detail = self.api.purchase(doc_no) if kind == "purchase" else self.api.sale(doc_no)
            except ApiError as error:
                messagebox.showerror("读取原单失败", str(error), parent=dialog)
                return
            for child in lines.winfo_children():
                child.destroy()
            quantity_inputs.clear()
            for column, label in enumerate(("商品", "原数量", "已退", "剩余可退", "本次退货")):
                ttk.Label(lines, text=label).grid(row=0, column=column, sticky="w", padx=6, pady=(0, 6))
            returnable = [item for item in detail["items"] if item["remaining_return_quantity"] > 0]
            if not returnable:
                ttk.Label(lines, text="该原单商品已全部退完。", foreground="#666666").grid(row=1, column=0, columnspan=5, sticky="w", pady=8)
            for row, item in enumerate(returnable, start=1):
                ttk.Label(lines, text=f"{item['product_sku']}  {item['product_name']}").grid(row=row, column=0, sticky="w", padx=6, pady=4)
                ttk.Label(lines, text=str(item["quantity"])).grid(row=row, column=1, sticky="w", padx=6, pady=4)
                ttk.Label(lines, text=str(item["returned_quantity"])).grid(row=row, column=2, sticky="w", padx=6, pady=4)
                remaining = item["remaining_return_quantity"]
                ttk.Label(lines, text=str(remaining)).grid(row=row, column=3, sticky="w", padx=6, pady=4)
                quantity = ttk.Spinbox(lines, from_=0, to=remaining, increment=1, width=8)
                quantity.set(0)
                quantity.grid(row=row, column=4, sticky="w", padx=6, pady=4)
                quantity_inputs[item["product_id"]] = quantity

        doc_combo.bind("<<ComboboxSelected>>", refresh_items)
        doc_var.set(doc_values[0])
        refresh_items()

        def save():
            try:
                source_doc_no = doc_var.get().split(" | ", 1)[0]
                items = [{"product_id": product_id, "quantity": int(widget.get())} for product_id, widget in quantity_inputs.items() if int(widget.get()) > 0]
                if not items:
                    raise ValueError("请输入至少一个商品的退货数量。")
                payload = {"source_doc_no": source_doc_no, "items": items}
                document = self.api.create_purchase_return(payload) if kind == "purchase" else self.api.create_sale_return(payload)
            except (ValueError, ApiError) as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()
            if messagebox.askyesno("退货单已保存", f"单号：{document['doc_no']}\n是否立即过账？", parent=self.root):
                try:
                    if kind == "purchase":
                        self.api.post_purchase_return(document["doc_no"])
                    else:
                        self.api.post_sale_return(document["doc_no"])
                    messagebox.showinfo("处理完成", "退货已过账并更新库存。", parent=self.root)
                except ApiError as error:
                    messagebox.showerror("过账失败", str(error), parent=self.root)
            self.show_inventory()

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=5, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存退货单", command=save).pack(side="right")

    def show_loans(self):
        try:
            rows = self.api.loans()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        self.clear_content()
        self.page_header("借还管理", [("新增借出", self.create_loan), ("归还选中", self.return_selected_loan)])
        columns = [("doc_no", "借出单号"), ("borrower", "借用人"), ("total_quantity", "借出数量"), ("returned_quantity", "已归还"), ("expected_return_date", "预计归还"), ("status", "状态"), ("created_at", "时间")]
        table_frame = ttk.Frame(self.content)
        table_frame.pack(fill="both", expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.loan_tree = ttk.Treeview(table_frame, columns=[key for key, _ in columns], show="headings")
        for key, label in columns:
            self.loan_tree.heading(key, text=label)
            width = 125
            if key in {"doc_no", "expected_return_date", "created_at"}:
                width = 140
            self.loan_tree.column(key, width=width, minwidth=86, anchor="center", stretch=True)
        for row in rows:
            self.loan_tree.insert("", "end", values=[row.get(key, "") for key, _ in columns])
        self.loan_tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.loan_tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.loan_tree.xview)
        self.loan_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

    def create_loan(self):
        try:
            products = [item for item in self.api.products() if item["active"]]
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        if not products:
            messagebox.showinfo("暂无商品", "请先建立商品资料。", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("新增商品借出")
        dialog.geometry("820x600")
        dialog.minsize(720, 520)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        borrower = ttk.Entry(frame, width=38)
        due_date = ttk.Entry(frame, width=38)
        product_values = [f"{item['id']} | {item['sku']} | {item['name']}" for item in products]
        product_var = tk.StringVar(value=product_values[0])
        product = ttk.Combobox(frame, textvariable=product_var, values=product_values, state="readonly", width=36)
        quantity = ttk.Spinbox(frame, from_=1, to=999999, increment=1, width=10)
        quantity.set(1)
        for row, label, widget in [(0, "借用人", borrower), (1, "预计归还日期", due_date), (2, "商品", product), (3, "数量", quantity)]:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=7, padx=(0, 12))
            widget.grid(row=row, column=1, pady=7)
        ttk.Label(frame, text="可留空；填写格式 YYYY-MM-DD", foreground="#666666").grid(row=1, column=2, sticky="w", padx=8)
        lines = ttk.Treeview(frame, columns=("sku", "name", "quantity"), show="headings", height=6)
        for key, label in (("sku", "商品编码"), ("name", "商品名称"), ("quantity", "数量")):
            lines.heading(key, text=label)
            lines.column(key, width=150, anchor="center")
        lines.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        selected_items = {}

        def add_item():
            try:
                product_id = int(product_var.get().split(" | ", 1)[0])
                count = int(quantity.get())
            except ValueError:
                messagebox.showerror("明细无效", "请选择商品并填写正整数数量。", parent=dialog)
                return
            if count <= 0:
                messagebox.showerror("明细无效", "数量必须大于 0。", parent=dialog)
                return
            selected_items[product_id] = selected_items.get(product_id, 0) + count
            for row in lines.get_children():
                lines.delete(row)
            by_id = {item["id"]: item for item in products}
            for item_id, item_count in selected_items.items():
                item = by_id[item_id]
                lines.insert("", "end", iid=str(item_id), values=(item["sku"], item["name"], item_count))

        def remove_item():
            for row in lines.selection():
                selected_items.pop(int(row), None)
                lines.delete(row)

        ttk.Button(frame, text="添加商品", command=add_item).grid(row=3, column=2, padx=8)
        ttk.Button(frame, text="移除选中", command=remove_item).grid(row=5, column=2, sticky="e", pady=(4, 0))
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        def save():
            try:
                if not selected_items:
                    raise ValueError("请先添加至少一种借出商品。")
                payload = {"borrower": borrower.get().strip(), "items": [{"product_id": product_id, "quantity": count, "unit_price": 0} for product_id, count in selected_items.items()]}
                if due_date.get().strip():
                    payload["expected_return_date"] = due_date.get().strip()
                document = self.api.create_loan(payload)
            except (ValueError, ApiError) as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()
            messagebox.showinfo("借出完成", f"借出单号：{document['doc_no']}", parent=self.root)
            self.show_loans()

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存借出", command=save).pack(side="right")

    def return_selected_loan(self):
        selected = self.loan_tree.selection()
        if not selected:
            messagebox.showinfo("请选择记录", "请先选择一条未完成归还的借出记录。", parent=self.root)
            return
        doc_no = self.loan_tree.item(selected[0], "values")[0]
        try:
            loan = self.api.loan(doc_no)
        except ApiError as error:
            messagebox.showerror("读取借出单失败", str(error), parent=self.root)
            return
        items = [item for item in loan["items"] if item["returned_quantity"] < item["quantity"]]
        if not items:
            messagebox.showinfo("无需归还", "该借出单已经全部归还。", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"归还借出单 {doc_no}")
        dialog.geometry("820x520")
        dialog.minsize(720, 440)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"借用人：{loan['borrower']}    单号：{doc_no}").pack(anchor="w", pady=(0, 10))
        lines = ttk.Frame(frame)
        lines.pack(fill="both", expand=True)
        for column, label in enumerate(("商品", "借出", "已归还", "剩余待还", "本次归还")):
            ttk.Label(lines, text=label).grid(row=0, column=column, sticky="w", padx=6, pady=(0, 6))
        quantity_inputs = {}
        for row, item in enumerate(items, start=1):
            remaining = item["quantity"] - item["returned_quantity"]
            ttk.Label(lines, text=f"{item['product_sku']}  {item['product_name']}").grid(row=row, column=0, sticky="w", padx=6, pady=4)
            ttk.Label(lines, text=str(item["quantity"])).grid(row=row, column=1, sticky="w", padx=6, pady=4)
            ttk.Label(lines, text=str(item["returned_quantity"])).grid(row=row, column=2, sticky="w", padx=6, pady=4)
            ttk.Label(lines, text=str(remaining)).grid(row=row, column=3, sticky="w", padx=6, pady=4)
            quantity = ttk.Spinbox(lines, from_=0, to=remaining, increment=1, width=8)
            quantity.set(0)
            quantity.grid(row=row, column=4, sticky="w", padx=6, pady=4)
            quantity_inputs[item["product_id"]] = quantity

        def save_return():
            try:
                return_items = [{"product_id": product_id, "quantity": int(widget.get())} for product_id, widget in quantity_inputs.items() if int(widget.get()) > 0]
                if not return_items:
                    raise ValueError("请输入至少一个商品的归还数量。")
                self.api.return_loan(doc_no, {"items": return_items})
            except (ValueError, ApiError) as error:
                messagebox.showerror("归还失败", str(error), parent=dialog)
                return
            dialog.destroy()
            messagebox.showinfo("归还完成", "本次归还已登记。", parent=self.root)
            self.show_loans()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="登记归还", command=save_return).pack(side="right")

    def show_admin(self):
        try:
            users = self.api.users()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        self.show_table("用户管理", [("id", "ID"), ("username", "账号"), ("display_name", "姓名"), ("role_name", "角色"), ("active", "启用"), ("created_at", "创建时间")], users, [("角色管理", self.show_roles), ("修改角色", self.change_user_role), ("重置密码", self.reset_user_password), ("启停选中用户", self.toggle_user_active), ("新增用户", self.add_user)])

    def show_roles(self):
        try:
            roles = self.api.roles()
        except ApiError as error:
            messagebox.showerror("请求失败", str(error), parent=self.root)
            return
        rows = [{**role, "permission_summary": ", ".join(role["permissions"])} for role in roles]
        self.show_table("角色管理", [("id", "ID"), ("code", "角色编码"), ("name", "角色名称"), ("active", "启用"), ("permission_summary", "权限")], rows, [("用户管理", self.show_admin), ("设置选中角色权限", self.edit_role_permissions), ("新增角色", self.add_role)])

    def toggle_user_active(self):
        selected = getattr(self, "current_tree", None)
        if selected is None or not selected.selection():
            messagebox.showinfo("请选择用户", "先在用户列表中选择一名用户。", parent=self.root)
            return
        values = selected.item(selected.selection()[0], "values")
        user_id, active = int(values[0]), str(values[4]) in {"1", "True", "true"}
        try:
            self.api.set_user_active(user_id, not active)
        except ApiError as error:
            messagebox.showerror("修改失败", str(error), parent=self.root)
            return
        self.show_admin()

    def change_user_role(self):
        selected = getattr(self, "current_tree", None)
        if selected is None or not selected.selection():
            messagebox.showinfo("请选择用户", "先在用户列表中选择一名用户。", parent=self.root)
            return
        selected_values = selected.item(selected.selection()[0], "values")
        user_id = int(selected_values[0])
        try:
            roles = [role for role in self.api.roles() if role["active"]]
        except ApiError as error:
            messagebox.showerror("读取角色失败", str(error), parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("修改用户角色")
        dialog.geometry("560x280")
        dialog.minsize(500, 240)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        role_values = [f"{role['id']} | {role['name']}" for role in roles]
        default_role = next((value for value, role in zip(role_values, roles) if role["name"] == selected_values[3]), role_values[0] if role_values else "")
        role_var = tk.StringVar(value=default_role)
        ttk.Label(frame, text="新角色").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=7)
        ttk.Combobox(frame, textvariable=role_var, values=role_values, state="readonly", width=36).grid(row=0, column=1, pady=7)

        def save():
            try:
                self.api.update_user_role(user_id, int(role_var.get().split(" | ", 1)[0]))
            except (ValueError, ApiError) as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()
            self.show_admin()

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存角色", command=save).pack(side="right")

    def reset_user_password(self):
        selected = getattr(self, "current_tree", None)
        if selected is None or not selected.selection():
            messagebox.showinfo("请选择用户", "先在用户列表中选择一名用户。", parent=self.root)
            return
        user_id = int(selected.item(selected.selection()[0], "values")[0])
        new_password = simpledialog.askstring("重置密码", "请输入新密码（至少 8 位）：", parent=self.root, show="*")
        if new_password is None:
            return
        if len(new_password) < 8:
            messagebox.showerror("密码无效", "新密码至少需要 8 位。", parent=self.root)
            return
        confirmation = simpledialog.askstring("重置密码", "请再次输入新密码：", parent=self.root, show="*")
        if confirmation != new_password:
            messagebox.showerror("密码无效", "两次输入的新密码不一致。", parent=self.root)
            return
        try:
            self.api.reset_user_password(user_id, new_password)
        except ApiError as error:
            messagebox.showerror("重置失败", str(error), parent=self.root)
            return
        messagebox.showinfo("重置完成", "密码已重置，该用户需要重新登录。", parent=self.root)
        if user_id == self.user["id"]:
            self.close()

    def edit_role_permissions(self):
        selected = getattr(self, "current_tree", None)
        if selected is None or not selected.selection():
            messagebox.showinfo("请选择角色", "先在角色列表中选择一个角色。", parent=self.root)
            return
        selected_id = int(selected.item(selected.selection()[0], "values")[0])
        try:
            roles = self.api.roles()
            permissions = self.api.permissions()
        except ApiError as error:
            messagebox.showerror("读取权限失败", str(error), parent=self.root)
            return
        role = next(item for item in roles if item["id"] == selected_id)
        if role["code"] == "admin":
            messagebox.showinfo("系统管理员", "系统管理员角色的全部权限固定，不可修改。", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"设置角色权限 - {role['name']}")
        dialog.geometry("640x560")
        dialog.minsize(560, 460)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        choices = {}
        for index, permission in enumerate(permissions):
            value = tk.BooleanVar(value=permission["code"] in role["permissions"])
            ttk.Checkbutton(frame, text=f"{permission['name']} ({permission['code']})", variable=value).grid(row=index, column=0, sticky="w", pady=3)
            choices[permission["code"]] = value

        def save():
            codes = [code for code, value in choices.items() if value.get()]
            try:
                self.api.update_role_permissions(role["id"], codes)
            except ApiError as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()
            self.show_roles()

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(permissions), column=0, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存权限", command=save).pack(side="right")

    def add_role(self):
        try:
            permissions = self.api.permissions()
        except ApiError as error:
            messagebox.showerror("读取权限失败", str(error), parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("新增角色")
        dialog.geometry("680x620")
        dialog.minsize(600, 520)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        code = ttk.Entry(frame, width=38)
        name = ttk.Entry(frame, width=38)
        for row, label, widget in [(0, "角色编码", code), (1, "角色名称", name)]:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
            widget.grid(row=row, column=1, pady=6)
        choices = {}
        for index, permission in enumerate(permissions, start=2):
            value = tk.BooleanVar(value=False)
            ttk.Checkbutton(frame, text=f"{permission['name']} ({permission['code']})", variable=value).grid(row=index, column=0, columnspan=2, sticky="w", pady=2)
            choices[permission["code"]] = value

        def save():
            try:
                self.api.create_role({"code": code.get().strip(), "name": name.get().strip(), "permission_codes": [key for key, value in choices.items() if value.get()]})
            except ApiError as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()
            self.show_roles()

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(permissions) + 2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="创建角色", command=save).pack(side="right")

    def add_user(self):
        try:
            roles = self.api.roles()
        except ApiError as error:
            messagebox.showerror("读取角色失败", str(error), parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("新增用户")
        dialog.geometry("600x360")
        dialog.minsize(540, 320)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        fields = {}
        for row, key, label, show in [(0, "username", "账号", ""), (1, "password", "密码", "*"), (2, "display_name", "姓名", "")]:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=7, padx=(0, 12))
            entry = ttk.Entry(frame, width=38, show=show)
            entry.grid(row=row, column=1, pady=7)
            fields[key] = entry
        ttk.Label(frame, text="角色").grid(row=3, column=0, sticky="w", pady=7, padx=(0, 12))
        role_values = [f"{role['id']} | {role['name']}" for role in roles if role["active"]]
        role_var = tk.StringVar(value=role_values[0])
        ttk.Combobox(frame, textvariable=role_var, values=role_values, state="readonly", width=36).grid(row=3, column=1, pady=7)

        def save():
            try:
                self.api.create_user({"username": fields["username"].get().strip(), "password": fields["password"].get(), "display_name": fields["display_name"].get().strip(), "role_id": int(role_var.get().split(" | ", 1)[0])})
            except (ValueError, ApiError) as error:
                messagebox.showerror("保存失败", str(error), parent=dialog)
                return
            dialog.destroy()
            self.show_admin()

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存用户", command=save).pack(side="right")

    def show_reports(self):
        self.clear_content()
        if not hasattr(self, "report_start_var"):
            self.report_start_var = tk.StringVar()
            self.report_end_var = tk.StringVar()
        try:
            summary = self.api.report_summary(self.report_start_var.get().strip(), self.report_end_var.get().strip())
            rows = self.api.report_sales(self.report_start_var.get().strip(), self.report_end_var.get().strip())
        except ApiError as error:
            messagebox.showerror("读取报表失败", str(error), parent=self.root)
            return
        self.report_rows = rows
        self.report_columns = [("sku", "商品编码"), ("name", "商品名称"), ("quantity", "销售数量"), ("returned_quantity", "退货数量"), ("net_quantity", "净销售数量"), ("net_amount", "净销售金额")]
        self.page_header(
            "经营报表",
            [("销售汇总", self.show_reports), ("采购汇总", self.show_purchase_report),
             ("每日趋势", self.show_daily_report), ("借出统计", self.show_loan_report),
             ("库存报表", self.show_inventory_report), ("导出 CSV", self.export_report)],
        )
        datebar = ttk.Frame(self.content)
        datebar.pack(fill="x", pady=(0, 10))
        ttk.Label(datebar, text="开始日期").pack(side="left")
        ttk.Entry(datebar, textvariable=self.report_start_var, width=12).pack(side="left", padx=(6, 14))
        ttk.Label(datebar, text="结束日期").pack(side="left")
        ttk.Entry(datebar, textvariable=self.report_end_var, width=12).pack(side="left", padx=(6, 14))
        ttk.Label(datebar, text="格式：YYYY-MM-DD", foreground="#666666").pack(side="left")
        ttk.Button(datebar, text="刷新", command=self.show_reports).pack(side="right")
        metrics = ttk.Frame(self.content)
        metrics.pack(fill="x", pady=(0, 12))
        values = [
            ("商品数", summary["product_count"]), ("供应商数", summary["supplier_count"]), ("客户数", summary["customer_count"]),
            ("采购净额", f"￥{summary['purchase_net_amount']:.2f}"), ("销售净额", f"￥{summary['sales_net_amount']:.2f}"),
            ("采购退货额", f"￥{summary['purchase_return_amount']:.2f}"), ("销售退货额", f"￥{summary['sales_return_amount']:.2f}"),
            ("低库存商品", len(summary["low_stock"])), ("未归还借出", summary["open_loan_count"]),
        ]
        for index, (label, value) in enumerate(values):
            box = ttk.Frame(metrics, relief="groove", padding=8)
            box.grid(row=index // 3, column=index % 3, padx=(0, 8), pady=(0, 8), sticky="nsew")
            ttk.Label(box, text=label, foreground="#666666").pack()
            ttk.Label(box, text=str(value), font=("Microsoft YaHei UI", 12, "bold")).pack(pady=(4, 0))
        for column in range(3):
            metrics.columnconfigure(column, weight=1)
        self._render_report_table()

    def show_purchase_report(self):
        try:
            self.report_rows = self.api.report_purchases(self.report_start_var.get().strip(), self.report_end_var.get().strip())
        except ApiError as error:
            messagebox.showerror("读取报表失败", str(error), parent=self.root)
            return
        self.report_columns = [("sku", "商品编码"), ("name", "商品名称"), ("quantity", "采购数量"), ("returned_quantity", "退货数量"), ("net_quantity", "净采购数量"), ("net_amount", "净采购金额")]
        self._render_report_table()

    def show_daily_report(self):
        try:
            self.report_rows = self.api.report_daily(self.report_start_var.get().strip(), self.report_end_var.get().strip())
        except ApiError as error:
            messagebox.showerror("读取报表失败", str(error), parent=self.root)
            return
        self.report_columns = [("day", "日期"), ("purchase_net", "采购净额"), ("sales_net", "销售净额")]
        self._render_report_table()

    def show_inventory_report(self):
        try:
            self.report_rows = self.api.report_inventory()
        except ApiError as error:
            messagebox.showerror("读取报表失败", str(error), parent=self.root)
            return
        self.report_columns = [("sku", "商品编码"), ("name", "商品名称"), ("available_stock", "可用库存"), ("loaned_quantity", "借出中"), ("warning_stock", "预警值")]
        self._render_report_table()

    def show_loan_report(self):
        try:
            self.report_rows = self.api.report_loans(self.report_start_var.get().strip(), self.report_end_var.get().strip())
        except ApiError as error:
            messagebox.showerror("读取报表失败", str(error), parent=self.root)
            return
        self.report_columns = [
            ("doc_no", "借出单号"), ("borrower", "借用人"), ("total_quantity", "借出数量"),
            ("returned_quantity", "已归还"), ("remaining_quantity", "待归还"),
            ("expected_return_date", "预计归还"), ("overdue", "是否逾期"), ("status", "状态"),
        ]
        self._render_report_table()

    def _render_report_table(self):
        if not hasattr(self, "report_table_frame") or not self.report_table_frame.winfo_exists():
            self.report_table_frame = ttk.Frame(self.content)
            self.report_table_frame.pack(fill="both", expand=True)
        for child in self.report_table_frame.winfo_children():
            child.destroy()
        table = ttk.Treeview(self.report_table_frame, columns=[key for key, _ in self.report_columns], show="headings")
        for key, label in self.report_columns:
            table.heading(key, text=label)
            table.column(key, width=120, minwidth=86, anchor="center", stretch=True)
        for row in self.report_rows:
            table.insert("", "end", values=[row.get(key, "") for key, _ in self.report_columns])
        vertical = ttk.Scrollbar(self.report_table_frame, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(self.report_table_frame, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.report_table_frame.rowconfigure(0, weight=1)
        self.report_table_frame.columnconfigure(0, weight=1)

    def export_report(self):
        if not getattr(self, "report_rows", None):
            messagebox.showinfo("暂无数据", "当前报表没有可导出的数据。", parent=self.root)
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")], initialfile="经营报表.csv")
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([label for _, label in self.report_columns])
            writer.writerows([[row.get(key, "") for key, _ in self.report_columns] for row in self.report_rows])
        messagebox.showinfo("导出完成", f"文件已保存：\n{path}", parent=self.root)

    def show_system(self):
        try:
            rows = self.api.backups()
        except ApiError as error:
            messagebox.showerror("读取备份失败", str(error), parent=self.root)
            return
        self.show_table(
            "系统管理 / 数据备份",
            [("name", "备份文件"), ("path", "服务器路径"), ("size_bytes", "大小（字节）")],
            rows,
            [("立即备份", self.backup), ("恢复选中备份", self.restore_selected_backup)],
        )

    def restore_selected_backup(self):
        selected = getattr(self, "current_tree", None)
        if selected is None or not selected.selection():
            messagebox.showinfo("请选择备份", "先在备份列表中选择一个备份文件。", parent=self.root)
            return
        values = selected.item(selected.selection()[0], "values")
        backup_path = values[1]
        if not messagebox.askyesno("确认恢复", "恢复会覆盖当前数据库，恢复前系统会自动再备份一次。是否继续？", parent=self.root):
            return
        try:
            result = self.api.restore(backup_path)
        except ApiError as error:
            messagebox.showerror("恢复失败", str(error), parent=self.root)
            return
        messagebox.showinfo("恢复完成", f"已从备份恢复。恢复前备份：\n{result['before_restore_backup']}", parent=self.root)
        self.show_system()

    def change_password(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("修改密码")
        dialog.geometry("560x340")
        dialog.minsize(500, 300)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        fields = {}
        for row, key, label in ((0, "old", "原密码"), (1, "new", "新密码"), (2, "confirm", "确认新密码")):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=7)
            entry = ttk.Entry(frame, width=34, show="*")
            entry.grid(row=row, column=1, pady=7)
            fields[key] = entry

        def save():
            old_password = fields["old"].get()
            new_password = fields["new"].get()
            if len(new_password) < 8:
                messagebox.showerror("密码无效", "新密码至少需要 8 位。", parent=dialog)
                return
            if new_password != fields["confirm"].get():
                messagebox.showerror("密码无效", "两次输入的新密码不一致。", parent=dialog)
                return
            try:
                self.api.change_password(old_password, new_password)
            except ApiError as error:
                messagebox.showerror("修改失败", str(error), parent=dialog)
                return
            dialog.destroy()
            messagebox.showinfo("修改完成", "密码已修改，请重新登录。", parent=self.root)
            self.close()

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="保存密码", command=save).pack(side="right")

    def backup(self):
        try:
            result = self.api.backup()
        except ApiError as error:
            messagebox.showerror("备份失败", str(error), parent=self.root)
            return
        messagebox.showinfo("备份完成", f"备份文件：\n{result['path']}", parent=self.root)
        self.show_system()

    def close(self):
        self.api.close()
        self.root.destroy()


def open_dashboard(api: ApiClient, user: dict) -> None:
    root = tk.Tk()
    Dashboard(root, api, user)
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="进销存桌面客户端")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="API 服务地址")
    args = parser.parse_args()
    root = tk.Tk()
    LoginWindow(root, args.api)
    root.mainloop()


if __name__ == "__main__":
    main()

