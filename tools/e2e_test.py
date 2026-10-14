"""
端到端验证 + 截图：
  1. 以 --load-extension 启动 Chrome（独立临时 profile，不影响用户数据）
  2. 打开本地演示商品详情页，确认内容脚本注入成功 → 截图
  3. 点击「获取图片」→ 等待画廊页打开 → 截图
  4. 在画廊页点击「下载选中 (PNG)」→ 校验下载目录里的 PNG 文件
用法：python tools/e2e_test.py
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

ROOT = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab"
SHOTS = os.path.join(ROOT, "测试截图")
PROFILE = os.path.join(ROOT, ".tmp-chrome-profile")
DOWNLOADS = os.path.join(ROOT, ".tmp-downloads")
EXT_ID = None
PORT = 9222
BASE = "http://127.0.0.1:8777"

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

os.makedirs(SHOTS, exist_ok=True)
os.makedirs(DOWNLOADS, exist_ok=True)

# 解析扩展 ID（Chrome 用路径的 SHA256 前 16 字节映射为 a-p 字母）
import hashlib

h = hashlib.sha256(ROOT.encode("utf-16-le")).hexdigest()[:32]
EXT_ID = "".join(chr(ord("a") + int(c, 16)) for c in h)
print("extension id:", EXT_ID)


# ----------------------------------------------------------------- CDP 工具
class Tab:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=40)
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
        params = {"format": "png", "captureBeyondViewport": bool(full)}
        if full:
            metrics = self.send("Page.getLayoutMetrics")
            size = metrics.get("cssContentSize") or metrics.get("contentSize")
            params["clip"] = {"x": 0, "y": 0, "width": size["width"],
                              "height": min(size["height"], 8000), "scale": 1}
        data = self.send("Page.captureScreenshot", **params)["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        print("saved:", path, os.path.getsize(path), "bytes")

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


def wait_for(pred, timeout=30, interval=0.4, desc=""):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(interval)
    raise TimeoutError(f"等待超时：{desc}")


# ----------------------------------------------------------------- 启动 Chrome
if os.path.exists(PROFILE):
    subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", PROFILE], capture_output=True)

chrome = subprocess.Popen([
    CHROME,
    f"--remote-debugging-port={PORT}",
    "--remote-allow-origins=*",
    f"--user-data-dir={PROFILE}",
    f"--load-extension={ROOT}",
    f"--disable-extensions-except={ROOT}",
    "--no-first-run", "--no-default-browser-check",
    "--disable-features=Translate,OptimizationHints",
    "--window-size=1440,900",
    "--window-position=0,0",
    "about:blank",
])
print("chrome pid:", chrome.pid)
time.sleep(4)

# 让下载落到工作区内的临时目录，便于自动化校验（不污染真实下载目录）
try:
    dl_tab = new_tab("about:blank")
    tdl = Tab(dl_tab["webSocketDebuggerUrl"])
    tdl.send("Browser.setDownloadBehavior", behavior="allow",
             downloadPath=DOWNLOADS, eventsEnabled=True)
    tdl.close()
    print("download behavior set ->", DOWNLOADS)
except Exception as e:
    print("setDownloadBehavior failed:", e)

results = {}
try:
    # 确认扩展已加载（访问 chrome://extensions 读取内部页面）
    ext_tab = new_tab("chrome://extensions/")
    time.sleep(3)
    t = Tab(ext_tab["webSocketDebuggerUrl"])
    t.send("Page.enable")
    t.send("Runtime.enable")
    time.sleep(2)
    info = t.eval("""
      (async () => {
        const mgr = document.querySelector('extensions-manager');
        const items = mgr?.shadowRoot?.querySelector('extensions-item-list')
          ?.shadowRoot?.querySelectorAll('extensions-item') || [];
        return [...items].map(i => ({
          id: i.id,
          name: i.shadowRoot.querySelector('#name')?.textContent?.trim(),
          err: !!i.shadowRoot.querySelector('#errors-button')
        }));
      })()
    """, await_promise=True)
    print("extensions:", json.dumps(info, ensure_ascii=False))
    results["extensions"] = info
    t.shot(os.path.join(SHOTS, "插件-01-已加载.png"))
    t.close()

    # ---------------------------------------------------------- 演示商品页
    demo = new_tab(f"{BASE}/demo/index.html")
    time.sleep(2)
    td = Tab(demo["webSocketDebuggerUrl"])
    td.send("Page.enable")
    td.send("Runtime.enable")
    td.send("Emulation.setDeviceMetricsOverride", width=1440, height=900,
            deviceScaleFactor=1, mobile=False)
    time.sleep(3)

    injected = wait_for(lambda: td.eval("!!document.getElementById('imagegrab-fab')"),
                        timeout=20, desc="等待内容脚本注入按钮")
    print("button injected:", injected)

    # 把按钮区域圈出来做一张特写，同时保留整页大图
    td.shot(os.path.join(SHOTS, "插件-02-详情页按钮.png"))
    td.eval("window.__igBtnRect = (() => { const r = document.getElementById('imagegrab-fab').getBoundingClientRect();"
            "return {x:r.x-40,y:r.y-40,w:r.width+80,h:r.height+80}; })()")
    rect = td.eval("window.__igBtnRect")
    print("button rect:", rect)

    # ---------------------------------------------------------- 点击提取
    td.eval("document.getElementById('imagegrab-fab').click()")
    time.sleep(2)

    # 提取过程中的提示 toast 截图（趁滚动 + toast 出现时抓一张）
    for _ in range(40):
        state = td.eval("document.getElementById('imagegrab-fab')?.className || ''")
        if "is-busy" in state:
            break
        time.sleep(0.2)
    time.sleep(1.0)
    td.shot(os.path.join(SHOTS, "插件-03-提取中提示.png"))

    # 等待画廊页出现
    def find_gallery():
        for tg in targets():
            if tg["type"] == "page" and "gallery.html" in tg.get("url", ""):
                return tg
        return None

    gal_target = wait_for(find_gallery, timeout=60, desc="等待画廊页打开")
    print("gallery target:", gal_target["url"])
    tg = Tab(gal_target["webSocketDebuggerUrl"])
    tg.send("Page.enable")
    tg.send("Runtime.enable")
    tg.send("Emulation.setDeviceMetricsOverride", width=1440, height=900,
            deviceScaleFactor=1, mobile=False)
    time.sleep(3)

    stats = tg.eval("""
      ({
        cards: document.querySelectorAll('#grid .card').length,
        selected: document.getElementById('counter')?.textContent,
        meta: document.getElementById('metaInfo')?.textContent,
        thumbs: [...document.querySelectorAll('#grid .card')].slice(0,3)
                  .map(c => c.querySelector('img')?.getAttribute('src'))
      })
    """)
    print("gallery stats:", json.dumps(stats, ensure_ascii=False))
    results["gallery"] = stats

    # 等缩略图加载完成（is-loaded）再截图
    wait_for(lambda: tg.eval(
        "document.querySelectorAll('#grid .card.is-loaded').length >= 6"), timeout=25,
        desc="等待缩略图加载")
    time.sleep(1)
    tg.shot(os.path.join(SHOTS, "插件-04-画廊页.png"))

    # ---------------------------------------------------------- 下载验证
    tg.eval("document.getElementById('btnDownload').click()")
    time.sleep(1.2)
    tg.shot(os.path.join(SHOTS, "插件-05-下载进度.png"))

    def downloaded():
        d = os.path.join(DOWNLOADS, "ImageGrab")
        if not os.path.isdir(d):
            return None
        files = [f for f in os.listdir(d) if f.lower().endswith(".png")]
        return files if len(files) >= 6 else None

    files = wait_for(downloaded, timeout=90, desc="等待 PNG 下载完成")
    print("downloaded files:", json.dumps(files, ensure_ascii=False))
    results["downloads"] = files

    sizes = {f: os.path.getsize(os.path.join(DOWNLOADS, "ImageGrab", f)) for f in files}
    results["download_sizes"] = sizes
    print("sizes:", json.dumps(sizes, ensure_ascii=False))

    # 下载完成后的结果反馈浮层
    time.sleep(0.6)
    tg.shot(os.path.join(SHOTS, "插件-06-下载完成反馈.png"))

    # 单张下载按钮的 hover 效果
    tg.eval("document.querySelector('#grid .card').dispatchEvent(new MouseEvent('mouseover',{bubbles:true}))")
    time.sleep(0.5)

    # ---------------------------------------------------------- 弹窗截图
    pop = new_tab(f"chrome-extension://{EXT_ID}/popup.html")
    time.sleep(2)
    tp = Tab(pop["webSocketDebuggerUrl"])
    tp.send("Page.enable")
    tp.send("Runtime.enable")
    tp.send("Emulation.setDeviceMetricsOverride", width=320, height=430,
            deviceScaleFactor=2, mobile=False)
    time.sleep(2)
    tp.shot(os.path.join(SHOTS, "插件-07-弹窗.png"))
    results["popup_text"] = tp.eval("document.body.innerText")
    tp.close()

    td.close()
    tg.close()

finally:
    with open(os.path.join(SHOTS, "e2e-result.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n=== RESULT ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    try:
        chrome.terminate()
    except Exception:
        pass
