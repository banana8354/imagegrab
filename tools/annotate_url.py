"""给线上官网截图加一条浏览器风格地址栏，直观展示域名（作业要求第 3 项：域名地址）"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab"
SHOTS = os.path.join(ROOT, "测试截图")
FONT = r"C:\Windows\Fonts\msyh.ttc"

URL = "https://banana8354.github.io/imagegrab/"
BAR_H = 52


def load_font(size):
    for p in (FONT, r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def add_url_bar(src, dst, url=URL, scale=1):
    img = Image.open(src).convert("RGB")
    w, h = img.size
    out = Image.new("RGB", (w, h + BAR_H * scale), (255, 255, 255))
    out.paste(img, (0, BAR_H * scale))

    d = ImageDraw.Draw(out)
    # 顶部条
    d.rectangle([0, 0, w, BAR_H * scale], fill=(242, 244, 248))
    d.line([0, BAR_H * scale - 1, w, BAR_H * scale - 1], fill=(214, 219, 228), width=1)

    # 三个窗口圆点
    cx = int(18 * scale)
    for color in ((255, 95, 87), (254, 188, 46), (40, 200, 64)):
        r = int(6 * scale)
        d.ellipse([cx - r, int(BAR_H * scale / 2) - r, cx + r, int(BAR_H * scale / 2) + r],
                  fill=color)
        cx += int(22 * scale)

    # 地址栏
    bx0 = int(96 * scale)
    bx1 = w - int(20 * scale)
    by0 = int(9 * scale)
    by1 = BAR_H * scale - int(11 * scale)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=int((by1 - by0) / 2),
                        fill=(255, 255, 255), outline=(206, 212, 222), width=max(1, scale))
    # 锁标
    lx = bx0 + int(16 * scale)
    ly = int((by0 + by1) / 2)
    d.rectangle([lx, ly - int(2 * scale), lx + int(8 * scale), ly + int(7 * scale)],
                outline=(90, 100, 115), width=max(1, scale))
    d.arc([lx + int(1 * scale), ly - int(8 * scale), lx + int(7 * scale), ly + int(2 * scale)],
          180, 360, fill=(90, 100, 115), width=max(1, scale))

    font = load_font(int(15 * scale))
    d.text((lx + int(20 * scale), ly - int(9 * scale)), url, font=font, fill=(32, 38, 50))
    d.text((bx1 - int(150 * scale), ly - int(9 * scale)), "GitHub Pages",
           font=load_font(int(13 * scale)), fill=(120, 130, 145))

    out.save(dst)
    print(f"saved {os.path.basename(dst)}  {out.size}  {os.path.getsize(dst)/1024:.0f} KB")


add_url_bar(os.path.join(SHOTS, "线上-01-Pages官网首屏.png"),
            os.path.join(SHOTS, "线上-00-Pages官网首屏(带域名).png"), scale=2)
