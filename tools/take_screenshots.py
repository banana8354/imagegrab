"""
截图脚本（CDP）：
  A. 插件界面：悬浮按钮+toast、画廊页、下载进度、下载完成反馈、插件弹窗
  B. 官网 docs：桌面整页、官网首屏、移动端（390px）整页
所有页面走本地 http 服务（127.0.0.1:8777），保证相对路径与 CORS 正常。
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab"
OUT = os.path.join(ROOT, "测试截图")
PROFILE = os.path.join(ROOT, ".tmp-shot-profile")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9222
BASE = "http://127.0.0.1:8777"

os.makedirs(OUT, exist_ok=True)


class Tab:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self.mid = 0

    def send(self, method, **params):
        self.mid += 1
        mid = self.mid
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method} -> {msg['error']}")
                return msg.get("result", {})

    def eval(self, expr, await_promise=False):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=await_promise, userGesture=True)
        return r.get("result", {}).get("value")

    def shot(self, path, full=False, scale=1):
        params = {"format": "png"}
        if full:
            m = self.send("Page.getLayoutMetrics")
            size = m.get("cssContentSize") or m.get("contentSize")
            params["captureBeyondViewport"] = True
            params["clip"] = {"x": 0, "y": 0, "width": size["width"],
                              "height": min(size["height"], 12000), "scale": scale}
        data = self.send("Page.captureScreenshot", **params)["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        print(f"  saved {os.path.basename(path)}  {os.path.getsize(path)/1024:.0f} KB", flush=True)

    def size(self, w, h, mobile=False, dpr=1):
        self.send("Emulation.setDeviceMetricsOverride", width=w, height=h,
                  deviceScaleFactor=dpr, mobile=mobile)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def targets():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=10) as r:
        return json.load(r)


def new_tab(url):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{url}", method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def open_page(url, w, h, dpr=1, mobile=False, settle=3.0):
    t = new_tab(url)
    tab = Tab(t["webSocketDebuggerUrl"])
    tab.send("Page.enable")
    tab.send("Runtime.enable")
    tab.size(w, h, mobile, dpr)
    time.sleep(settle)
    return tab


def wait_images(tab, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        done = tab.eval("""
          (() => {
            const imgs = [...document.images];
            return imgs.length > 0 && imgs.every(i => i.complete);
          })()
        """)
        if done:
            return True
        time.sleep(0.5)
    return False


# ------------------------------------------------------------------ 启动 Chrome
subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", PROFILE], capture_output=True)
proc = subprocess.Popen([
    CHROME, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
    f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check",
    "--disable-crash-reporter", "--force-color-profile=srgb",
    "--force-prefers-color-scheme=light",   # 固定浅色主题，保证截图风格一致
    "--hide-scrollbars", "--window-size=1440,900", "about:blank",
])
print("chrome pid", proc.pid, flush=True)
time.sleep(5)

try:
    print("\n=== A. 插件界面 ===", flush=True)

    # A1 详情页 + 悬浮按钮 + 提取完成提示
    t = open_page(f"{BASE}/tools/content-preview.html", 1440, 900, dpr=1, settle=4)
    t.eval("document.getElementById('imagegrab-fab').classList.remove('is-busy');"
           "document.querySelector('#imagegrab-fab .imagegrab-fab__text').textContent='获取图片'")
    time.sleep(1.5)
    t.shot(os.path.join(OUT, "插件-01-详情页悬浮按钮.png"))
    t.close()

    # A2 画廊页
    t = open_page(f"{BASE}/tools/gallery-preview.html", 1440, 900, dpr=1, settle=3)
    wait_images(t)
    time.sleep(1)
    t.shot(os.path.join(OUT, "插件-02-画廊页总览.png"))
    t.shot(os.path.join(OUT, "插件-03-画廊页整页.png"), full=True, scale=1)
    t.close()

    # A3 下载进度 + 结果反馈
    t = open_page(f"{BASE}/tools/gallery-preview.html", 1440, 900, dpr=1, settle=3)
    wait_images(t)
    t.eval("document.getElementById('btnDownload').click()")
    time.sleep(1.2)
    t.shot(os.path.join(OUT, "插件-04-下载进度.png"))
    time.sleep(2.6)
    t.shot(os.path.join(OUT, "插件-05-下载完成反馈.png"))
    t.close()

    # A4 插件弹窗
    t = open_page(f"{BASE}/tools/popup-preview.html", 320, 470, dpr=2, settle=2.5)
    t.shot(os.path.join(OUT, "插件-06-弹窗.png"))
    t.close()

    print("\n=== B. 官网 ===", flush=True)

    # B1 桌面首屏
    t = open_page(f"{BASE}/docs/index.html", 1440, 900, dpr=1, settle=3)
    t.eval("window.scrollTo(0,0)")
    time.sleep(1.4)
    t.shot(os.path.join(OUT, "官网-01-首屏.png"))

    # B2 桌面整页
    t.eval("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('is-visible'))")
    time.sleep(1.2)
    t.shot(os.path.join(OUT, "官网-02-整页.png"), full=True)

    # B3 平板宽度
    t.size(834, 1000)
    time.sleep(1.6)
    t.shot(os.path.join(OUT, "官网-03-平板.png"))

    # B4 手机宽度（含汉堡菜单展开）
    t.size(390, 844, mobile=True, dpr=2)
    time.sleep(1.5)
    t.shot(os.path.join(OUT, "官网-04-手机.png"))
    t.eval("document.getElementById('hamburger').click()")
    time.sleep(1)
    t.shot(os.path.join(OUT, "官网-05-手机菜单.png"))
    t.close()

    print("\nALL SCREENSHOTS DONE", flush=True)
finally:
    proc.terminate()
