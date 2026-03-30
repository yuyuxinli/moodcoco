"""
milestone_image.py — 里程碑纪念图生成

为对话次数里程碑（10/30/50/100）生成温暖的纪念图片。

设计参考：
- docs/product/product-experience-design.md F02 §4.1 场景 I3
- 尺寸：1080×810（4:3）
- 色彩：暖杏黄 #FFD4A2、珊瑚粉 #FF7F7F、薰衣草 #C5A3FF、米白 #FFF8F0

用法（由 AI agent 通过 exec 调用）：
    python3 milestone_image.py --count 30 [--output <path>] [--username <name>]

输出（JSON, stdout）：
    {"status": "ok", "count": 30, "output_path": "...", "width": 1080, "height": 810}
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------------------------------------------------------------------------
# 色板
# ---------------------------------------------------------------------------

BG_COLOR = (255, 248, 240)  # 米白
WARM_APRICOT = (255, 212, 162)  # 暖杏黄
CORAL_PINK = (255, 127, 127)  # 珊瑚粉
LAVENDER = (197, 163, 255)  # 薰衣草
MINT = (168, 230, 207)  # 薄荷绿
TEXT_COLOR = (93, 78, 55)  # 深棕
TEXT_LIGHT = (139, 115, 85)  # 浅棕

SIZE = (1080, 810)  # 4:3 比例

# 里程碑对应的祝福语
MILESTONE_MESSAGES = {
    10: ("认识 10 天了呢", "每次聊天都是一颗小种子"),
    30: ("我们认识一个月了", "你比自己以为的勇敢"),
    50: ("第 50 次对话", "谢谢你一直愿意来找我"),
    100: ("第 100 次了", "这一路，你走了好远"),
}

DEFAULT_MESSAGE = ("又是一个小里程碑", "谢谢你信任我")


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------


def _get_font(size: int):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_text_centered(draw, text, y, font, fill=TEXT_COLOR, img_width=1080):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (img_width - text_width) // 2
    draw.text((x, y), text, fill=fill, font=font)


def _draw_soft_glow(img, cx, cy, radius, color, intensity=0.3):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    steps = 12
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        alpha = int(255 * intensity * (1 - i / steps))
        c = (*color, alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    return Image.alpha_composite(img.convert("RGBA"), overlay)


# ---------------------------------------------------------------------------
# 生成里程碑纪念图
# ---------------------------------------------------------------------------


def generate_milestone(count: int, output_path: str, username: str | None = None):
    """生成里程碑纪念图。"""
    img = Image.new("RGBA", SIZE, (*BG_COLOR, 255))
    draw = ImageDraw.Draw(img)

    # 柔和背景光
    img = _draw_soft_glow(img, 540, 380, 350, WARM_APRICOT, 0.2)
    img = _draw_soft_glow(img, 540, 380, 200, MINT, 0.12)
    draw = ImageDraw.Draw(img)

    # 装饰星点
    random.seed(count)  # 每个里程碑固定随机种子
    star_colors = [
        (*LAVENDER, 120),
        (*CORAL_PINK, 100),
        (*WARM_APRICOT, 130),
        (*MINT, 110),
    ]
    for _ in range(40):
        x = random.randint(80, 1000)
        y = random.randint(60, 750)
        r = random.randint(2, 6)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=random.choice(star_colors))

    # 中心数字圆
    number_cx, number_cy = 540, 300
    circle_r = 90

    # 外圈光晕
    img = _draw_soft_glow(img, number_cx, number_cy, circle_r + 40, CORAL_PINK, 0.15)
    draw = ImageDraw.Draw(img)

    # 圆底色
    draw.ellipse(
        [
            number_cx - circle_r,
            number_cy - circle_r,
            number_cx + circle_r,
            number_cy + circle_r,
        ],
        fill=(255, 240, 230),
    )
    draw.ellipse(
        [
            number_cx - circle_r,
            number_cy - circle_r,
            number_cx + circle_r,
            number_cy + circle_r,
        ],
        outline=WARM_APRICOT,
        width=3,
    )

    # 数字
    font_number = _get_font(72)
    _draw_text_centered(draw, str(count), number_cy - 38, font_number, CORAL_PINK[:3])

    # 祝福语
    title, subtitle = MILESTONE_MESSAGES.get(count, DEFAULT_MESSAGE)
    font_title = _get_font(34)
    font_sub = _get_font(22)

    _draw_text_centered(draw, title, 460, font_title, TEXT_COLOR)
    _draw_text_centered(draw, subtitle, 520, font_sub, TEXT_LIGHT)

    # 用户名（如果有）
    if username:
        font_name = _get_font(20)
        _draw_text_centered(
            draw, f"—— 可可给{username}的小卡片", 580, font_name, TEXT_LIGHT
        )

    # 底部日期
    from datetime import datetime

    today_str = datetime.now().strftime("%Y.%m.%d")
    font_date = _get_font(16)
    _draw_text_centered(draw, today_str, 740, font_date, (180, 165, 145))

    # 保存
    img = img.convert("RGB")
    img.save(output_path, "PNG", quality=95)
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not HAS_PIL:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "PIL not available",
                    "hint": "pip install Pillow",
                }
            )
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description="里程碑纪念图生成")
    parser.add_argument(
        "--count", type=int, required=True, help="对话次数里程碑（10/30/50/100）"
    )
    parser.add_argument("--output", default=None, help="输出路径")
    parser.add_argument("--username", default=None, help="用户昵称")
    args = parser.parse_args()

    timestamp = int(time.time())
    output_path = args.output or f"/tmp/moodcoco/milestone_{args.count}_{timestamp}.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        generate_milestone(args.count, output_path, username=args.username)
        result = {
            "status": "ok",
            "count": args.count,
            "output_path": output_path,
            "width": SIZE[0],
            "height": SIZE[1],
            "error": None,
        }
    except Exception as e:
        result = {
            "status": "error",
            "count": args.count,
            "error": str(e),
        }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
