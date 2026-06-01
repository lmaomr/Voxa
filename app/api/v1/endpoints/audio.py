"""
音频处理 API - 人声分离
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from app.services.vocal_service import vocal

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/separate", summary="人声分离")
async def api_separate(
    audio_path: str = Query(..., description="输入音频路径"),
):
    """从音频中分离人声和伴奏"""
    if not Path(audio_path).exists():
        raise HTTPException(400, detail=f"文件不存在: {audio_path}")

    try:
        result = vocal.separate(audio_path)
        return {"status": "ok", "files": result}
    except Exception as e:
        raise HTTPException(500, detail=f"分离失败: {e}")


@router.post("/vocals", summary="提取人声")
async def api_vocals(
    audio_path: str = Query(..., description="输入音频路径"),
    out_path: str = Query(None, description="输出路径（可选）"),
):
    """从音频中提取人声"""
    if not Path(audio_path).exists():
        raise HTTPException(400, detail=f"文件不存在: {audio_path}")

    try:
        result = vocal.vocals(audio_path, out_path)
        return {"status": "ok", "path": result}
    except Exception as e:
        raise HTTPException(500, detail=f"提取失败: {e}")


@router.post("/accompaniment", summary="提取伴奏")
async def api_accompaniment(
    audio_path: str = Query(..., description="输入音频路径"),
    out_path: str = Query(None, description="输出路径（可选）"),
):
    """从音频中提取伴奏"""
    if not Path(audio_path).exists():
        raise HTTPException(400, detail=f"文件不存在: {audio_path}")

    try:
        result = vocal.accompaniment(audio_path, out_path)
        return {"status": "ok", "path": result}
    except Exception as e:
        raise HTTPException(500, detail=f"提取失败: {e}")
