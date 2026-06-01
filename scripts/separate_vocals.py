"""
命令行人声分离

用法:
    python scripts/separate_vocals.py -i audio.wav            # 分离人声+伴奏（MP3，快速）
    python scripts/separate_vocals.py -i audio.wav --vocals    # 仅人声
    python scripts/separate_vocals.py -i audio.wav --acc       # 仅伴奏
    python scripts/separate_vocals.py -i audio.wav --model high  # 高质量模式
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.vocal_service import vocal


def main():
    p = argparse.ArgumentParser(description="人声分离")
    p.add_argument("-i", "--input", required=True, help="输入音频")
    p.add_argument("--vocals", action="store_true", help="仅提取人声")
    p.add_argument("--acc", "--accompaniment", action="store_true", help="仅提取伴奏")
    p.add_argument("--model", choices=["fast", "balanced", "high"], default=None,
                    help="模型: fast(快速默认) / balanced(均衡) / high(高质量慢)")

    args = p.parse_args()

    if not Path(args.input).exists():
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    if args.vocals:
        out = vocal.vocals(args.input)
        print(f"✅ 人声: {out}")
    elif args.acc:
        out = vocal.accompaniment(args.input)
        print(f"✅ 伴奏: {out}")
    else:
        r = vocal.separate(args.input)
        print(f"✅ 分离完成")
        for k, v in r.items():
            size = Path(v).stat().st_size / 1024 / 1024
            print(f"   {k}: {v} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
