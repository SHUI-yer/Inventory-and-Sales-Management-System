from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException

from app.db import get_db
from app.schemas import LoginRequest, PasswordChange
from app.security import create_session, get_current_user, hash_password, verify_password


router = APIRouter(prefix="/api/auth", tags=["身份认证"])


@router.post("/login")
def login(payload: LoginRequest):
    with get_db() as connection:
        user = connection.execute(
            """SELECT u.id, u.username, u.password_hash, u.display_name, u.active,
                      r.code AS role_code, r.name AS role_name
               FROM users u JOIN roles r ON r.id = u.role_id
               WHERE u.username = ?""",
            (payload.username.strip(),),
        ).fetchone()
    if user is None or not user["active"] or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_session(user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role_code": user["role_code"],
            "role_name": user["role_name"],
        },
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), user: dict = Depends(get_current_user)):
    token = authorization[7:].strip()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with get_db() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
    return {"ok": True}


@router.post("/password")
def change_password(payload: PasswordChange, user: dict = Depends(get_current_user)):
    with get_db() as connection:
        row = connection.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if row is None or not verify_password(payload.old_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="原密码不正确")
        connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(payload.new_password), user["id"]))
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    return {"ok": True, "message": "密码已修改，请重新登录"}

