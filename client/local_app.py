"""Packaged local desktop entry: run the API in-process and open Tkinter."""

from __future__ import annotations

import os
import socket
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

os.environ.setdefault("IMS_MODE", "local")

from app.main import app


def _find_free_port() -> int:
    """Ask Windows for an unused loopback port for the embedded API."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def main() -> None:
    os.environ["IMS_MODE"] = "local"
    requested_port = os.getenv("IMS_LOCAL_PORT", "").strip()
    try:
        port = int(requested_port) if requested_port else _find_free_port()
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as error:
        raise RuntimeError("IMS_LOCAL_PORT 必须是 1 到 65535 之间的端口号") from error

    server_error: list[BaseException] = []

    def run_server() -> None:
        try:
            uvicorn.run(
                app=app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                # PyInstaller --windowed sets sys.stderr to None. Uvicorn's
                # default formatter calls stderr.isatty(), so disable its
                # console logging for the embedded desktop server.
                log_config=None,
                access_log=False,
            )
        except BaseException as error:  # surfaced to the main thread below
            server_error.append(error)

    server = threading.Thread(
        target=run_server,
        daemon=True,
    )
    server.start()
    api_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if server_error:
            error = server_error[0]
            raise RuntimeError(f"本地 API 启动失败：{error}") from error
        if not server.is_alive():
            raise RuntimeError("本地 API 服务线程已退出，请检查端口或数据目录权限")
        try:
            with urlopen(f"{api_url}/health", timeout=0.5) as response:
                if response.status == 200:
                    break
        except (OSError, URLError):
            time.sleep(0.2)
    else:
        detail = f"端口 {port} 在 20 秒内没有响应"
        if server_error:
            detail += f"：{server_error[0]}"
        raise RuntimeError(f"本地 API 启动超时，{detail}")

    import tkinter as tk
    from client.main import LoginWindow

    root = tk.Tk()
    LoginWindow(root, api_url)
    root.mainloop()


if __name__ == "__main__":
    main()

