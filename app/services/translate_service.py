"""
翻译服务 - 基于 translators（支持 Bing/Baidu/Google 等多种后端）
"""
import logging
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

# 常见语言代码对照
LANGUAGE_MAP = {
    "自动检测": "auto",
    "中文": "zh",
    "英文": "en",
    "日语": "ja",
    "韩语": "ko",
    "法语": "fr",
    "德语": "de",
    "西班牙语": "es",
    "葡萄牙语": "pt",
    "俄语": "ru",
    "阿拉伯语": "ar",
    "意大利语": "it",
    "荷兰语": "nl",
    "泰语": "th",
    "越南语": "vi",
    "印尼语": "id",
    "印地语": "hi",
}

# 后端优先级：Bing(国内可用) > Baidu(国内可用) > Google(需科学上网)
BACKEND_PRIORITY = ["bing", "baidu", "google"]


class TranslateService:
    """翻译服务"""

    def __init__(self):
        self._backend = None

    def _check_available(self):
        """检查依赖是否可用（每次调用实时检查）"""
        try:
            import translators as ts
            _ = ts  # 抑制未使用警告
            return True
        except ImportError:
            return False

    @property
    def available(self) -> bool:
        return self._check_available()

    @property
    def backend(self) -> str | None:
        """当前使用的翻译后端"""
        return self._backend

    @property
    def supported_languages(self) -> dict:
        """返回支持的语言列表"""
        return LANGUAGE_MAP

    def _normalize_lang_code(self, code: str) -> str:
        """规范化语言代码"""
        # 中文代码映射
        code_map = {
            "zh-CN": "zh",
            "zh-TW": "zh",
            "zh-HK": "zh",
            "zh-cn": "zh",
            "zh-tw": "zh",
        }
        return code_map.get(code, code)

    def _try_translate(
        self,
        text: str,
        source: str,
        target: str,
        backends: list[str] = None,
    ) -> tuple[str, str]:
        """
        尝试用多个后端翻译，直到成功

        Returns:
            (翻译结果, 使用的后端名称)
        """
        import translators as ts

        if backends is None:
            backends = BACKEND_PRIORITY

        last_error = None

        for backend in backends:
            try:
                logger.info(f"尝试翻译后端: {backend}")
                result = ts.translate_text(
                    text,
                    from_language=source,
                    to_language=target,
                    translator=backend,
                )

                if result and result.strip():
                    self._backend = backend
                    logger.info(f"翻译后端 {backend} 成功")
                    return result.strip(), backend

            except Exception as e:
                last_error = e
                logger.warning(f"翻译后端 {backend} 失败: {e}")
                continue

        # 所有后端都失败
        raise RuntimeError(
            f"所有翻译后端均不可用 (尝试: {backends}): {last_error}"
        ) from last_error

    def translate(
        self,
        text: str,
        source: str = "auto",
        target: str = "zh",
        backends: list[str] = None,
    ) -> dict:
        """
        翻译文本

        Args:
            text: 待翻译文本
            source: 源语言代码（"auto" 为自动检测）
            target: 目标语言代码
            backends: 翻译后端优先级列表，默认 ["bing", "baidu", "google"]

        Returns:
            {
                "text": "翻译结果",
                "source": "检测到的源语言",
                "target": "目标语言",
                "source_text": "原始文本",
                "backend": "使用的翻译后端",
            }
        """
        if not text or not text.strip():
            raise ValueError("翻译文本不能为空")

        if not self._check_available():
            raise ImportError(
                "缺少 translators 依赖，请执行: pip install translators"
            )

        # 将中文语言名转换为代码
        if source in LANGUAGE_MAP:
            source = LANGUAGE_MAP[source]
        if target in LANGUAGE_MAP:
            target = LANGUAGE_MAP[target]

        # 规范化语言代码
        source = self._normalize_lang_code(source)
        target = self._normalize_lang_code(target)

        logger.info(f"开始翻译: '{text[:60]}...' ({source} -> {target})")

        try:
            if backends is None:
                backends = BACKEND_PRIORITY

            result, used_backend = self._try_translate(
                text=text,
                source=source,
                target=target,
                backends=backends,
            )

            logger.info(
                f"翻译完成 [{used_backend}]: '{result[:60]}...'"
            )

            return {
                "text": result,
                "source": source if source != "auto" else "auto",
                "target": target,
                "source_text": text,
                "backend": used_backend,
            }

        except Exception as e:
            error_msg = str(e).lower()
            raise RuntimeError(f"翻译失败: {e}") from e

    def translate_batch(
        self,
        texts: list[str],
        source: str = "auto",
        target: str = "zh",
        backends: list[str] = None,
    ) -> list[dict]:
        """
        批量翻译

        Args:
            texts: 待翻译文本列表
            source: 源语言
            target: 目标语言
            backends: 翻译后端优先级

        Returns:
            [{"text": "...", "source_text": "..."}, ...]
        """
        results = []
        for i, text in enumerate(texts):
            try:
                # 每翻译一条间隔一下，避免触发限流
                if i > 0:
                    time.sleep(0.5)

                result = self.translate(
                    text=text,
                    source=source,
                    target=target,
                    backends=backends,
                )
                results.append(result)
            except Exception as e:
                results.append({
                    "text": "",
                    "source": source,
                    "target": target,
                    "source_text": text,
                    "error": str(e),
                })
        return results


# 全局单例
translate_svc = TranslateService()


def translate_text(
    text: str,
    source: str = "auto",
    target: str = "zh",
    backends: list[str] = None,
) -> dict:
    """
    便捷函数 - 翻译文本

    用法:
        translate_text("Hello world", target="zh")
    """
    return translate_svc.translate(
        text=text,
        source=source,
        target=target,
        backends=backends,
    )
