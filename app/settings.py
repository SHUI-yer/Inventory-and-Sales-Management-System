from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "InventorySalesManagement"
DEFAULT_PORT = 8000


def get_mode() -> str:
    mode = os.getenv("IMS_MODE", "local").strip().lower()
    return mode if mode in {"local", "server"} else "local"


def get_data_dir() -> Path:
    configured = os.getenv("IMS_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    if sys.platform == "win32":
        if get_mode() == "server":
            base = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData"))
        else:
            base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / APP_NAME

    if get_mode() == "server":
        return Path.home() / ".local" / "share" / "inventory-sales"
    return Path.home() / ".local" / "share" / "inventory-sales-local"


def get_database_path() -> Path:
    return get_data_dir() / "inventory.db"


def get_admin_password() -> str:
    return os.getenv("IMS_ADMIN_PASSWORD", "admin123")

