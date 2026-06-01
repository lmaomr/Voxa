"""
翻译 API 端点 - 基于 Deep Translator
"""
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.translate_service import translate_svc

logger = logging.getLogger(__name__)
router = APIRouter()


class TranslateRequest(BaseModel):
    """翻译请求参数"""
    text: str = Field(..., description="待翻译文本")
    source: str = Field(default="auto", description="源语言代码（auto 为自动检测）")
    target: str = Field(default="zh-CN", description="目标语言代码")


class TranslateResponse(BaseModel):
    """翻译响应"""
    text: str = Field(..., description="翻译结果")
    source: str = Field(..., description="检测到的源语言")
    target: str = Field(..., description="目标语言")
    source_text: str = Field(..., description="原始文本")


class LanguagesResponse(BaseModel):
    """支持的语言列表响应"""
    languages: dict = Field(..., description="语言映射表 {显示名: 语言代码}")


@router.post("/translate", response_model=TranslateResponse, summary="文本翻译")
async def translate(request: TranslateRequest):
    """
    翻译文本（支持 80+ 种语言）

    - **text**: 待翻译的文本
    - **source**: 源语言代码（auto 为自动检测）
    - **target**: 目标语言代码（如 zh-CN, en, ja 等）
    """
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="翻译文本不能为空",
            )

        if not translate_svc.available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="翻译服务不可用，请安装 translators: pip install translators",
            )

        result = translate_svc.translate(
            text=request.text,
            source=request.source,
            target=request.target,
        )

        return TranslateResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("翻译失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"翻译失败: {e}",
        )


@router.get("/languages", response_model=LanguagesResponse, summary="获取支持的语言列表")
async def get_languages():
    """
    获取翻译服务支持的语言列表
    """
    return LanguagesResponse(languages=translate_svc.supported_languages)
