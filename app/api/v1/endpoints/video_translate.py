"""
视频翻译 API 端点

完整流程:
  1. 提取音频 + 人声分离
  2. ASR 识别 + 翻译 + 语音克隆
  3. 拼接 + 混音 + 压制字幕
"""
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.video_translate_service import video_translate_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# 简单进度缓存（单用户场景适用）
_progress_cache: dict[str, dict] = {}


class VideoTranslateRequest(BaseModel):
    """视频翻译请求"""
    video_path: str = Field(..., description="输入视频文件路径")
    output_path: str | None = Field(default=None, description="输出视频文件路径（可选）")
    source_lang: str | None = Field(default=None, description="源语言（None=自动检测）")
    target_lang: str = Field(default="zh", description="目标语言（默认 zh）")
    model_name: str | None = Field(default=None, description="UVR5 模型名（可选）")
    reference_wav: str | None = Field(default=None, description="参考人声路径（用于音色克隆）")
    keep_temp: bool = Field(default=False, description="是否保留临时文件")


class VideoTranslateResponse(BaseModel):
    """视频翻译响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(default="queued", description="任务状态")


class ProgressResponse(BaseModel):
    """进度查询响应"""
    status: str = Field(..., description="任务状态")
    stages: dict = Field(default={}, description="各阶段结果")
    progress: float = Field(default=0.0, description="进度 0-1")
    message: str = Field(default="", description="当前状态信息")
    output_video: str | None = Field(default=None, description="输出视频路径")
    total_time: float | None = Field(default=None, description="总耗时")


def _do_translate(task_id: str, req: VideoTranslateRequest):
    """后台执行翻译任务"""
    try:
        # 进度回调
        def _on_progress(stage: str, pct: float, msg: str):
            _progress_cache[task_id] = {
                "status": "running",
                "progress": round(pct, 3),
                "message": msg,
                "stage": stage,
            }

        result = video_translate_service.translate(
            video_path=req.video_path,
            output_path=req.output_path,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            model_name=req.model_name,
            keep_temp=req.keep_temp,
            progress_callback=_on_progress,
        )

        _progress_cache[task_id] = {
            "status": "completed",
            "progress": 1.0,
            "message": "视频翻译完成",
            "output_video": result.get("output_video"),
            **result,
        }

    except Exception as e:
        logger.exception(f"视频翻译失败 (task={task_id})")
        _progress_cache[task_id] = {
            "status": "failed",
            "message": str(e),
        }


@router.post("/video-translate", response_model=VideoTranslateResponse)
async def translate_video(
    request: VideoTranslateRequest,
    background_tasks: BackgroundTasks,
):
    """
    视频翻译（后台异步执行）

    完整流程：提取音频 → 人声分离 → ASR 识别 → 翻译 → 语音克隆 → 拼接混音 → 压制字幕
    """
    path = Path(request.video_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"视频文件不存在: {request.video_path}",
        )

    task_id = f"vt_{int(time.time())}_{path.stem}"
    background_tasks.add_task(_do_translate, task_id, request)

    logger.info(f"视频翻译任务已提交: task_id={task_id}, video={request.video_path}")

    return VideoTranslateResponse(
        task_id=task_id,
        status="queued",
    )


@router.get("/video-translate/progress/{task_id}", response_model=ProgressResponse)
async def get_progress(task_id: str):
    """
    查询视频翻译任务进度
    """
    progress = _progress_cache.get(task_id)

    if progress is None:
        return ProgressResponse(
            status="not_found",
            progress=0.0,
            message="任务不存在",
        )

    return ProgressResponse(
        status=progress.get("status", "unknown"),
        stages=progress.get("stages", {}),
        progress=progress.get("progress", 0.0),
        message=progress.get("message", ""),
        output_video=progress.get("output_video"),
        total_time=progress.get("total_time"),
    )


@router.post("/video-translate/sync", response_model=dict, summary="同步视频翻译")
async def translate_video_sync(request: VideoTranslateRequest):
    """
    视频翻译（同步等待完成）

    注意：长视频可能需要较长时间，建议使用异步接口
    """
    path = Path(request.video_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"视频文件不存在: {request.video_path}",
        )

    try:
        result = video_translate_service.translate(
            video_path=request.video_path,
            output_path=request.output_path,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            model_name=request.model_name,
            reference_wav=request.reference_wav,
            keep_temp=request.keep_temp,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"视频翻译失败: {e}",
        )
