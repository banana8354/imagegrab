"""
抓取 GitHub Pages 线上官网截图（作业要求：使用 GitHub Pages 发布的官网静态页面截图）。
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
PROFILE = os.path.join(ROOT, ".tmp-pages-profile")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9224
PROXY = "http://127.0.0.1:7897"
URL = "https://banana8354.github.io/imagegrab/"


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

    def shot(self, path, full=False):
        params = {"format": "png"}
        if full:
            m = self.send("Page.getLayoutMetrics")
            size = m.get("cssContentSize") or m.get("contentSize")
            params["captureBeyondViewport"] = True
            params["clip"] = {"x": 0, "y": 0, "width": size["width"],
                              "height": min(size["height"], 12000), "scale": 1}
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


subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", PROFILE], capture_output=True)
proc = subprocess.Popen([
    CHROME, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
    f"--user-data-dir={PROFILE}", f"--proxy-server={PROXY}",
    "--no-first-run", "--no-default-browser-check", "--disable-crash-reporter",
    "--force-prefers-color-scheme=light", "--hide-scrollbars",
    "--window-size=1440,900", "about:blank",
])
print("chrome pid", proc.pid, flush=True)
time.sleep(6)

try:
    t = new_tab(URL)
    tab = Tab(t["webSocketDebuggerUrl"])
    tab.send("Page.enable")
    tab.send("Runtime.enable")
    tab.send("Network.enable")

    # 收集网络请求，确认静态资源都是从 github.io 正常加载的
    loaded = tab.eval("performance.getEntriesByType('resource').map(r=>r.name)") or []

    tab.size(1440, 900)
    time.sleep(6)
    print("实际 URL:", tab.eval("location.href"), flush=True)
    print("标题:", tab.eval("document.title"), flush=True)

    # 等动画与字体稳定
    tab.eval("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('is-visible'))")
    time.sleep(1.5)
    tab.shot(os.path.join(OUT, "线上-01-Pages官网首屏.png"))

    # 整页
    tab.eval("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1.5)
    tab.shot(os.path.join(OUT, "线上-02-Pages官网整页.png"), full=True)

    # 各区块特写
    for sel, name in [("#features", "线上-03-Pages核心功能区.png"),
                      ("#install", "线上-04-Pages安装步骤区.png")]:
        tab.eval(f"document.querySelector('{sel}').scrollIntoView({{block:'start'}})")
        time.sleep(1.5)
        tab.shot(os.path.join(OUT, name))

    # 移动端
    tab.size(390, 844, mobile=True, dpr=2)
    tab.eval("window.scrollTo(0,0)")
    time.sleep(2)
    tab.shot(os.path.join(OUT, "线上-05-Pages移动端.png"))

    resources = tab.eval("performance.getEntriesByType('resource').map(r=>r.name)") or []
    print("\n加载的静态资源：", flush=True)
    for r in sorted(set(resources))[:15]:
        print("   ", r, flush=True)

    print("\nDONE", flush=True)
    tab.close()
finally:
    proc.terminate()
