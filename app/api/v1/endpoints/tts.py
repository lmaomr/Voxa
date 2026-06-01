"""
TTS (语音合成) API 端点
"""
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.clone_service import clone_text_to_speech

logger = logging.getLogger(__name__)
router = APIRouter()


class TTSRequest(BaseModel):
    """语音合成请求参数"""
    text: str = Field(..., min_length=1, description="要合成的文本")
    reference_wav_path: str = Field(..., description="参考音频路径（用于音色克隆）")
    cfg_value: float = Field(default=2.0, ge=0.5, le=10.0, description="CFG 引导系数")
    inference_timesteps: int = Field(default=10, ge=1, le=50, description="推理步数")


class TTSResponse(BaseModel):
    """语音合成响应"""
    output_path: str = Field(..., description="生成的音频文件路径")
    text: str = Field(..., description="合成的文本")


@router.post("/clone", response_model=TTSResponse, summary="语音克隆")
async def clone_voice(request: TTSRequest):
    """
    基于参考音频进行语音克隆合成

    - **text**: 要合成的文本内容
    - **reference_wav_path**: 参考音频的本地路径
    - **cfg_value**: CFG 引导系数，默认 2.0
    - **inference_timesteps**: 推理步数，默认 10
    """
    try:
        ref_path = Path(request.reference_wav_path)
        if not ref_path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"参考音频文件不存在: {request.reference_wav_path}",
            )

        # 生成输出路径（放到配置的 TTS_OUTPUT_DIR 目录）
        output_dir = Path(settings.TTS_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"tts_output_{hash(request.text) & 0xFFFFFFFF}.wav"

        result_path = clone_text_to_speech(
            text=request.text,
            reference_wav_path=str(ref_path),
            output_path=str(output_path),
            cfg_value=request.cfg_value,
            inference_timesteps=request.inference_timesteps,
        )

        return TTSResponse(
            output_path=result_path,
            text=request.text,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("语音克隆失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音克隆失败: {e}",
        )


@router.post("/clone-simple", summary="简易语音克隆（直接指定输出路径）")
async def clone_voice_simple(
    text: str = Query(..., min_length=1, description="要合成的文本"),
    reference_wav_path: str = Query(..., description="参考音频路径"),
    output_path: str = Query(..., description="输出音频保存路径"),
    cfg_value: float = Query(2.0, ge=0.5, le=10.0, description="CFG 引导系数"),
    inference_timesteps: int = Query(10, ge=1, le=50, description="推理步数"),
):
    """
    简易接口 - 直接指定输入输出路径进行语音克隆
    """
    try:
        result_path = clone_text_to_speech(
            text=text,
            reference_wav_path=reference_wav_path,
            output_path=output_path,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
        )
        return {
            "message": "语音克隆成功",
            "output_path": result_path,
        }
    except Exception as e:
        logger.exception("语音克隆失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音克隆失败: {e}",
        )
