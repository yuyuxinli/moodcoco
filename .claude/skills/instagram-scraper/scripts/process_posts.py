#!/usr/bin/env python3
"""
Process extracted Instagram post data from JSONL into CSV and individual .md files.

Handles two JSONL formats:
- v1 Compact: {n, sc, t, u, l, c, d, txt, imgs, tc}
- v2 Full: {shortcode, type, url, likes, comments_count, date, content, image_urls, image_urls_clean, comments}

Usage:
    python3 process_posts.py --input posts_data.jsonl --output-dir posts/ --csv instagram_data.csv [--images-dir images/]
"""
import json
import csv
import os
import argparse


def normalize_post(raw):
    """Normalize post data from either compact or full format."""
    if 'sc' in raw:
        return {
            'shortcode': raw.get('sc', ''),
            'type': raw.get('t', ''),
            'url': raw.get('u', ''),
            'likes': raw.get('l', 0),
            'comments_count': raw.get('c', 0),
            'date': raw.get('d', ''),
            'content': raw.get('txt', ''),
            'image_urls': raw.get('imgs', []),
            'image_urls_clean': [u.split('?')[0] for u in raw.get('imgs', [])],
            'comments': [{'user': c.get('a', ''), 'text': c.get('t', ''), 'likes': c.get('l', 0)} for c in raw.get('tc', [])],
        }
    # v2 format — normalize comments_count field
    if 'comments' in raw and isinstance(raw.get('comments'), list) and 'comments_count' not in raw:
        raw['comments_count'] = len(raw['comments'])
    return raw


def fmt_num(n):
    """Format number with K/M suffix."""
    n = int(n) if n else 0
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def process_posts(input_file, output_dir, csv_file, images_dir=None):
    """Process JSONL file into CSV and individual .md files."""
    os.makedirs(output_dir, exist_ok=True)

    posts = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    posts.append(normalize_post(json.loads(line)))
                except json.JSONDecodeError as e:
                    print(f"Skipping invalid JSON line: {e}")

    print(f"Loaded {len(posts)} posts")

    # Write CSV
    csv_fields = ['post_number', 'shortcode', 'type', 'url', 'likes', 'comments_count',
                  'date', 'content', 'image_count', 'top_comments_count']

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()

        for i, post in enumerate(posts, 1):
            writer.writerow({
                'post_number': i,
                'shortcode': post.get('shortcode', ''),
                'type': post.get('type', ''),
                'url': post.get('url', ''),
                'likes': post.get('likes', ''),
                'comments_count': post.get('comments_count', ''),
                'date': post.get('date', ''),
                'content': post.get('content', ''),
                'image_count': len(post.get('image_urls', [])),
                'top_comments_count': len(post.get('comments', [])),
            })

    print(f"CSV saved to {csv_file} ({len(posts)} rows)")

    # Write individual .md files
    for i, post in enumerate(posts, 1):
        content = post.get('content', '')
        likes = post.get('likes', 0)
        comments_count = post.get('comments_count', 0)
        post_type = post.get('type', '')
        url = post.get('url', '')
        date = post.get('date', '')
        shortcode = post.get('shortcode', 'unknown')
        comments = post.get('comments', [])

        md_content = f"""---
post_number: {i}
shortcode: {shortcode}
url: {url}
type: {post_type}
likes: {likes}
comments_count: {comments_count}
date: {date}
---

# Post #{i} — {fmt_num(likes)} likes, {fmt_num(comments_count)} comments

**URL:** {url}
**Type:** {post_type} | **Date:** {date}
**Engagement:** {fmt_num(likes)} likes, {fmt_num(comments_count)} comments

## Content

{content}

## Images

"""
        # Use local image paths if images_dir exists, otherwise use clean URLs
        clean_urls = post.get('image_urls_clean', post.get('image_urls', []))
        for j, img_url in enumerate(clean_urls, 1):
            if images_dir:
                local_path = f"{images_dir}/{shortcode}_{j}.jpg"
                if os.path.exists(local_path):
                    md_content += f"![Image {j}]({local_path})\n\n"
                else:
                    md_content += f"![Image {j}]({img_url})\n\n"
            else:
                md_content += f"![Image {j}]({img_url})\n\n"

        if comments:
            md_content += "\n## Top Comments\n\n"
            for comment in comments:
                user = comment.get('user', comment.get('author', ''))
                text = comment.get('text', '')
                clikes = comment.get('likes', 0)
                like_str = f" ({clikes} likes)" if clikes else ""
                md_content += f"- **{user}**{like_str}: {text}\n"

        filename = f"{i:03d}_{shortcode}.md"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

    print(f"Individual .md files saved to {output_dir}/ ({len(posts)} files)")

    # Print summary stats
    all_likes = [p.get('likes', 0) for p in posts]
    all_comments = [p.get('comments_count', 0) for p in posts]
    all_fetched_comments = [len(p.get('comments', [])) for p in posts]
    reels = sum(1 for p in posts if p.get('type') == 'reel')
    total_images = sum(len(p.get('image_urls', [])) for p in posts)
    print(f"\n--- Summary ---")
    print(f"Total posts: {len(posts)} ({reels} reels, {len(posts)-reels} image posts)")
    print(f"Date range: {posts[-1].get('date', '?')} to {posts[0].get('date', '?')}")
    print(f"Avg likes: {sum(all_likes)//len(posts):,} | Max: {max(all_likes):,}")
    print(f"Avg comments: {sum(all_comments)//len(posts):,} | Max: {max(all_comments):,}")
    print(f"Total images: {total_images} (avg {total_images/len(posts):.1f}/post)")
    print(f"Total fetched comments: {sum(all_fetched_comments)} (avg {sum(all_fetched_comments)/len(posts):.1f}/post)")

    return posts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process Instagram post data')
    parser.add_argument('--input', default='posts_data.jsonl', help='Input JSONL file')
    parser.add_argument('--output-dir', default='posts', help='Output directory for .md files')
    parser.add_argument('--csv', default='instagram_data.csv', help='Output CSV file')
    parser.add_argument('--images-dir', default=None, help='Local images directory (optional)')

    args = parser.parse_args()
    process_posts(args.input, args.output_dir, args.csv, args.images_dir)
