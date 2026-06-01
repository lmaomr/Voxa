"""
语音克隆服务 - 基于 VoxCPM2 的 TTS 服务
"""
from concurrent.futures import ProcessPoolExecutor
import gc
import logging
from pathlib import Path

import soundfile as sf
import torch

from app.core.config import settings

logger = logging.getLogger(__name__)


class VoiceCloneService:
    """语音克隆服务封装"""

    def __init__(self, model_path: str | Path | None = None):
        self.model_path = Path(model_path or settings.TTS_MODEL_PATH)
        self._model = None

    def _load_model(self):
        """延迟加载模型"""
        if self._model is not None:
            return

        try:
            from voxcpm import VoxCPM

            logger.info(f"正在加载语音克隆模型: {self.model_path}")
            self._model = VoxCPM.from_pretrained(
                str(self.model_path),
                load_denoiser=False,
            )
            logger.info("模型加载完成")
        except ImportError:
            raise ImportError(
                "缺少 voxcpm 依赖，请执行: pip install voxcpm"
            )
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {e}") from e
        
    def unload(self):
        """卸载模型释放资源"""
        if self._model is not None:
            logger.info("卸载 VoiceClone 模型，释放 GPU 显存...")
            del self._model
            self._model = None
        torch.cuda.empty_cache()
        torch.cuda.synchronize()  # 确保所有CUDA操作完成
        torch.cuda.ipc_collect()  # 清理进程间通信缓存
        logger.info("VoiceClone 显存已释放")

    @property
    def model(self):
        if self._model is None:
            self._load_model()
        return self._model

    def generate(
        self,
        text: str,
        reference_wav_path: str | Path,
        output_path: str | Path,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10,
        denoise: bool = True
    ) -> str:
        """
        语音克隆生成

        Args:
            text: 要合成的文本
            reference_wav_path: 参考音频路径（用于音色克隆）
            output_path: 输出音频保存路径
            cfg_value: CFG 引导系数（默认 2.0）
            inference_timesteps: 推理步数（默认 10）
            denoise: 是否启用去噪（默认 True）

        Returns:
            输出音频文件的路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"开始语音克隆: text='{text[:30]}...' "
            f"ref='{reference_wav_path}' "
            f"steps={inference_timesteps}"
        )

        wav = self.model.generate(
            text=text,
            reference_wav_path=str(reference_wav_path),
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
            denoise = denoise
        )

        sf.write(str(output_path), wav, self.model.tts_model.sample_rate)
        logger.info(f"语音生成完成: {output_path}")

        return str(output_path.resolve())

    
clone = VoiceCloneService()

def clone_text_to_speech(
    text: str,
    reference_wav_path: str | Path,
    output_path: str | Path,
    cfg_value: float = 2.0,
    inference_timesteps: int = 10,
) -> str:
    try:
        return clone.generate(
            text=text,
            reference_wav_path=reference_wav_path,
            output_path=output_path,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
        )
    finally:
        clone.unload()

if __name__ == "__main__":
    from modelscope import snapshot_download
    snapshot_download("OpenBMB/VoxCPM2", local_dir='./models/VoxCPM2') # 指定模型保存的本地路径

    from voxcpm import VoxCPM
    import soundfile as sf
    model = VoxCPM.from_pretrained('./models/VoxCPM2', load_denoiser=False)

    for i in range(10):
        wav = model.generate(
            text="VoxCPM2 是目前推荐使用的多语言语音合成版本。",
            reference_wav_path=r"C:\Users\45826\Desktop\Voxa\demo.wav",
            cfg_value=2.0,
            inference_timesteps=10,
            denoise=True
        )
        sf.write("demo.wav", wav, model.tts_model.sample_rate) 