"""
命令行语音克隆脚本

用法:
    python scripts/clone_voice.py --text "要合成的文本" --ref "参考音频.wav" --out "输出路径.wav"
    
    # 或者像原始代码那样直接运行:
    python scripts/clone_voice.py
"""
import argparse
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.clone_service import clone_text_to_speech


def main():
    parser = argparse.ArgumentParser(description="VoxCPM2 语音克隆")
    parser.add_argument("--text", type=str, help="要合成的文本")
    parser.add_argument("--ref", type=str, help="参考音频路径")
    parser.add_argument("--out", type=str, help="输出音频保存路径")
    parser.add_argument("--cfg", type=float, default=2.0, help="CFG 引导系数")
    parser.add_argument("--steps", type=int, default=10, help="推理步数")

    args = parser.parse_args()

    if args.text and args.ref and args.out:
        # 命令行模式
        output = clone_text_to_speech(
            text=args.text,
            reference_wav_path=args.ref,
            output_path=args.out,
            cfg_value=args.cfg,
            inference_timesteps=args.steps,
        )
        print(f"✅ 语音生成成功: {output}")
    else:
        # 交互/测试模式 - 使用原始代码的示例
        text = (
            "开学以来，离开过长沙市的所有同学，包括已请假与未请假，"
            "统一报备名字给副班长，并收集带行程的行程卡"
        )
        ref_path = (
            r"C:\Users\45826\Documents\xwechat_files\wxid_bm3qhh5nexkg22_c6a9\msg\file\2026-05\标准录音 4.mp3"
        )
        out_path = r"C:\Users\45826\Desktop\Voxa\123.wav"

        output = clone_text_to_speech(
            text=text,
            reference_wav_path=ref_path,
            output_path=out_path,
            cfg_value=2.0,
            inference_timesteps=10,
        )
        print(f"✅ 语音生成成功: {output}")


if __name__ == "__main__":
    main()
