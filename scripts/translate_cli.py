"""
命令行翻译工具

用法:
    python scripts/translate_cli.py "Hello world" --target zh-CN
    python scripts/translate_cli.py "你好世界" --source zh-CN --target en
"""
import argparse
import sys

from app.services.translate_service import translate_svc


def main():
    parser = argparse.ArgumentParser(description="翻译文本")
    parser.add_argument("text", help="待翻译文本")
    parser.add_argument("--source", default="auto", help="源语言（默认自动检测）")
    parser.add_argument("--target", default="zh-CN", help="目标语言（默认中文）")
    parser.add_argument("--list-languages", action="store_true", help="列出支持的语言")

    args = parser.parse_args()

    if args.list_languages:
        print("支持的语音：")
        for name, code in translate_svc.supported_languages.items():
            print(f"  {name:12s} -> {code}")
        sys.exit(0)

    if not translate_svc.available:
        print("错误: 缺少 translators 依赖，请执行: pip install translators")
        sys.exit(1)

    try:
        result = translate_svc.translate(
            text=args.text,
            source=args.source,
            target=args.target,
        )
        print(f"[翻译] {result['source']} -> {result['target']}")
        print(f"原文: {result['source_text']}")
        print(f"译文: {result['text']}")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
