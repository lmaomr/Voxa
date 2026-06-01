"""
ASR (语音识别) API 端点 - 基于 Whisper
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.asr_service import transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter()


class ASRRequest(BaseModel):
    """语音识别请求参数"""
    audio_path: str = Field(..., description="音频文件路径")
    language: str | None = Field(default=None, description="语言代码（如 zh/en），None 为自动检测")
    task: str = Field(default="transcribe", description="识别任务类型，默认为转录（transcribe），可选 translate")

class ASRResponse(BaseModel):
    """语音识别响应"""
    text: str = Field(..., description="识别文本")
    language: str = Field(..., description="检测到的语言")
    duration: float = Field(default=0.0, description="音频时长（秒）")


class ASRSegment(BaseModel):
    """语音片段"""
    start: float = Field(..., description="开始时间（秒）")
    end: float = Field(..., description="结束时间（秒）")
    text: str = Field(..., description="片段文本")


class ASRFullResponse(BaseModel):
    """完整语音识别响应"""
    text: str = Field(..., description="识别文本")
    segments: list[ASRSegment] = Field(default=[], description="分段识别结果")
    language: str = Field(..., description="检测到的语言")
    duration: float = Field(default=0.0, description="音频时长（秒）")


@router.post("/transcribe", response_model=ASRFullResponse, summary="语音识别")
async def transcribe(request: ASRRequest):
    """
    语音识别（支持多语言）

    - **audio_path**: 音频文件的本地路径
    - **language**: 语言代码（zh/en/jp 等），不填自动检测
    """
    try:
        path = Path(request.audio_path)
        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"音频文件不存在: {request.audio_path}",
            )

        result = transcribe_audio(
            audio_path=str(path),
            language=request.language,
            task=request.task,
        )

        # 转换 segments
        segments = [
            ASRSegment(start=s["start"], end=s["end"], text=s["text"].strip())
            for s in result.get("segments", [])
        ]

        return ASRFullResponse(
            text=result["text"],
            segments=segments,
            language=result["language"],
            duration=result["duration"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("语音识别失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音识别失败: {e}",
        )


@router.post("/transcribe-simple", response_model=ASRResponse, summary="简易语音识别")
async def transcribe_simple(
    audio_path: str = Query(..., description="音频文件路径"),
    language: str | None = Query(default=None, description="语言代码"),
):
    """
    简易接口 - 只返回文本和语言信息
    """
    try:
        path = Path(audio_path)
        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"音频文件不存在: {audio_path}",
            )

        result = transcribe_audio(
            audio_path=str(path),
            language=language,
        )

        return ASRResponse(
            text=result["text"],
            language=result["language"],
            duration=result["duration"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("语音识别失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音识别失败: {e}",
        )
