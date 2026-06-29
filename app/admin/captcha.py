import random
import io
from PIL import Image, ImageDraw


def generate_captcha():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    code = ''.join(random.choices(chars, k=4))
    img = Image.new('RGB', (120, 40), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for i, c in enumerate(code):
        draw.text((10 + i * 28, 8), c, fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)))
    for _ in range(8):
        draw.line([(random.randint(0, 120), random.randint(0, 40)) for _ in range(2)], fill=(180, 180, 180))
    buf = io.BytesIO()
    img.save(buf, 'png')
    buf.seek(0)
    return code, buf
