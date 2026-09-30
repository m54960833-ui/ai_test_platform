"""
Web 管理平台入口：挂静态页面 + 管理 API。
启动方式：python run.py web （会自动带上被测服务一起起）
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router

STATIC_DIR = __import__("pathlib").Path(__file__).resolve().parent / "static"

app = FastAPI(title="AITestPlatform Web", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# 静态前端
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
