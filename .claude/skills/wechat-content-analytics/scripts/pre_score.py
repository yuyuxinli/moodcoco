#!/usr/bin/env python3
"""WeChat Pre-publish Article Scorer

Analyzes a markdown article against quantitative metrics before publishing.
Outputs JSON with structural metrics and rhythm analysis.

Usage:
    python pre_score.py "/path/to/article.md"
    python pre_score.py "/path/to/article.md" --output /tmp/score.json
"""

import sys
import json
import re
import argparse
from pathlib import Path


# Baselines from historical data (SKILL.md)
BASELINES = {
    "title_length": {"min": 14, "max": 18, "label": "标题字数"},
    "total_words": {"min": 2500, "max": 3500, "label": "总字数"},
    "chapter_count": {"min": 4, "max": 5, "label": "章节数"},
    "words_per_chapter": {"min": 500, "max": 700, "label": "章均字数"},
    "bold_density_per_1k": {"min": 1.0, "max": 3.0, "label": "金句密度(/千字)"},
}


def count_chinese_chars(text: str) -> int:
    """Count Chinese characters + basic CJK punctuation as 'words'."""
    # Count CJK unified ideographs
    cjk = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    # Count CJK punctuation and fullwidth forms as half
    punct = len(re.findall(r'[\u3000-\u303f\uff00-\uffef]', text))
    # Count ASCII alphanumeric words (each word = 1)
    ascii_words = len(re.findall(r'[a-zA-Z0-9]+', text))
    return cjk + punct + ascii_words


def strip_markdown(text: str) -> str:
    """Remove markdown formatting, keep plain text."""
    # Remove reference section
    text = re.split(r'^---\s*$', text, flags=re.MULTILINE)[0]
    # Remove headings markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    # Remove links
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    # Remove footnote refs like <sup>[1]</sup>
    text = re.sub(r'<sup>\[?\d+\]?</sup>', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove blockquotes
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    return text


def extract_body(text: str) -> str:
    """Extract article body: exclude reference section and brand CTA."""
    # Split at --- (reference divider)
    parts = re.split(r'^---\s*$', text, flags=re.MULTILINE)
    return parts[0]


def analyze_article(filepath: str) -> dict:
    """Analyze a markdown article and return quantitative metrics."""
    content = Path(filepath).read_text(encoding="utf-8")
    body = extract_body(content)
    plain = strip_markdown(body)

    # --- Title ---
    title_match = re.match(r'^#\s+(.+)', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""
    title_length = count_chinese_chars(title)

    # --- Chapters ---
    chapters = re.findall(r'^###\s+(.+)', body, re.MULTILINE)
    chapter_count = len(chapters)

    # Split body by chapter headings to get per-chapter content
    chapter_sections = re.split(r'^###\s+.+', body, flags=re.MULTILINE)
    # First section is content before first ###, skip if empty
    chapter_texts = []
    for i, section in enumerate(chapter_sections):
        stripped = strip_markdown(section).strip()
        if stripped and i > 0:  # skip pre-chapter content
            chapter_texts.append(stripped)
        elif stripped and i == 0 and chapter_count == 0:
            # No chapters, entire body is one section
            chapter_texts.append(stripped)

    # --- Word counts ---
    total_words = count_chinese_chars(plain.strip())
    chapter_word_counts = [count_chinese_chars(t) for t in chapter_texts]
    avg_words_per_chapter = (
        round(sum(chapter_word_counts) / len(chapter_word_counts))
        if chapter_word_counts else 0
    )

    # --- Bold phrases (金句) ---
    bold_matches = re.findall(r'\*\*(.+?)\*\*', body)
    bold_count = len(bold_matches)
    bold_density_per_1k = round(bold_count / max(total_words, 1) * 1000, 2)

    # --- Brand bridge ---
    has_brand_bridge = bool(re.search(r'心情可可|可可', body))

    # --- Share CTA ---
    last_500 = plain[-500:] if len(plain) >= 500 else plain
    has_share_cta = bool(re.search(r'转发|分享|在看|点赞', last_500))

    # --- Questions (engagement hooks) ---
    questions = re.findall(r'[？?]', body)
    question_count = len(questions)

    # --- 300-word rhythm analysis ---
    rhythm = analyze_rhythm(body, chapter_texts)

    # --- Status evaluation ---
    metrics = {
        "title": title,
        "title_length": title_length,
        "chapter_count": chapter_count,
        "chapter_titles": chapters,
        "total_words": total_words,
        "chapter_word_counts": chapter_word_counts,
        "words_per_chapter": avg_words_per_chapter,
        "bold_count": bold_count,
        "bold_phrases": bold_matches,
        "bold_density_per_1k": bold_density_per_1k,
        "has_brand_bridge": has_brand_bridge,
        "has_share_cta": has_share_cta,
        "question_count": question_count,
        "rhythm": rhythm,
    }

    # Evaluate against baselines
    evaluations = evaluate_baselines(metrics)
    metrics["evaluations"] = evaluations

    return metrics


def analyze_rhythm(body: str, chapter_texts: list) -> dict:
    """Analyze 300-character rhythm for turn points and flat zones."""
    plain = strip_markdown(body).strip()
    segment_size = 300
    segments = []

    for i in range(0, len(plain), segment_size):
        segment = plain[i:i + segment_size]
        if not segment.strip():
            continue

        # Count turn points in this segment
        turn_points = 0
        # Questions
        turn_points += len(re.findall(r'[？?]', segment))
        # Short paragraphs (< 20 chars between double newlines)
        short_paras = re.findall(r'\n\n(.{1,20})\n\n', segment)
        turn_points += len(short_paras)
        # Exclamation/emphasis
        turn_points += len(re.findall(r'[！!]', segment))

        segments.append({
            "index": len(segments),
            "char_range": f"{i}-{min(i + segment_size, len(plain))}",
            "turn_points": turn_points,
            "is_flat": turn_points == 0,
        })

    flat_zones = [s for s in segments if s["is_flat"]]
    # Consecutive flat zones (2+ in a row)
    consecutive_flat = []
    streak = 0
    for s in segments:
        if s["is_flat"]:
            streak += 1
        else:
            if streak >= 2:
                consecutive_flat.append({
                    "start_segment": s["index"] - streak,
                    "length": streak,
                    "char_range": f"{(s['index'] - streak) * segment_size}-{s['index'] * segment_size}",
                })
            streak = 0
    if streak >= 2:
        consecutive_flat.append({
            "start_segment": len(segments) - streak,
            "length": streak,
            "char_range": f"{(len(segments) - streak) * segment_size}-{len(segments) * segment_size}",
        })

    return {
        "segment_count": len(segments),
        "segment_size": segment_size,
        "total_turn_points": sum(s["turn_points"] for s in segments),
        "flat_zone_count": len(flat_zones),
        "consecutive_flat_zones": consecutive_flat,
        "segments": segments,
    }


def evaluate_baselines(metrics: dict) -> list:
    """Evaluate metrics against baselines, return status for each."""
    results = []
    for key, baseline in BASELINES.items():
        value = metrics.get(key)
        if value is None:
            status = "unknown"
        elif baseline["min"] <= value <= baseline["max"]:
            status = "ok"
        elif value < baseline["min"]:
            status = "low"
        else:
            status = "high"

        results.append({
            "metric": key,
            "label": baseline["label"],
            "value": value,
            "baseline": f"{baseline['min']}-{baseline['max']}",
            "status": status,
        })

    # Non-range checks
    results.append({
        "metric": "has_brand_bridge",
        "label": "品牌桥接",
        "value": metrics["has_brand_bridge"],
        "baseline": "有",
        "status": "ok" if metrics["has_brand_bridge"] else "missing",
    })
    results.append({
        "metric": "has_share_cta",
        "label": "分享CTA",
        "value": metrics["has_share_cta"],
        "baseline": "有",
        "status": "ok" if metrics["has_share_cta"] else "missing",
    })
    flat_zones = len(metrics["rhythm"]["consecutive_flat_zones"])
    results.append({
        "metric": "consecutive_flat_zones",
        "label": "平直段",
        "value": flat_zones,
        "baseline": "0",
        "status": "ok" if flat_zones == 0 else "warning",
    })

    return results


def main():
    parser = argparse.ArgumentParser(description="WeChat Pre-publish Article Scorer")
    parser.add_argument("file", help="Markdown article file path")
    parser.add_argument("--output", "-o", default=None, help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    metrics = analyze_article(args.file)
    output = json.dumps(metrics, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Score saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
