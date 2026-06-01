"""
命令行语音识别脚本 (Whisper)

用法:
    python scripts/transcribe.py -i "audio.wav"
    python scripts/transcribe.py -i "audio.wav" -l zh
    python scripts/transcribe.py -i "audio.wav" --translate
    python scripts/transcribe.py -i "audio.wav" -l zh -s   # 只输出文本
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.asr_service import asr


def main():
    parser = argparse.ArgumentParser(description="Whisper 语音识别")
    parser.add_argument("-i", "--input", type=str, required=True, help="输入音频路径")
    parser.add_argument("-l", "--language", type=str, default=None, help="语言代码 (zh/en/ja 等，默认自动检测)")
    parser.add_argument("--translate", action="store_true", help="翻译为英文")
    parser.add_argument("-s", "--simple", action="store_true", help="仅输出文本")
    parser.add_argument("--model", type=str, default=None, help=f"Whisper 模型大小 (tiny/base/small/medium/large/turbo，默认: {settings.WHISPER_MODEL_SIZE})")

    args = parser.parse_args()

    # 检查文件
    path = Path(args.input)
    if not path.exists():
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    # 如果指定了不同模型，创建新实例
    service = asr
    if args.model:
        from app.services.asr_service import WhisperService, _get_device
        service = WhisperService(model_name=args.model)
        print(f"  设备:     {service._device}")

    # 执行识别
    task = "translate" if args.translate else "transcribe"
    result = service.transcribe(
        audio_path=str(path),
        language=args.language,
        task=task,
    )

    if args.simple:
        # 仅输出文本
        print(result["text"])
    else:
        # 详细输出
        print(f"\n{'='*50}")
        print(f"  语音识别结果")
        print(f"{'='*50}")
        print(f"  音频:     {path.name}")
        print(f"  时长:     {result['duration']:.1f}s")
        print(f"  语言:     {result['language']}")
        print(f"  模型:     {args.model or 'base'}")
        print(f"{'='*50}")
        print(f"  文本:     {result['text']}")
        print(f"{'='*50}")

        # 分段显示
        segments = result.get("segments", [])
        if segments:
            print(f"\n  分段详情 ({len(segments)} 段):")
            print(f"  {'-'*50}")
            for seg in segments:
                start = seg["start"]
                end = seg["end"]
                text = seg["text"].strip()
                print(f"  [{start:6.1f}s - {end:6.1f}s]  {text}")
            print(f"  {'-'*50}")


if __name__ == "__main__":
    main()
