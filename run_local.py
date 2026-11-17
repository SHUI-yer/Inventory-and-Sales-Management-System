"""Start the local API on loopback and open the desktop client."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def main() -> None:
    project_root = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["IMS_MODE"] = "local"
    requested_port = env.get("IMS_LOCAL_PORT", "").strip()
    try:
        port = int(requested_port) if requested_port else find_free_port()
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as error:
        raise RuntimeError("IMS_LOCAL_PORT 必须是 1 到 65535 之间的端口号") from error
    server = subprocess.Popen(
        [sys.executable, str(project_root / "run_server.py"), "--host", "127.0.0.1", "--port", str(port)],
        cwd=project_root,
        env=env,
    )
    try:
        api_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(f"本地 API 服务启动失败，请检查端口 {port} 或数据目录权限")
            try:
                with urlopen(f"{api_url}/health", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except (OSError, URLError):
                time.sleep(0.2)
        else:
            raise RuntimeError("等待本地 API 服务超时")
        subprocess.run([sys.executable, "-m", "client", "--api", api_url], cwd=project_root, env=env, check=False)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()

