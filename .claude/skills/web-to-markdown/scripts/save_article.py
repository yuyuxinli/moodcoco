#!/usr/bin/env python3
"""
save_article.py — 把从 stdin 读入的文章内容保存为 Markdown 文件

用法：
  echo '{"title":"xxx","content":"..."}' | python3 save_article.py --output /path/to/output.md

  或多 chunk 模式：
  python3 save_article.py --output /path/to/output.md --chunks chunk1.txt chunk2.txt chunk3.txt

参数：
  --output: 输出文件路径
  --chunks: 多个 chunk 文件路径（按顺序拼接）
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Save article as Markdown')
    parser.add_argument('--output', '-o', required=True, help='Output markdown file path')
    parser.add_argument('--chunks', nargs='*', help='Chunk files to concatenate')
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.chunks:
        # 多 chunk 模式：拼接所有 chunk 文件
        content_parts = []
        for chunk_file in args.chunks:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                content_parts.append(f.read())
        content = '\n'.join(content_parts)
    else:
        # stdin JSON 模式
        data = json.load(sys.stdin)
        content = data.get('content', '')

    output_path.write_text(content, encoding='utf-8')
    print(f'Saved: {output_path} ({len(content)} chars)')


if __name__ == '__main__':
    main()
