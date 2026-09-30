# 注册 / 登录
from fastapi import APIRouter, HTTPException

from .. import auth as auth_util
from .. import db
from ..schemas import LoginReq, RegisterReq

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(req: RegisterReq):
    # 用户名不能重复
    if db.query_one("SELECT id FROM users WHERE username=?", (req.username,)):
        # 业务错误用 200 + code，跟登录失败的写法保持一致
        return {"code": 1001, "message": "用户名已存在", "data": None}
    uid = db.insert(
        "INSERT INTO users (username, password, email) VALUES (?,?,?)",
        (req.username, req.password, req.email),
    )
    return {"code": 0, "message": "ok", "data": {"user_id": uid}}


@router.post("/login")
def login(req: LoginReq):
    user = db.query_one("SELECT * FROM users WHERE username=?", (req.username,))
    if not user or user["password"] != req.password:
        return {"code": 1002, "message": "用户名或密码错误", "data": None}
    token = auth_util.create_token(user["id"])
    return {
        "code": 0,
        "message": "ok",
        "data": {"token": token, "user_id": user["id"], "nickname": user["nickname"]},
    }
