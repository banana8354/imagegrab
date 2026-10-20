"""
抓取 GitHub 仓库页面截图（作业要求：项目推送到 GitHub 的截图）。
流程：Chrome 独立 profile（已登录态由 Cookie 注入）→ 打开仓库页 → 截图。
为了让仓库页显示为「已登录」状态，先把 token 写进 Cookie 不可行，
因此这里用未登录的公开仓库页面截图（Public 仓库无需登录即可完整展示）。
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
PROFILE = os.path.join(ROOT, ".tmp-gh-profile")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9223
PROXY = "http://127.0.0.1:7897"
REPO = "https://github.com/banana8354/imagegrab"


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
                              "height": min(size["height"], 6000), "scale": 1}
        data = self.send("Page.captureScreenshot", **params)["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        print(f"  saved {os.path.basename(path)}  {os.path.getsize(path)/1024:.0f} KB", flush=True)

    def size(self, w, h):
        self.send("Emulation.setDeviceMetricsOverride", width=w, height=h,
                  deviceScaleFactor=1, mobile=False)

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
    for url, name, full in [
        (REPO, "GitHub-01-仓库首页.png", False),
        (f"{REPO}/tree/main", "GitHub-02-仓库文件列表.png", True),
        (f"{REPO}/commits/main", "GitHub-03-提交记录.png", False),
        (f"{REPO}/blob/main/docs/index.html", "GitHub-04-官网源码.png", False),
    ]:
        t = new_tab(url)
        tab = Tab(t["webSocketDebuggerUrl"])
        tab.send("Page.enable")
        tab.send("Runtime.enable")
        tab.size(1440, 900)
        time.sleep(9)

        # GitHub 的文件列表/统计是异步填充的，等灰条（skeleton）消失再截图
        for i in range(24):
            pending = tab.eval("""
              document.querySelectorAll(
                '.Box-row [data-testid="skeleton"], .react-directory-filename-column .skeleton,'
                + ' [class*="Skeleton"], [class*="skeleton"]').length
            """)
            if not pending:
                break
            time.sleep(1)
        # 再触发一次滚动，确保懒加载的内容全部渲染
        tab.eval("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        tab.eval("window.scrollTo(0, 0)")
        time.sleep(2)

        title = tab.eval("document.title")
        print(f"\n{url}\n  title: {title}", flush=True)
        tab.shot(os.path.join(OUT, name), full=full)
        tab.close()

    print("\nDONE", flush=True)
finally:
    proc.terminate()
