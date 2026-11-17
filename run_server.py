from __future__ import annotations

import argparse

import uvicorn

from app.db import init_db
from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="启动进销存 API 服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，本地模式使用 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    init_db()
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

