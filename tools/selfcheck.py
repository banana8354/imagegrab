"""提交前自检：清单合法性、被引用文件是否存在、JS 语法、官网资源可达性"""
import json
import os
import re
import subprocess
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab"
ok = True


def check(cond, label, detail=""):
    global ok
    mark = "PASS" if cond else "FAIL"
    if not cond:
        ok = False
    print(f"[{mark}] {label}" + (f"  -> {detail}" if detail else ""))


# 1. manifest.json
m = json.load(open(os.path.join(ROOT, "manifest.json"), encoding="utf-8"))
check(m.get("manifest_version") == 3, "manifest_version = 3")
check(set(m["permissions"]) >= {"activeTab", "scripting", "downloads", "storage"},
      "权限包含 activeTab/scripting/downloads/storage", str(m["permissions"]))
hosts = m["host_permissions"]
for must in ["*://*.taobao.com/*", "*://*.tmall.com/*", "*://*.jd.com/*",
             "*://*.pinduoduo.com/*", "*://*.yangkeduo.com/*"]:
    check(must in hosts, f"host_permissions 覆盖 {must}")
check(m["background"]["service_worker"] == "background.js", "Service Worker 指向 background.js")

# 2. 被引用的文件都存在
refs = set()
refs.update(m.get("icons", {}).values())
refs.update(m.get("action", {}).get("default_icon", {}).values())
refs.add(m["action"]["default_popup"])
refs.add(m["background"]["service_worker"])
for cs in m["content_scripts"]:
    refs.update(cs.get("js", []))
    refs.update(cs.get("css", []))
for r in refs:
    check(os.path.exists(os.path.join(ROOT, r)), f"清单引用文件存在: {r}")

# 3. gallery.html 引用
gh = open(os.path.join(ROOT, "gallery.html"), encoding="utf-8").read()
for asset in re.findall(r'(?:href|src)="([^"]+)"', gh):
    check(os.path.exists(os.path.join(ROOT, asset)), f"gallery.html 资源存在: {asset}")

# 4. JS 语法检查（node --check）
for js in ["content.js", "background.js", "gallery.js", "popup.js",
           "docs/js/main.js", "tools/static-server.js"]:
    p = os.path.join(ROOT, js)
    r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
    check(r.returncode == 0, f"JS 语法正确: {js}", r.stderr.strip()[:200])

# 5. 官网资源与本地服务可达性
base = "http://127.0.0.1:8777"
for path in ["/docs/index.html", "/docs/css/style.css", "/docs/js/main.js",
             "/docs/assets/favicon.svg", "/docs/images/website.png",
             "/demo/index.html", "/demo/assets/product_01.png",
             "/gallery.html", "/popup.html", "/manifest.json"]:
    try:
        with urllib.request.urlopen(base + path, timeout=8) as r:
            check(r.status == 200, f"本地服务可访问 {path}", str(r.status))
    except Exception as e:
        check(False, f"本地服务可访问 {path}", str(e)[:120])

# 6. 官网 HTML 结构要求（语义化标签 / 区块 id）
idx = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
for tag in ["<header", "<nav", "<main", "<section", "<footer"]:
    check(tag in idx, f"官网使用语义化标签 {tag}>")
for anchor in ['id="intro"', 'id="features"', 'id="install"', 'id="faq"', 'id="download"']:
    check(anchor in idx, f"官网包含区块 {anchor}")

# 7. CSS 变量与响应式断点
css = open(os.path.join(ROOT, "docs", "css", "style.css"), encoding="utf-8").read()
check(":root" in css and "--primary" in css, "官网样式使用 :root CSS 变量")
check("min-width: 768px" in css and "min-width: 1024px" in css, "官网包含平板/桌面断点")
check("max-width: 359px" in css, "官网保证 320px 宽度可用")

print("\n结果:", "全部通过 ✅" if ok else "存在失败项 ❌")
