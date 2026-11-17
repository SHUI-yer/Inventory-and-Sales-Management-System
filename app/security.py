from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status

from app.db import get_db


SESSION_HOURS = 12
PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).isoformat()
    with get_db() as connection:
        connection.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, expires_at),
        )
    return token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    token = authorization[7:].strip()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        row = connection.execute(
            """SELECT u.id, u.username, u.display_name, u.role_id, r.code AS role_code,
                      r.name AS role_name
               FROM sessions s JOIN users u ON u.id = s.user_id
               JOIN roles r ON r.id = u.role_id
               WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1 AND r.active = 1""",
            (token_hash, now),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")
    return dict(row)


def require_permission(permission_code: str):
    def dependency(user: dict = Depends(get_current_user)):
        if not user_has_permission(user["id"], permission_code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有此操作权限")
        return user

    return dependency


def user_has_permission(user_id: int, permission_code: str) -> bool:
    with get_db() as connection:
        row = connection.execute(
            """SELECT 1 FROM users u
               JOIN role_permissions rp ON rp.role_id = u.role_id
               JOIN permissions p ON p.id = rp.permission_id
               WHERE u.id = ? AND (p.code = ? OR p.code = '*') LIMIT 1""",
            (user_id, permission_code),
        ).fetchone()
    return row is not None

