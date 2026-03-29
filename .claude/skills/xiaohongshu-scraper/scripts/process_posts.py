#!/usr/bin/env python3
"""
小红书数据处理脚本：将 JSONL 数据转化为 CSV + 独立 .md 文件

用法:
    python3 process_posts.py \
        --search-input search_results.jsonl \
        --detail-input post_details.jsonl \
        --output-dir posts \
        --csv xiaohongshu_data.csv
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime


def parse_jsonl(filepath):
    """读取 JSONL 文件，返回列表"""
    if not os.path.exists(filepath):
        return []
    results = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return results


def merge_data(search_results, post_details):
    """合并搜索结果和帖子详情数据"""
    detail_map = {d['noteId']: d for d in post_details if 'noteId' in d}

    merged = []
    for sr in search_results:
        note_id = sr.get('noteId', '')
        detail = detail_map.get(note_id, {})

        post = {
            'noteId': note_id,
            'title': detail.get('title') or sr.get('title', ''),
            'type': detail.get('type') or sr.get('type', 'normal'),
            'likes': detail.get('likes') or sr.get('likes', 0),
            'collected': detail.get('collected') or sr.get('collected', 0),
            'comments_count': detail.get('comments_count') or sr.get('comments_count', 0),
            'shared': detail.get('shared') or sr.get('shared', 0),
            'date': sr.get('date', ''),
            'time': detail.get('time', 0),
            'userName': detail.get('userName') or sr.get('userName', ''),
            'userId': detail.get('userId') or sr.get('userId', ''),
            'ipLocation': detail.get('ipLocation', ''),
            'desc': detail.get('desc', ''),
            'tags': detail.get('tags', []),
            'imageUrls': detail.get('imageUrls', []),
            'coverUrl': sr.get('coverUrl', ''),
            'comments': detail.get('comments', []),
            'url': f"https://www.xiaohongshu.com/explore/{note_id}",
        }
        merged.append(post)

    # 添加只在 detail 中有而搜索结果中没有的帖子
    search_ids = {sr.get('noteId', '') for sr in search_results}
    for d in post_details:
        if d.get('noteId', '') not in search_ids:
            merged.append({
                'noteId': d['noteId'],
                'title': d.get('title', ''),
                'type': d.get('type', 'normal'),
                'likes': d.get('likes', 0),
                'collected': d.get('collected', 0),
                'comments_count': d.get('comments_count', 0),
                'shared': d.get('shared', 0),
                'date': '',
                'time': d.get('time', 0),
                'userName': d.get('userName', ''),
                'userId': d.get('userId', ''),
                'ipLocation': d.get('ipLocation', ''),
                'desc': d.get('desc', ''),
                'tags': d.get('tags', []),
                'imageUrls': d.get('imageUrls', []),
                'coverUrl': '',
                'comments': d.get('comments', []),
                'url': f"https://www.xiaohongshu.com/explore/{d['noteId']}",
            })

    # 按点赞数降序排序
    merged.sort(key=lambda x: x.get('likes', 0), reverse=True)
    return merged


def format_number(n):
    """格式化数字显示"""
    if n >= 10000:
        return f"{n/10000:.1f}W"
    elif n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def generate_md(post, index, output_dir):
    """生成单个帖子的 .md 文件"""
    note_id = post['noteId']
    filename = f"{index:03d}_{note_id}.md"
    filepath = os.path.join(output_dir, filename)

    lines = []

    # YAML frontmatter
    lines.append('---')
    lines.append(f"post_number: {index}")
    lines.append(f"noteId: {note_id}")
    lines.append(f"title: \"{post['title'].replace('\"', '\\\"')}\"")
    lines.append(f"type: {post['type']}")
    lines.append(f"likes: {post['likes']}")
    lines.append(f"collected: {post['collected']}")
    lines.append(f"comments_count: {post['comments_count']}")
    lines.append(f"shared: {post['shared']}")
    lines.append(f"date: {post['date']}")
    lines.append(f"author: {post['userName']}")
    lines.append('---')
    lines.append('')

    # Header
    likes_str = format_number(post['likes'])
    collected_str = format_number(post['collected'])
    comments_str = format_number(post['comments_count'])
    lines.append(f"# Post #{index} — {likes_str} likes, {collected_str} collected, {comments_str} comments")
    lines.append('')

    # Metadata
    lines.append(f"**Author:** {post['userName']}")
    type_label = '图文' if post['type'] == 'normal' else '视频'
    date_str = post['date']
    if post['time']:
        try:
            date_str = datetime.fromtimestamp(post['time'] / 1000).strftime('%Y-%m-%d')
        except (ValueError, OSError):
            pass
    ip_str = f" | **IP:** {post['ipLocation']}" if post['ipLocation'] else ''
    lines.append(f"**Type:** {type_label} | **Date:** {date_str}{ip_str}")
    lines.append(f"**Engagement:** {likes_str} likes, {collected_str} collected, {comments_str} comments, {format_number(post['shared'])} shared")
    lines.append(f"**URL:** {post['url']}")
    lines.append('')

    # Content
    lines.append('## Content')
    lines.append('')
    if post['desc']:
        lines.append(post['desc'])
    else:
        lines.append('*(正文未获取，需导航到帖子详情页)*')
    lines.append('')

    # Tags
    if post['tags']:
        lines.append('## Tags')
        lines.append('')
        lines.append(' '.join(f"#{t}" for t in post['tags']))
        lines.append('')

    # Images
    image_urls = post.get('imageUrls', [])
    if not image_urls and post.get('coverUrl'):
        image_urls = [post['coverUrl']]
    if image_urls:
        lines.append('## Images')
        lines.append('')
        for i, url in enumerate(image_urls, 1):
            lines.append(f"![Image {i}]({url})")
        lines.append('')

    # Comments
    comments = post.get('comments', [])
    if comments:
        lines.append('## Top Comments')
        lines.append('')
        for c in comments:
            likes_info = f" ({c.get('likes', 0)} likes"
            if c.get('subCommentCount', 0) > 0:
                likes_info += f", {c['subCommentCount']} replies"
            likes_info += ")"
            lines.append(f"- **{c.get('userName', 'unknown')}**{likes_info}: {c.get('content', '')}")
        lines.append('')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return filename


def generate_csv(posts, csv_path):
    """生成 CSV 汇总文件"""
    fieldnames = [
        'post_number', 'noteId', 'title', 'type', 'likes', 'collected',
        'comments_count', 'shared', 'date', 'author', 'desc_preview',
        'tags', 'top_comments_count', 'url'
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, post in enumerate(posts, 1):
            desc_preview = post.get('desc', '')[:200].replace('\n', ' ')
            tags = ', '.join(post.get('tags', []))
            comments_count = len(post.get('comments', []))

            writer.writerow({
                'post_number': i,
                'noteId': post['noteId'],
                'title': post['title'],
                'type': post['type'],
                'likes': post['likes'],
                'collected': post['collected'],
                'comments_count': post['comments_count'],
                'shared': post['shared'],
                'date': post['date'],
                'author': post['userName'],
                'desc_preview': desc_preview,
                'tags': tags,
                'top_comments_count': comments_count,
                'url': post['url'],
            })


def main():
    parser = argparse.ArgumentParser(description='Process 小红书 JSONL data into CSV + .md files')
    parser.add_argument('--search-input', default='search_results.jsonl',
                        help='搜索结果 JSONL 文件路径')
    parser.add_argument('--detail-input', default='post_details.jsonl',
                        help='帖子详情 JSONL 文件路径')
    parser.add_argument('--output-dir', default='posts',
                        help='.md 文件输出目录')
    parser.add_argument('--csv', default='xiaohongshu_data.csv',
                        help='CSV 输出路径')
    args = parser.parse_args()

    # 读取数据
    search_results = parse_jsonl(args.search_input)
    post_details = parse_jsonl(args.detail_input)

    if not search_results and not post_details:
        print("Error: No data found. Check input file paths.", file=sys.stderr)
        sys.exit(1)

    print(f"Search results: {len(search_results)}")
    print(f"Post details: {len(post_details)}")

    # 合并数据
    posts = merge_data(search_results, post_details)
    print(f"Merged posts: {len(posts)}")

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)

    # 生成 .md 文件
    for i, post in enumerate(posts, 1):
        filename = generate_md(post, i, args.output_dir)

    print(f"Generated {len(posts)} .md files in {args.output_dir}/")

    # 生成 CSV
    generate_csv(posts, args.csv)
    print(f"Generated CSV: {args.csv}")

    # 统计汇报
    normal_count = sum(1 for p in posts if p['type'] == 'normal')
    video_count = sum(1 for p in posts if p['type'] == 'video')
    with_desc = sum(1 for p in posts if p.get('desc'))
    with_comments = sum(1 for p in posts if p.get('comments'))
    avg_likes = sum(p['likes'] for p in posts) / len(posts) if posts else 0
    max_likes = max((p['likes'] for p in posts), default=0)

    print(f"\n--- Summary ---")
    print(f"Total: {len(posts)} posts ({normal_count} 图文, {video_count} 视频)")
    print(f"With content: {with_desc}/{len(posts)}")
    print(f"With comments: {with_comments}/{len(posts)}")
    print(f"Avg likes: {avg_likes:.0f}, Max likes: {max_likes}")


if __name__ == '__main__':
    main()
