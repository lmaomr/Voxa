"""
YouTube 下载 API 端点
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.youtube_service import youtube_svc

logger = logging.getLogger(__name__)
router = APIRouter()


class YouTubeInfoRequest(BaseModel):
    """YouTube 视频信息请求"""
    url: str = Field(..., description="YouTube 视频 URL")


class YouTubeDownloadRequest(BaseModel):
    """YouTube 视频下载请求"""
    url: str = Field(..., description="YouTube 视频 URL")
    output_dir: str | None = Field(default=None, description="自定义输出目录（可选）")


class YouTubeInfoResponse(BaseModel):
    """YouTube 视频信息响应"""
    title: str = Field(..., description="视频标题")
    description: str = Field(..., description="视频描述")
    upload_date: str = Field(..., description="上传日期")
    uploader: str = Field(..., description="上传者")
    duration: int = Field(default=0, description="视频时长（秒）")
    view_count: int = Field(default=0, description="播放量")
    url: str = Field(..., description="视频 URL")


class YouTubeDownloadResponse(BaseModel):
    """YouTube 视频下载响应"""
    title: str = Field(..., description="视频标题")
    description: str = Field(..., description="视频描述")
    upload_date: str = Field(..., description="上传日期")
    uploader: str = Field(..., description="上传者")
    video_path: str = Field(..., description="视频本地路径")
    subtitle_path: str = Field(default="", description="字幕路径")
    thumbnail_path: str = Field(default="", description="封面路径")
    url: str = Field(..., description="视频 URL")


@router.post("/youtube/info", response_model=YouTubeInfoResponse, summary="获取 YouTube 视频信息")
async def get_youtube_info(request: YouTubeInfoRequest):
    """
    获取 YouTube 视频信息（不下载）
    """
    try:
        result = youtube_svc.get_info(request.url)
        return YouTubeInfoResponse(**result)
    except Exception as e:
        logger.exception("获取 YouTube 视频信息失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取视频信息失败: {e}",
        )


@router.post("/youtube/download", response_model=YouTubeDownloadResponse, summary="下载 YouTube 视频")
async def download_youtube_video(request: YouTubeDownloadRequest):
    """
    下载 YouTube 视频并提取信息

    - **url**: YouTube 视频 URL
    - **output_dir**: 自定义输出目录（可选）
    """
    try:
        result = youtube_svc.download(
            url=request.url,
            output_dir=request.output_dir,
        )
        return YouTubeDownloadResponse(**result)
    except Exception as e:
        logger.exception("下载 YouTube 视频失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载视频失败: {e}",
        )