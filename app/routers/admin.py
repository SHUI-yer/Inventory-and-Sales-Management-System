from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.schemas import AdminPasswordReset, RoleCreate, RolePermissionsUpdate, UserActiveUpdate, UserCreate, UserRoleUpdate
from app.security import get_current_user, hash_password, require_permission


router = APIRouter(prefix="/api/admin", tags=["用户与角色"])


@router.get("/roles")
def list_roles(_user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        roles = connection.execute("SELECT * FROM roles ORDER BY id").fetchall()
        return [
            {
                **dict(role),
                "permissions": [
                    row["code"] for row in connection.execute(
                        "SELECT p.code FROM role_permissions rp JOIN permissions p ON p.id = rp.permission_id WHERE rp.role_id = ? ORDER BY p.code",
                        (role["id"],),
                    ).fetchall()
                ],
            }
            for role in roles
        ]


@router.get("/permissions")
def list_permissions(_user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM permissions WHERE code != '*' ORDER BY code")]


@router.post("/roles", status_code=201)
def create_role(payload: RoleCreate, _user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = connection.execute("INSERT INTO roles(code, name) VALUES (?, ?)", (payload.code, payload.name.strip()))
            role_id = cursor.lastrowid
            _replace_permissions(connection, role_id, payload.permission_codes)
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise HTTPException(status_code=409, detail="角色编码或名称已存在") from error
        except Exception:
            connection.rollback()
            raise
        row = connection.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
    return dict(row)


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(role_id: int, payload: RolePermissionsUpdate, _user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        role = connection.execute("SELECT code FROM roles WHERE id = ?", (role_id,)).fetchone()
        if role is None:
            raise HTTPException(status_code=404, detail="角色不存在")
        if role["code"] == "admin":
            raise HTTPException(status_code=400, detail="系统管理员角色权限不可修改")
        connection.execute("BEGIN IMMEDIATE")
        try:
            _replace_permissions(connection, role_id, payload.permission_codes)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return {"ok": True}


def _replace_permissions(connection, role_id: int, codes: list[str]) -> None:
    codes = list(dict.fromkeys(codes))
    if "*" in codes:
        raise HTTPException(status_code=400, detail="不能将全部权限分配给普通角色")
    if codes:
        placeholders = ",".join("?" for _ in codes)
        found = connection.execute(f"SELECT id, code FROM permissions WHERE code IN ({placeholders})", codes).fetchall()
        found_codes = {row["code"] for row in found}
        missing = sorted(set(codes) - found_codes)
        if missing:
            raise HTTPException(status_code=400, detail=f"未知权限：{', '.join(missing)}")
    else:
        found = []
    connection.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
    connection.executemany(
        "INSERT INTO role_permissions(role_id, permission_id) VALUES (?, ?)",
        [(role_id, row["id"]) for row in found],
    )


@router.get("/users")
def list_users(_user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        return [
            dict(row)
            for row in connection.execute(
                """SELECT u.id, u.username, u.display_name, u.role_id, r.name AS role_name,
                          u.active, u.created_at
                   FROM users u JOIN roles r ON r.id = u.role_id ORDER BY u.id"""
            )
        ]


@router.post("/users", status_code=201)
def create_user(payload: UserCreate, _user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        role = connection.execute("SELECT id FROM roles WHERE id = ? AND active = 1", (payload.role_id,)).fetchone()
        if role is None:
            raise HTTPException(status_code=404, detail="角色不存在或已停用")
        try:
            cursor = connection.execute(
                "INSERT INTO users(username, password_hash, display_name, role_id) VALUES (?, ?, ?, ?)",
                (payload.username.strip(), hash_password(payload.password), payload.display_name.strip(), payload.role_id),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="用户名已存在") from error
        return {"id": cursor.lastrowid, "username": payload.username.strip(), "role_id": payload.role_id}


@router.patch("/users/{user_id}/active")
def set_user_active(user_id: int, payload: UserActiveUpdate, current_user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT u.id, r.code AS role_code FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            connection.rollback()
            raise HTTPException(status_code=404, detail="用户不存在")
        if user_id == current_user["id"] and not payload.active:
            connection.rollback()
            raise HTTPException(status_code=400, detail="不能停用当前登录账号")
        if user["role_code"] == "admin" and not payload.active:
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users u JOIN roles r ON r.id = u.role_id WHERE r.code = 'admin' AND u.active = 1"
            ).fetchone()[0]
            if active_admins <= 1:
                connection.rollback()
                raise HTTPException(status_code=400, detail="不能停用最后一个系统管理员")
        connection.execute("UPDATE users SET active = ? WHERE id = ?", (int(payload.active), user_id))
        connection.commit()
    return {"ok": True}


@router.patch("/users/{user_id}/role")
def set_user_role(user_id: int, payload: UserRoleUpdate, current_user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT u.id, u.role_id, r.code AS role_code FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?",
            (user_id,),
        ).fetchone()
        role = connection.execute("SELECT id, code FROM roles WHERE id = ? AND active = 1", (payload.role_id,)).fetchone()
        if user is None:
            connection.rollback()
            raise HTTPException(status_code=404, detail="用户不存在")
        if role is None:
            connection.rollback()
            raise HTTPException(status_code=404, detail="目标角色不存在或已停用")
        if user_id == current_user["id"]:
            connection.rollback()
            raise HTTPException(status_code=400, detail="不能修改当前登录账号的角色")
        if user["role_code"] == "admin" and role["code"] != "admin":
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users u JOIN roles r ON r.id = u.role_id WHERE r.code = 'admin' AND u.active = 1"
            ).fetchone()[0]
            if active_admins <= 1:
                connection.rollback()
                raise HTTPException(status_code=400, detail="不能移除最后一个系统管理员")
        connection.execute("UPDATE users SET role_id = ? WHERE id = ?", (payload.role_id, user_id))
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        connection.commit()
    return {"ok": True}


@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, payload: AdminPasswordReset, _user: dict = Depends(require_permission("users.manage"))):
    with get_db() as connection:
        cursor = connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(payload.new_password), user_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="用户不存在")
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return {"ok": True}

