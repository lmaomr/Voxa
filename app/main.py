"""
应用入口 - FastAPI 实例
"""
import logging
import sys
from pathlib import Path

from fastapi import FastAPI

# ====== 日志配置（stderr + 文件持久化） ======
_log_file = Path(__file__).resolve().parent.parent / "logs" / "server.log"
_log_file.parent.mkdir(parents=True, exist_ok=True)

_file_handler = logging.FileHandler(str(_log_file), encoding="utf-8", mode="a")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logging.getLogger().addHandler(_file_handler)
# 将 uvicorn 的访问日志调为 WARNING，避免刷屏
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.endpoints import asr, audio, items, translate, tts, upload, users, video_translate, youtube

app = FastAPI(
    title="Voxa API",
    description="Voxa - AI 语音工具包",
    version="0.1.0",
)

# 注册 API 路由（优先于静态文件）
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["tts"])
app.include_router(audio.router, prefix="/api/v1/audio", tags=["audio"])
app.include_router(asr.router, prefix="/api/v1/asr", tags=["asr"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(translate.router, prefix="/api/v1/translate", tags=["translate"])
app.include_router(video_translate.router, prefix="/api/v1/video", tags=["video"])
app.include_router(youtube.router, prefix="/api/v1", tags=["youtube"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}


# Web UI 托管
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/web", StaticFiles(directory=str(static_dir), html=True), name="web")

# 数据目录托管（用于播放音频文件）
data_dir = Path(__file__).resolve().parent.parent / "data"
data_dir.mkdir(exist_ok=True)
app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")


@app.get("/")
async def root():
    """根路径重定向到 Web UI"""
    return RedirectResponse(url="/web/")
