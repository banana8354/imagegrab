/**
 * 图提取 ImageGrab —— background.js（Service Worker, MV3）
 * 职责：
 *   1. 接收内容脚本提取到的图片列表并暂存；
 *   2. 打开画廊页 gallery.html；
 *   3. 处理跨域图片下载（fetch -> createImageBitmap -> OffscreenCanvas -> PNG）；
 *   4. 通过 chrome.downloads API 保存文件并回报进度。
 */

const STORE_KEY = 'imagegrab_payload';
const MAX_HISTORY = 5;

/* ------------------------------------------------------------------ */
/* 1. 消息入口                                                         */
/* ------------------------------------------------------------------ */

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg?.type) {
        case 'EXTRACT_DONE': {
          // 暂存数据 + 记录来源，随后打开画廊
          await chrome.storage.session.set({
            [STORE_KEY]: { ...msg.payload, tabId: sender?.tab?.id ?? null }
          });
          await rememberHistory(msg.payload);
          const url = chrome.runtime.getURL('gallery.html');
          // 复用已打开的画廊页，避免开一堆标签
          const existing = await chrome.tabs.query({ url });
          if (existing.length) {
            await chrome.tabs.update(existing[0].id, { active: true, url });
          } else {
            await chrome.tabs.create({ url });
          }
          sendResponse({ ok: true });
          break;
        }

        case 'OPEN_GALLERY': {
          await chrome.tabs.create({ url: chrome.runtime.getURL('gallery.html') });
          sendResponse({ ok: true });
          break;
        }

        case 'GET_PAYLOAD': {
          const data = await chrome.storage.session.get(STORE_KEY);
          sendResponse({ ok: true, payload: data[STORE_KEY] || null });
          break;
        }

        case 'GET_HISTORY': {
          const data = await chrome.storage.local.get('imagegrab_history');
          sendResponse({ ok: true, history: data.imagegrab_history || [] });
          break;
        }

        case 'DOWNLOAD_ONE': {
          const result = await downloadAsPng(msg.image, msg.index);
          sendResponse({ ok: true, result });
          break;
        }

        case 'DOWNLOAD_MANY': {
          // 逐个下载并回报进度，避免一次性并发过高被浏览器限流
          const list = msg.images || [];
          const results = [];
          for (let i = 0; i < list.length; i += 1) {
            try {
              const r = await withRetry(() => downloadAsPng(list[i], i + 1), 2);
              results.push({ ok: true, ...r });
            } catch (err) {
              results.push({ ok: false, error: String(err?.message || err), url: list[i]?.url });
            }
            // 通知画廊当前进度（画廊可能已关闭，忽略错误）
            chrome.runtime.sendMessage({
              type: 'DOWNLOAD_PROGRESS',
              done: i + 1,
              total: list.length,
              current: list[i]?.url || ''
            }).catch(() => {});
            // 轻微间隔，避免触发浏览器下载限流
            await sleep(120);
          }
          sendResponse({ ok: true, results });
          break;
        }

        default:
          sendResponse({ ok: false, error: 'UNKNOWN_MESSAGE' });
      }
    } catch (err) {
      console.error('[ImageGrab][background]', err);
      sendResponse({ ok: false, error: String(err?.message || err) });
    }
  })();
  return true; // 保持消息通道，用于异步 sendResponse
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 简单重试：网络抖动时再试一次 */
async function withRetry(fn, retries = 1) {
  let lastErr;
  for (let i = 0; i <= retries; i += 1) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      await sleep(400 * (i + 1));
    }
  }
  throw lastErr;
}

/* ------------------------------------------------------------------ */
/* 2. 下载：统一转成 PNG                                               */
/* ------------------------------------------------------------------ */

/**
 * 把任意格式的图片下载为 PNG。
 * Service Worker 中没有 DOM，使用 fetch + createImageBitmap + OffscreenCanvas，
 * 这样即使图片服务器未开放 CORS 头，也能借助扩展的 host_permissions 正常取回数据。
 * @param {{url:string, name?:string}} image
 * @param {number} index 序号，用于文件名补零
 */
async function downloadAsPng(image, index) {
  if (!image?.url) throw new Error('缺少图片地址');
  const seq = String(index).padStart(3, '0');
  const rawName = (image.name || 'image').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 48);
  const filename = `商品图_${seq}_${rawName}.png`;

  // 2.1 取回原始二进制
  const resp = await fetch(image.url, { credentials: 'omit' });
  if (!resp.ok) throw new Error(`图片请求失败：HTTP ${resp.status}`);
  const blob = await resp.blob();
  if (!blob.size) throw new Error('图片内容为空');

  // 2.2 转 PNG（OffscreenCanvas 在 Service Worker 中可用）
  const { blob: pngBlob, converted } = await toPng(blob);

  // 2.3 交给 chrome.downloads 保存。
  //     Service Worker 中 URL.createObjectURL 不可用，因此使用 data URL。
  const dataUrl = await blobToDataUrl(pngBlob);
  const downloadId = await chrome.downloads.download({
    url: dataUrl,
    filename: `ImageGrab/${filename}`,
    saveAs: false,
    conflictAction: 'uniquify'
  });

  return { downloadId, filename, bytes: pngBlob.size, converted };
}

/** Blob -> PNG Blob；转换失败时退回原图，保证「下载成功」优先 */
async function toPng(blob) {
  if (blob.type === 'image/png') return { blob, converted: false };
  try {
    const bitmap = await createImageBitmap(blob);
    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(bitmap, 0, 0);
    bitmap.close();
    return { blob: await canvas.convertToBlob({ type: 'image/png' }), converted: true };
  } catch (err) {
    console.warn('[ImageGrab] PNG 转换失败，退回原图', err);
    return { blob, converted: false };
  }
}

/** Blob 转 data URL（Service Worker 中可用的替代方案） */
function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('读取图片数据失败'));
    reader.readAsDataURL(blob);
  });
}

/* ------------------------------------------------------------------ */
/* 3. 历史记录（方便用 popup 快速回到上一次结果）                       */
/* ------------------------------------------------------------------ */

async function rememberHistory(payload) {
  const { imagegrab_history: history = [] } = await chrome.storage.local.get('imagegrab_history');
  history.unshift({
    site: payload.site,
    pageUrl: payload.pageUrl,
    pageTitle: payload.pageTitle,
    count: payload.images.length,
    extractedAt: payload.extractedAt
  });
  await chrome.storage.local.set({ imagegrab_history: history.slice(0, MAX_HISTORY) });
}

/* ------------------------------------------------------------------ */
/* 4. 安装引导                                                         */
/* ------------------------------------------------------------------ */

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    chrome.tabs.create({ url: chrome.runtime.getURL('gallery.html?welcome=1') });
  }
});
