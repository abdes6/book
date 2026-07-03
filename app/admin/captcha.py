"""图形验证码生成器 — 带旋转、扭曲和噪声干扰。"""
import random
import io
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter


_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _random_color(lo=0, hi=120):
    return tuple(random.randint(lo, hi) for _ in range(3))


def _draw_noise_arcs(draw, w, h, count=3):
    for _ in range(count):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = random.randint(0, w), random.randint(0, h)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        if x1 == x2:
            x2 += 1
        if y1 == y2:
            y2 += 1
        draw.arc([x1, y1, x2, y2], random.randint(0, 360),
                 random.randint(30, 180), fill=(180, 180, 180), width=1)


def _draw_noise_dots(draw, w, h, count=60):
    for _ in range(count):
        x, y = random.randint(0, w - 1), random.randint(0, h - 1)
        draw.point((x, y), fill=_random_color(100, 200))


def generate_captcha():
    """生成 4 字符图形验证码。"""
    code = ''.join(random.choices(_CHARS, k=4))
    w, h = 140, 50

    img = Image.new('RGB', (w, h), (245, 242, 237))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype('arial.ttf', 28)
    except (IOError, OSError):
        font = ImageFont.load_default()

    for i, ch in enumerate(code):
        char_img = Image.new('RGBA', (35, 44), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((3, 2), ch, font=font, fill=_random_color(0, 80))

        angle = random.randint(-30, 30)
        char_img = char_img.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))

        x_offset = 8 + i * 33 + random.randint(-3, 3)
        y_offset = 3 + int(2 * math.sin(i * 1.2))
        img.paste(char_img, (x_offset, y_offset), char_img)

    _draw_noise_arcs(draw, w, h, count=4)
    _draw_noise_dots(draw, w, h, count=50)

    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))

    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return code, buf
