"""离线夹具：给 popup 提供 chrome.* 模拟数据，用于截图预览。"""
import os

ROOT = r"C:\Users\30816\Documents\deepseek-harness\default-workspace\imagegrab"
src = open(os.path.join(ROOT, "popup.html"), encoding="utf-8").read()

stub = """
  <script>
    // ---- 离线夹具：模拟扩展环境（真实插件里由 chrome.tabs / background.js 提供）----
    window.chrome = {
      tabs: {
        query: async () => [{
          id: 1, active: true,
          url: 'https://item.taobao.com/item.htm?id=888888888',
          title: '秋冬加厚保暖连帽羽绒服 男女同款'
        }],
        sendMessage: async () => ({ ok: true })
      },
      runtime: {
        sendMessage: async (msg) => {
          if (msg.type === 'GET_HISTORY') {
            const now = Date.now();
            return { ok: true, history: [
              { site: '淘宝', count: 8, extractedAt: now - 6 * 60e3 },
              { site: '京东', count: 14, extractedAt: now - 3 * 3600e3 },
              { site: '拼多多商家版', count: 21, extractedAt: now - 26 * 3600e3 }
            ] };
          }
          return { ok: true };
        }
      }
    };
  </script>
"""

# 在 popup.js 之前插入夹具，并用 <base> 让 popup.css / popup.js 仍相对扩展根目录解析
out = src.replace("<title>图提取 ImageGrab</title>",
                  '<title>图提取 ImageGrab</title>\n  <base href="../">')
out = out.replace('<script src="popup.js"></script>', stub + '  <script src="popup.js"></script>')
assert "<base" in out and "chrome.tabs" in out, "未能插入夹具脚本"

dst = os.path.join(ROOT, "tools", "popup-preview.html")
open(dst, "w", encoding="utf-8").write(out)
print("written:", dst)
