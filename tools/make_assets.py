"""生成插图标与演示商品图（纯 Pillow，无外部依赖）"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab"
ICON_DIR = os.path.join(ROOT, "icons")
DEMO_DIR = os.path.join(ROOT, "demo", "assets")
os.makedirs(ICON_DIR, exist_ok=True)
os.makedirs(DEMO_DIR, exist_ok=True)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(size, c1, c2, diagonal=True):
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / max(w - 1, 1) + y / max(h - 1, 1)) / 2 if diagonal else y / max(h - 1, 1)
            px[x, y] = lerp(c1, c2, t)
    return img


FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def centered(draw, text, font, box, fill):
    x0, y0, x1, y1 = box
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    draw.text((x0 + (x1 - x0 - (r - l)) / 2 - l, y0 + (y1 - y0 - (b - t)) / 2 - t), text, font=font, fill=fill)


# ---------------------------------------------------------------- 插件图标
def draw_icon(size):
    """圆角渐变底 + 白色图片山形图标（自绘，保证与页面风格一致）"""
    scale = 8
    s = size * scale
    img = gradient((s, s), (91, 123, 255), (122, 77, 255))
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.24), fill=255)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)

    d = ImageDraw.Draw(out)
    u = s / 24.0
    # 相框
    d.rounded_rectangle([3.2 * u, 4.0 * u, 20.8 * u, 20.0 * u], radius=3.2 * u,
                        outline=(255, 255, 255, 255), width=max(1, int(1.9 * u)))
    # 太阳
    d.ellipse([7.0 * u, 7.6 * u, 10.2 * u, 10.8 * u], fill=(255, 255, 255, 255))
    # 山形
    d.polygon([(6.4 * u, 17.0 * u), (11.4 * u, 11.4 * u), (15.0 * u, 15.2 * u),
               (17.2 * u, 12.8 * u), (20.2 * u, 17.0 * u)], fill=(255, 255, 255, 255))
    return out.resize((size, size), Image.LANCZOS)


for n in (16, 32, 48, 128):
    draw_icon(n).save(os.path.join(ICON_DIR, f"icon{n}.png"))

# ---------------------------------------------------------------- 演示商品图
PALETTE = [
    ("新品首发", (91, 123, 255), (122, 77, 255)),
    ("详情图 02", (255, 138, 91), (255, 77, 129)),
    ("细节实拍", (16, 185, 129), (56, 189, 248)),
    ("材质特写", (245, 158, 11), (239, 68, 68)),
    ("场景展示", (99, 102, 241), (236, 72, 153)),
    ("规格参数", (14, 165, 233), (45, 212, 191)),
    ("包装清单", (168, 85, 247), (99, 102, 241)),
    ("售后保障", (34, 197, 94), (132, 204, 22)),
]

W, H = 800, 800
for i, (title, c1, c2) in enumerate(PALETTE, 1):
    img = gradient((W, H), c1, c2)
    d = ImageDraw.Draw(img, "RGBA")

    # 斜向高光条带
    for k in range(-H, W, 90):
        d.polygon([(k, H), (k + 34, H), (k + H + 34, 0), (k + H, 0)], fill=(255, 255, 255, 22))

    # 半透明产品卡片
    d.rounded_rectangle([70, 150, W - 70, H - 150], radius=42, fill=(255, 255, 255, 38),
                        outline=(255, 255, 255, 130), width=3)
    centered(d, title, load_font(66), (70, 250, W - 70, 360), (255, 255, 255, 255))
    centered(d, f"IMAGE GRAB  ·  DEMO {i:02d}", load_font(30), (70, 380, W - 70, 440),
             (255, 255, 255, 205))
    centered(d, "800 × 800 · PNG", load_font(26), (70, H - 250, W - 70, H - 190),
             (255, 255, 255, 180))

    img.save(os.path.join(DEMO_DIR, f"product_{i:02d}.png"), optimize=True)

# ---------------------------------------------------------------- 一个纯色小图，用于验证"过滤小图标"逻辑
tiny = Image.new("RGB", (24, 24), (240, 240, 240))
tiny.save(os.path.join(DEMO_DIR, "logo_tiny.png"))
logo = Image.new("RGB", (160, 48), (255, 255, 255))
ImageDraw.Draw(logo).text((8, 14), "DEMO SHOP LOGO", font=load_font(16), fill=(90, 90, 90))
logo.save(os.path.join(DEMO_DIR, "brand_logo.png"))

print("icons:", sorted(os.listdir(ICON_DIR)))
print("demo assets:", sorted(os.listdir(DEMO_DIR)))
