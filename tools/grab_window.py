"""抓取用户当前已打开的窗口截图（不新开页面）。

优先 PrintWindow(PW_RENDERFULLCONTENT)（能抓到被遮挡窗口的内容），
失败则退回屏幕 BitBlt 拷贝。
用法：python tools/grab_window.py [标题关键词...]
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

OUT = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab\测试截图"
os.makedirs(OUT, exist_ok=True)

PW_RENDERFULLCONTENT = 0x00000002
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def list_windows():
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            rect = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            out.append((hwnd, buf.value, rect.left, rect.top,
                        rect.right - rect.left, rect.bottom - rect.top))
        return True

    user32.EnumWindows(cb, None)
    return out


def capture(hwnd, w, h, mode="print"):
    hdc_win = user32.GetWindowDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    gdi32.SelectObject(hdc_mem, hbmp)

    if mode == "print":
        user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
    else:
        # 从屏幕对应位置拷贝（要求窗口在最前）
        hdc_screen = user32.GetDC(0)
        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, SRCCOPY)
        user32.ReleaseDC(0, hdc_screen)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h          # 负数 = 自上而下
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)
    return img


targets_words = sys.argv[1:] or ["Token", "token", "GitHub"]
wins = list_windows()
print("=== 当前可见窗口 ===")
for hwnd, title, x, y, w, h in wins:
    print(f"  hwnd={hwnd}  pos=({x},{y})  size={w}x{h}  title={title}")

cands = [w for w in wins if any(t.lower() in w[1].lower() for t in targets_words) and w[4] > 500]
print("\n候选人（关键词匹配且宽度>500）:", [(c[1][:60], c[4], c[5]) for c in cands])

if not cands:
    print("没有匹配到目标窗口")
    sys.exit(1)

hwnd, title, x, y, w, h = max(cands, key=lambda c: c[4] * c[5])
print(f"\n选中: {title}  {w}x{h}")

for mode, name in (("print", "插件-00-当前窗口.png"), ("screen", "插件-00b-当前窗口截图拷贝.png")):
    img = capture(hwnd, w, h, mode)
    path = os.path.join(OUT, name)
    img.save(path)
    print(f"  [{mode}] 已保存 {name}  {os.path.getsize(path)/1024:.0f} KB")
