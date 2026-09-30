"""
登录态的依赖：从 Authorization 头里取 Bearer token，查到 token 就返回用户，
否则抛 401。token 就是一段随机字符串，存在 tokens 表里，先不去搞真正的 JWT，
演示够了。
"""
import secrets

from fastapi import Header, HTTPException

from . import db  # noqa: F401  放这避免相对导入麻烦


def create_token(user_id: int) -> str:
    token = secrets.token_hex(16)
    db.execute("INSERT INTO tokens (token, user_id) VALUES (?,?)", (token, user_id))
    return token


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或 token 缺失")
    token = authorization[len("Bearer "):].strip()
    row = db.query_one("SELECT * FROM tokens WHERE token=?", (token,))
    if not row:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    user = db.query_one("SELECT * FROM users WHERE id=?", (row["user_id"],))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
