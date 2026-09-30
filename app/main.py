"""
内置的 Demo 被测服务（电商用户/订单/认证）。

启动方式：python run.py server
默认监听 127.0.0.1:8001，Swagger 文档在 /docs，OpenAPI schema 在 /openapi.json
（AI 生成测试用例就是读这个 openapi.json 来做的）。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routers import auth, orders, users

db.init_db()

app = FastAPI(title="AITestPlatform Demo Service", version="1.0.0")

# 前端页面是单独一个端口跑的，跨域要放开
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(orders.router)


@app.get("/api/health")
def health():
    # 测试执行前会先轮询这个接口，等服务起来再打用例
    return {"status": "ok", "service": "aitest-demo", "version": "1.0.0"}
