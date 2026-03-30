"""
ritual_image.py — 仪式图片生成

为告别仪式生成视觉化图片（纯 Python 绘制，不依赖外部 AI API）。

三种仪式类型：
- burn: 烧掉日记/信念 — 温暖的火焰与光点
- capsule: 时间胶囊封印 — 信封/瓶子被封好
- letter: 未寄出的信 — 一封温暖的信纸

设计参考：
- docs/product/product-experience-design.md F02 §4.1-4.3
- 色彩：暖杏黄 #FFD4A2、珊瑚粉 #FF7F7F、薰衣草 #C5A3FF、米白 #FFF8F0

用法（由 AI agent 通过 exec 调用）：
    python3 ritual_image.py --type burn [--output <path>] [--open-date YYYY-MM-DD] [--text "自定义文字"]

输出（JSON, stdout）：
    {"status": "ok", "type": "burn", "output_path": "/tmp/moodcoco/ritual_burn_xxx.png", "width": 1080, "height": 1080}
    {"status": "error", "error": "PIL not available"}
"""

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path

# 尝试导入 PIL — 不可用时输出 error JSON 并退出
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ---------------------------------------------------------------------------
# 色板（F02 §4.3 风格指南）
# ---------------------------------------------------------------------------

BG_COLOR = (255, 248, 240)       # 米白 #FFF8F0
WARM_APRICOT = (255, 212, 162)   # 暖杏黄 #FFD4A2
CORAL_PINK = (255, 127, 127)     # 珊瑚粉 #FF7F7F
LAVENDER = (197, 163, 255)       # 薰衣草 #C5A3FF
MINT = (168, 230, 207)           # 薄荷绿 #A8E6CF
TEXT_COLOR = (93, 78, 55)        # 深棕 #5D4E37
TEXT_LIGHT = (139, 115, 85)      # 浅棕 #8B7355

SIZE = (1080, 1080)


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------

def _get_font(size: int):
    """尝试加载系统中文字体，fallback 到 PIL 默认。"""
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 绘制基础元素
# ---------------------------------------------------------------------------

def _draw_circle(draw, cx, cy, r, fill, alpha=255):
    """绘制一个填充圆。"""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _draw_soft_glow(img, cx, cy, radius, color, intensity=0.3):
    """在图像上叠加一个柔和光晕（用半透明圆层叠模拟）。"""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    steps = 15
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        alpha = int(255 * intensity * (1 - i / steps))
        c = color + (alpha,)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _draw_particles(draw, cx, cy, count, spread, colors):
    """绘制随机散布的小光点。"""
    random.seed(42)  # 确定性渲染
    for _ in range(count):
        x = cx + random.randint(-spread, spread)
        y = cy + random.randint(-spread, spread)
        r = random.randint(2, 6)
        color = random.choice(colors)
        _draw_circle(draw, x, y, r, color)


def _draw_text_centered(draw, text, y, font, fill=TEXT_COLOR, img_width=1080):
    """在指定 y 位置水平居中绘制文字。"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (img_width - text_width) // 2
    draw.text((x, y), text, fill=fill, font=font)


# ---------------------------------------------------------------------------
# 三种仪式图片
# ---------------------------------------------------------------------------

def generate_burn(output_path: str, text: str = None):
    """烧掉日记/信念 — 纸张在火焰中化为光点。"""
    img = Image.new("RGBA", SIZE, BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # 底部火焰光晕
    img = _draw_soft_glow(img, 540, 700, 400, CORAL_PINK, 0.25)
    img = _draw_soft_glow(img, 540, 650, 300, WARM_APRICOT, 0.35)
    draw = ImageDraw.Draw(img)

    # 中心纸张轮廓（简化的矩形，略微倾斜感用多边形）
    paper_coords = [(420, 380), (660, 380), (670, 620), (410, 620)]
    draw.polygon(paper_coords, fill=(255, 255, 250, 180))
    draw.polygon(paper_coords, outline=(220, 200, 170, 120), width=2)

    # 纸张上的"灰烬线条"
    for y_offset in range(400, 600, 30):
        draw.line(
            [(450, y_offset), (630, y_offset)],
            fill=(210, 195, 170, 100), width=1
        )

    # 火焰光点
    particle_colors = [
        CORAL_PINK + (200,),
        WARM_APRICOT + (220,),
        (255, 200, 100, 180),
        (255, 240, 200, 150),
    ]
    _draw_particles(draw, 540, 550, 80, 200, particle_colors)

    # 上升的光点（烟尘感）
    for i in range(30):
        x = 540 + random.randint(-120, 120)
        y = 350 - random.randint(0, 200)
        r = random.randint(1, 4)
        alpha = random.randint(60, 150)
        draw.ellipse([x - r, y - r, x + r, y + r],
                     fill=(255, 220, 180, alpha))

    # 标题
    font_title = _get_font(36)
    font_sub = _get_font(22)
    _draw_text_centered(draw, "烧掉了", 800, font_title, TEXT_COLOR)
    _draw_text_centered(draw, "从现在起，这些不再是你的负担", 860, font_sub, TEXT_LIGHT)

    if text:
        font_custom = _get_font(18)
        _draw_text_centered(draw, text, 910, font_custom, TEXT_LIGHT)

    # 保存
    img = img.convert("RGB")
    img.save(output_path, "PNG", quality=95)
    return output_path


def generate_capsule(output_path: str, open_date: str = None, text: str = None):
    """时间胶囊封印 — 封好的信封/瓶子。"""
    img = Image.new("RGBA", SIZE, BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # 背景光晕
    img = _draw_soft_glow(img, 540, 500, 350, LAVENDER, 0.2)
    img = _draw_soft_glow(img, 540, 500, 200, MINT, 0.15)
    draw = ImageDraw.Draw(img)

    # 信封主体
    env_top = 350
    env_bottom = 650
    env_left = 300
    env_right = 780

    # 信封底色
    draw.rounded_rectangle(
        [env_left, env_top, env_right, env_bottom],
        radius=16, fill=(255, 245, 235, 255)
    )
    draw.rounded_rectangle(
        [env_left, env_top, env_right, env_bottom],
        radius=16, outline=(220, 200, 180), width=2
    )

    # 信封翻盖（三角形）
    flap_top = env_top - 80
    draw.polygon(
        [(env_left, env_top), (540, flap_top), (env_right, env_top)],
        fill=(245, 235, 225)
    )
    draw.polygon(
        [(env_left, env_top), (540, flap_top), (env_right, env_top)],
        outline=(220, 200, 180), width=2
    )

    # 封印圆章
    seal_cx, seal_cy = 540, env_top
    draw.ellipse(
        [seal_cx - 30, seal_cy - 30, seal_cx + 30, seal_cy + 30],
        fill=CORAL_PINK
    )
    seal_font = _get_font(18)
    _draw_text_centered(draw, "封", seal_cy - 10, seal_font, (255, 255, 255), SIZE[0])

    # 星星装饰
    star_colors = [LAVENDER + (150,), MINT + (130,), WARM_APRICOT + (140,)]
    for _ in range(25):
        x = random.randint(200, 880)
        y = random.randint(150, 900)
        r = random.randint(2, 5)
        draw.ellipse([x - r, y - r, x + r, y + r],
                     fill=random.choice(star_colors))

    # 文字
    font_title = _get_font(36)
    font_sub = _get_font(22)
    font_date = _get_font(20)

    _draw_text_centered(draw, "时间胶囊已封好", 750, font_title, TEXT_COLOR)
    _draw_text_centered(draw, "写给未来的你", 810, font_sub, TEXT_LIGHT)

    if open_date:
        _draw_text_centered(draw, f"{open_date} 打开", 860, font_date, LAVENDER[:3])

    if text:
        font_custom = _get_font(18)
        _draw_text_centered(draw, text, 910, font_custom, TEXT_LIGHT)

    img = img.convert("RGB")
    img.save(output_path, "PNG", quality=95)
    return output_path


def generate_letter(output_path: str, text: str = None):
    """未寄出的信 — 一封温暖的信纸。"""
    img = Image.new("RGBA", SIZE, BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # 柔和背景光
    img = _draw_soft_glow(img, 540, 500, 400, WARM_APRICOT, 0.15)
    draw = ImageDraw.Draw(img)

    # 信纸
    paper_left, paper_top = 240, 200
    paper_right, paper_bottom = 840, 800
    draw.rounded_rectangle(
        [paper_left, paper_top, paper_right, paper_bottom],
        radius=12, fill=(255, 252, 248, 255)
    )
    draw.rounded_rectangle(
        [paper_left, paper_top, paper_right, paper_bottom],
        radius=12, outline=(230, 215, 195), width=2
    )

    # 信纸横线
    for y in range(280, 760, 40):
        draw.line(
            [(paper_left + 40, y), (paper_right - 40, y)],
            fill=(235, 225, 210), width=1
        )

    # 信纸左侧竖线（信纸设计常见元素）
    draw.line(
        [(paper_left + 60, paper_top + 20), (paper_left + 60, paper_bottom - 20)],
        fill=(255, 200, 180, 100), width=2
    )

    # 模拟手写文字痕迹（用短线条代表）
    random.seed(42)
    for y in range(290, 720, 40):
        line_len = random.randint(200, 480)
        draw.line(
            [(paper_left + 80, y - 5), (paper_left + 80 + line_len, y - 5)],
            fill=(180, 160, 140, 80), width=2
        )

    # 花朵装饰（右下角）
    flower_x, flower_y = 750, 730
    for angle in range(0, 360, 45):
        px = flower_x + int(20 * math.cos(math.radians(angle)))
        py = flower_y + int(20 * math.sin(math.radians(angle)))
        draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=CORAL_PINK + (120,))
    draw.ellipse([flower_x - 6, flower_y - 6, flower_x + 6, flower_y + 6],
                 fill=WARM_APRICOT)

    # 标题
    font_title = _get_font(36)
    font_sub = _get_font(22)
    _draw_text_centered(draw, "这封信，不用寄出去", 860, font_title, TEXT_COLOR)
    _draw_text_centered(draw, "写完了就好", 920, font_sub, TEXT_LIGHT)

    if text:
        font_custom = _get_font(18)
        _draw_text_centered(draw, text, 970, font_custom, TEXT_LIGHT)

    img = img.convert("RGB")
    img.save(output_path, "PNG", quality=95)
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

GENERATORS = {
    "burn": generate_burn,
    "capsule": generate_capsule,
    "letter": generate_letter,
}


def main():
    if not HAS_PIL:
        print(json.dumps({
            "status": "error",
            "error": "PIL not available",
            "hint": "pip install Pillow",
        }))
        sys.exit(1)

    parser = argparse.ArgumentParser(description="仪式图片生成")
    parser.add_argument("--type", required=True, choices=["burn", "capsule", "letter"],
                        help="仪式类型")
    parser.add_argument("--output", default=None,
                        help="输出路径，默认 /tmp/moodcoco/ritual_{type}_{timestamp}.png")
    parser.add_argument("--open-date", default=None,
                        help="时间胶囊开封日期 YYYY-MM-DD（仅 capsule 类型）")
    parser.add_argument("--text", default=None,
                        help="图片上叠加的自定义文字")
    args = parser.parse_args()

    # 确保输出目录存在
    timestamp = int(time.time())
    output_path = args.output or f"/tmp/moodcoco/ritual_{args.type}_{timestamp}.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        gen_func = GENERATORS[args.type]
        kwargs = {}
        if args.type == "capsule" and args.open_date:
            kwargs["open_date"] = args.open_date
        if args.text:
            kwargs["text"] = args.text

        gen_func(output_path, **kwargs)

        result = {
            "status": "ok",
            "type": args.type,
            "output_path": output_path,
            "width": SIZE[0],
            "height": SIZE[1],
            "error": None,
        }
    except Exception as e:
        result = {
            "status": "error",
            "type": args.type,
            "error": str(e),
        }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
