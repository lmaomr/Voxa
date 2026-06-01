"""
语音识别服务 - 基于 faster-whisper (CTranslate2 GPU 批量推理)
"""
from concurrent.futures import ProcessPoolExecutor
import gc
import logging
import os
from pathlib import Path
import time
import whisperx
import torch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.core.config import settings

logger = logging.getLogger(__name__)

HF_ENDPOINT = settings.HF_ENDPOINT.strip()
if HF_ENDPOINT:
    os.environ.setdefault("HF_ENDPOINT", HF_ENDPOINT)


class ASRService:
    """faster-whisper 语音识别服务"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.WHISPER_MODEL_PATH
        self._model = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._compute_type = "float16" if self._device == "cuda" else "int8"

    def _load_model(self):
        """懒加载 WhisperX 模型"""
        if self._model is None:
            logger.info("正在加载WhisperX模型...")
            # 基本配置
            device = self._device
            compute_type = self._compute_type
            logger.info(f"设备: {device}, 计算类型: {compute_type}")
            model_path = self.model_name
            if not Path(model_path).exists():
                logger.warning(f"模型路径不存在: {model_path}，尝试使用 HuggingFace 镜像加载...")
                model_path = self.model_name = settings.WHISPER_MODEL_SIZE
            self._model = whisperx.load_model(self.model_name, device, compute_type=compute_type)
        return self._model
        
    def _load_audio_manually(self, file_path):
        """手动加载音频并转换为 WhisperX 所需格式"""
        import librosa
        logger.info(f"正在加载音频: {file_path}")
        
        # librosa 一次性完成：加载、重采样到16000Hz、转单声道
        audio_numpy, sr = librosa.load(file_path, sr=16000, mono=True)
        audio_numpy = audio_numpy.astype('float32')
        
        logger.info(f"音频加载完成，采样率: {sr} Hz, 时长: {len(audio_numpy)/sr:.1f}秒")
        return audio_numpy

    def unload(self):
        if self._model is not None:
            logger.info("卸载 ASR 模型，释放 GPU 显存...")
            del self._model
            self._model = None
        torch.cuda.empty_cache()
        torch.cuda.synchronize()  # 确保所有CUDA操作完成
        torch.cuda.ipc_collect()  # 清理进程间通信缓存
        gc.collect()
        logger.info("ASR 显存已释放")

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
        task: str = "transcribe",
    ) -> dict:
        """
        语音识别

        Args:
            audio_path: 音频文件路径
            language: 语言代码（如 "zh", "en"），None 为自动检测
            task: 识别任务类型，默认为转录（transcribe），可选 translate

        Returns:
            {
                "text": "识别文本",
                "segments": [{ "start": 0.0, "end": 1.5, "text": "..." }, ...],
                "language": "检测到的语言",
                "duration": 音频时长(秒),
            }
        """
        try:
            path = Path(audio_path)
            if not path.exists():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")

            logger.info(f"开始语音识别: {path.name} (语言={language or 'auto'})")

            # 1. 加载模型
            model = self._load_model()

            # 2. 音频预处理
            logger.info("正在预处理音频...")
            audio = self._load_audio_manually(audio_path)
            audio_duration = len(audio) / 16000.0

            # 3. 语音识别
            logger.info("正在执行语音识别...")
            result = model.transcribe(audio, batch_size=16, language=language)
            detected_lang = result.get("language", language or "unknown")
            
            # 4. 词级对齐
            model_a, metadata = whisperx.load_align_model(
                language_code=detected_lang, 
                device=self._device
            )

            # 5. 对齐结果处理（统一构建 segments）
            result = whisperx.align(
                result.get("segments", []), 
                model_a, 
                metadata, 
                audio, 
                self._device,
                return_char_alignments=False
            )

            if model_a is not None:
                del model_a
            if metadata is not None:
                del metadata
            if audio is not None:
                del audio

            segments_data = result.get("segments", [])
            if task == "translate" and detected_lang != "zh":
                from app.services import translate_svc
                logger.info(f"正在批量翻译 {len(segments_data)} 段文本...")
                texts = [seg.get("text", "").strip() for seg in segments_data]
                batch_results = translate_svc.translate_batch(
                    texts=texts,
                    source=detected_lang,
                    target="zh",
                )
                # 翻译结果映射：索引 -> 翻译后文本
                text_map = {i: r.get("text", "").strip() for i, r in enumerate(batch_results)}
            else:
                # 原文映射：索引 -> 原文
                text_map = {}

            # 统一构建 segments（合并原来两个分支）
            segments = [
                {
                    "id": i,
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": text_map.get(i) or seg.get("text", "").strip()
                }
                for i, seg in enumerate(segments_data)
            ]
            full_text = " ".join(s["text"] for s in segments)

            logger.info(f"识别完成: 语言={detected_lang}, 时长={audio_duration:.1f}s, 段数={len(segments)}")

            return {
                "text": full_text,
                "segments": segments,
                "language": detected_lang,
                "duration": audio_duration,
            }
        finally:
            self.unload()

def _transcribe_audio(
    audio_path: str | Path,
    language: str | None = None,
    task: str = "transcribe",
) -> dict:
    """便捷函数 - 语音识别"""
    _asr = ASRService()
    return _asr.transcribe(audio_path, language=language, task=task)

def transcribe_audio(
    audio_path: str | Path,
    language: str | None = None,
    task: str = "transcribe",
) -> dict:
    """外部调用 - 语音识别"""
    with ProcessPoolExecutor() as pool:
        fut = pool.submit(_transcribe_audio, audio_path, language, task)
        return fut.result()

if __name__ == "__main__":
    time_start = time.time()
    asr = ASRService()

    # 处理单个文件
    single_file = r"C:\Users\45826\Desktop\Voxa\data\uploads\0932601ca6d245ce912ae3a7bc07726b.mp4"
    result = asr.transcribe(
        audio_path=single_file,
        language="en",
        task="transcribe"
    )

    print(result)

    time_end = time.time()
    print(f"总耗时: {time_end - time_start:.1f}秒")