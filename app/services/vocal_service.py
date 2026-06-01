"""
人声分离服务 - 基于 UVR5 (PyTorch GPU)
"""
import gc
import logging
import os
import sys
from pathlib import Path

import torch

from app.core.config import settings

logger = logging.getLogger(__name__)

# 将 uvr5_lib 加入 sys.path，使 vr.py 能 from lib.lib_v5 import ... 
_uvr5_lib_dir = Path(__file__).parent / "uvr5_lib"
if str(_uvr5_lib_dir) not in sys.path:
    sys.path.insert(0, str(_uvr5_lib_dir))

# 动态导入 vr 模块（避免 IDE 静态分析报 not found）
import importlib
_vr_mod = importlib.import_module("vr")
AudioPre = _vr_mod.AudioPre
AudioPreDeEcho = _vr_mod.AudioPreDeEcho

# UVR5 权重目录
WEIGHTS_DIR = Path(settings.UVR5_WEIGHTS_PATH)


# 支持的格式
SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}


def _get_device() -> str:
    """自动选择设备"""
    if torch.cuda.is_available():
        device = "cuda"
        logger.info(f"使用 GPU 加速: {torch.cuda.get_device_name(0)}")
    else:
        device = "cpu"
        logger.info("GPU 不可用，使用 CPU")
    return device


def _detect_format(audio_path: str) -> str:
    """检测输入音频格式"""
    ext = Path(audio_path).suffix.lower()
    if ext in SUPPORTED_FORMATS:
        return ext.lstrip(".")
    return "wav"


def _list_models() -> dict[str, str]:
    """列出可用模型 {名称: 路径}"""
    models = {}
    if not WEIGHTS_DIR.exists():
        return models
    for f in WEIGHTS_DIR.iterdir():
        if f.suffix in (".pth", ".ckpt"):
            name = f.stem
            models[name] = str(f)
    # 检查 onnx_dereverb 子目录
    onnx_dir = WEIGHTS_DIR / "onnx_dereverb_By_FoxJoy"
    if onnx_dir.exists():
        models["onnx_dereverb_By_FoxJoy"] = str(onnx_dir / "vocals.onnx")
    return models


class VocalService:
    """人声分离服务（UVR5 PyTorch）"""

    def __init__(self):
        self._model = None
        self._model_name = None
        self._device = _get_device()
        self._is_half = True if self._device == "cuda" else False
        self.output_dir = Path(settings.OUTPUT_DIR)
        self.available_models = _list_models()

        logger.info(f"可用 UVR5 模型 ({len(self.available_models)}): {list(self.available_models.keys())}")

    def unload(self):
        """释放模型和 GPU 显存，避免影响后续语音克隆"""
        if self._model is not None:
            logger.info("卸载 UVR5 模型，释放 GPU 显存...")
            del self._model
            self._model = None
            self._model_name = None
        if self._device == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        gc.collect()
        logger.info("UVR5 显存已释放")

    def _init(self, model_name: str = None) -> str:
        """初始化/切换模型，返回选中的模型名"""
        # 确定使用哪个模型
        if model_name is not None and model_name in self.available_models:
            chosen = model_name
        else:
            # 默认优先用 HP2（速度快，效果好）
            for preferred in ["HP2_all_vocals", "HP5_only_main_vocal",
                              "VR-DeEchoAggressive", "model_bs_roformer_ep_317_sdr_12.9755"]:
                if preferred in self.available_models:
                    chosen = preferred
                    break
            else:
                # 用第一个可用的
                chosen = next(iter(self.available_models), None)
                if chosen is None:
                    raise RuntimeError("未找到任何 UVR5 模型文件")

        # 如果模型已加载且没变，跳过
        if self._model is not None and self._model_name == chosen:
            return chosen

        model_path = self.available_models[chosen]
        logger.info(f"加载 UVR5 模型: {chosen} ({model_path})")

        try:
            if "DeEcho" in chosen:
                self._model = AudioPreDeEcho(
                    agg=10,
                    model_path=model_path,
                    device=self._device,
                    is_half=self._is_half,
                )
            else:
                self._model = AudioPre(
                    agg=10,
                    model_path=model_path,
                    device=self._device,
                    is_half=self._is_half,
                )
            self._model_name = chosen
            logger.info(f"UVR5 模型加载完成: {chosen}")
        except Exception as e:
            raise RuntimeError(f"UVR5 模型加载失败 ({chosen}): {e}")

        return chosen

    def separate(self, audio_path: str, model_name: str = None) -> dict[str, str]:
        """
        人声分离

        Args:
            audio_path: 输入音频路径
            model_name: 指定模型（None=自动选择）

        Returns:
            {"vocals": "人声路径", "accompaniment": "伴奏路径"}
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {audio_path}")

        # 检测输入格式
        in_format = _detect_format(audio_path)
        logger.info(f"输入格式: .{in_format}，输出保持相同格式")

        # 初始化模型
        chosen_model = self._init(model_name)

        # 判断是否 HP3 模式
        is_hp3 = "HP3" in chosen_model

        # 输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 调用的模型路径和输出路径（人声/伴奏互换 by design）
        # AudioPre: ins_root=伴奏, vocal_root=人声
        # AudioPreDeEcho: ins_root=人声(反), vocal_root=伴奏(反) 
        if "DeEcho" in chosen_model:
            ins_root = str(self.output_dir)
            vocal_root = str(self.output_dir)
        else:
            ins_root = str(self.output_dir)
            vocal_root = str(self.output_dir)

        logger.info(f"开始分离: {path.name} (模型={chosen_model})")

        self._model._path_audio_(
            str(path),
            ins_root=ins_root,
            vocal_root=vocal_root,
            format=in_format,
            is_hp3=is_hp3,
        )

        # 收集输出文件
        result = {}
        stem = path.stem
        for f in os.listdir(self.output_dir):
            if f.startswith(stem):
                fp = str(self.output_dir / f)
                # 原始 UVR5 命名: _instrument=伴奏, _vocal=人声
                if "_vocal" in f.lower():
                    result.setdefault("vocals", fp)
                elif "_instrument" in f.lower():
                    result.setdefault("accompaniment", fp)
                else:
                    result.setdefault("vocals", fp)

        # 如果只找到一个文件，两个键都指向它
        unique = list(result.values())
        if len(unique) == 1:
            result["accompaniment"] = result.get("vocals", unique[0])
        elif len(unique) == 0:
            raise RuntimeError(f"分离完成但未找到输出文件，请检查 data/out 目录")

        logger.info(f"分离完成: {result}")
        return result

    def vocals(self, audio_path: str, out_path: str = None, model_name: str = None) -> str:
        """提取人声"""
        result = self.separate(audio_path, model_name=model_name)
        return result.get("vocals", "")

    def accompaniment(self, audio_path: str, out_path: str = None, model_name: str = None) -> str:
        """提取伴奏"""
        result = self.separate(audio_path, model_name=model_name)
        return result.get("accompaniment", "")


# 全局单例
vocal = VocalService()
