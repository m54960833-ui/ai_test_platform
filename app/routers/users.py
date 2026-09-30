# 用户相关接口，除列表/查询外都需要登录态
from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..auth import get_current_user
from ..schemas import UserUpdateReq

router = APIRouter(prefix="/api/users", tags=["users"])


def _public_user(row: dict) -> dict:
    # 返回给前端时不要把密码带出去
    return {k: v for k, v in row.items() if k != "password"}


@router.get("")
def list_users(page: int = 1, page_size: int = 10, _: dict = Depends(get_current_user)):
    total = db.query_one("SELECT COUNT(*) AS c FROM users")["c"]
    rows = db.query(
        "SELECT * FROM users ORDER BY id LIMIT ? OFFSET ?",
        (page_size, (page - 1) * page_size),
    )
    return {"code": 0, "message": "ok", "data": {"total": total, "items": [_public_user(r) for r in rows]}}


@router.get("/{uid}")
def get_user(uid: int, _: dict = Depends(get_current_user)):
    row = db.query_one("SELECT * FROM users WHERE id=?", (uid,))
    if not row:
        # 资源不存在走 HTTP 404，方便测试平台断言状态码
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 0, "message": "ok", "data": _public_user(row)}


@router.put("/{uid}")
def update_user(uid: int, req: UserUpdateReq, _: dict = Depends(get_current_user)):
    row = db.query_one("SELECT * FROM users WHERE id=?", (uid,))
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.execute(
        "UPDATE users SET email=?, nickname=? WHERE id=?",
        (req.email, req.nickname, uid),
    )
    return {"code": 0, "message": "ok", "data": {"user_id": uid}}


@router.delete("/{uid}")
def delete_user(uid: int, _: dict = Depends(get_current_user)):
    # 演示用户 demo 不允许删，防止把种子数据搞没了
    row = db.query_one("SELECT * FROM users WHERE id=?", (uid,))
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    if row["username"] == "demo":
        return {"code": 1003, "message": "演示用户不允许删除", "data": None}
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    return {"code": 0, "message": "ok", "data": {"user_id": uid}}
