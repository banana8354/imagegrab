/**
 * 图提取 ImageGrab —— 内容脚本（content.js）
 * 职责：
 *   1. 判断当前页面是否为受支持的电商商品详情页；
 *   2. 在页面右下角注入悬浮按钮「获取图片」；
 *   3. 扫描页面中所有商品图片（img / srcset / data-* 懒加载 / 背景图）；
 *   4. 过滤图标、logo、占位图、过小的图片，补全相对路径并去重；
 *   5. 把结果通过 chrome.runtime.sendMessage 交给 Service Worker。
 */
(() => {
  'use strict';

  /** 避免在 iframe 或重复注入时出现多个按钮 */
  if (window.__IMAGE_GRAB_INJECTED__) return;
  window.__IMAGE_GRAB_INJECTED__ = true;

  const MIN_SIZE = 100;          // 小于 100x100 的图片视为图标，直接过滤
  const MIN_FILE_SIZE = 3 * 1024; // 小于 3KB 的图片视为占位图

  /* ------------------------------------------------------------------ */
  /* 1. 页面识别                                                         */
  /* ------------------------------------------------------------------ */

  /**
   * 简单的站点识别：不追求 100% 精确，只区分「详情页」与「列表页/首页」，
   * 列表页同样允许提取（用户可能想批量下载主图），但会给出提示。
   */
  function detectSite() {
    const host = location.hostname;
    if (/taobao\.com$/.test(host)) return '淘宝';
    if (/tmall\.com$/.test(host)) return '天猫';
    if (/jd\.com$/.test(host)) return '京东';
    if (/pinduoduo\.com$/.test(host) || /yangkeduo\.com$/.test(host)) return '拼多多商家版';
    return '未知平台';
  }

  function isDetailPage() {
    const url = location.href;
    return (
      /item\.taobao\.com|detail\.tmall\.com|item\.jd\.com|mobile\.yangkeduo\.com\/goods|mobile\.pinduoduo\.com\/goods|.\/goods\.html/.test(url) ||
      !!document.querySelector('[class*="detail"],[id*="detail"],[class*="gallery"],[id*="gallery"]')
    );
  }

  /* ------------------------------------------------------------------ */
  /* 2. 注入悬浮按钮                                                     */
  /* ------------------------------------------------------------------ */

  const btn = document.createElement('button');
  btn.id = 'imagegrab-fab';
  btn.type = 'button';
  btn.setAttribute('aria-label', '获取图片');
  btn.innerHTML = `
    <span class="imagegrab-fab__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="3"></rect>
        <circle cx="8.5" cy="8.5" r="1.5"></circle>
        <path d="M21 15l-5-5L5 21"></path>
      </svg>
    </span>
    <span class="imagegrab-fab__text">获取图片</span>
    <span class="imagegrab-fab__badge" hidden>0</span>
  `;

  /** 页面右下角可能已有平台自己的悬浮客服按钮，做一次向上避让 */
  function avoidOverlap() {
    const occupied = ['#J_TabBar', '.tb-seller-mobile', '#J_imContainer', '.pdd-kefu', '.jd-kefu'];
    let offset = 0;
    for (const sel of occupied) {
      const el = document.querySelector(sel);
      if (el) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && rect.bottom > window.innerHeight * 0.7) {
          offset = Math.max(offset, window.innerHeight - rect.top);
        }
      }
    }
    btn.style.setProperty('--imagegrab-offset', `${Math.min(offset, 180)}px`);
  }

  document.documentElement.appendChild(btn);
  avoidOverlap();

  const badge = btn.querySelector('.imagegrab-fab__badge');

  function setBusy(busy, text) {
    btn.classList.toggle('is-busy', busy);
    btn.disabled = busy;
    if (text) btn.querySelector('.imagegrab-fab__text').textContent = text;
  }

  /* ------------------------------------------------------------------ */
  /* 3. 图片收集                                                         */
  /* ------------------------------------------------------------------ */

  /** 把可能的懒加载属性名集中起来，方便兼容不同平台 */
  const LAZY_ATTRS = [
    'src', 'data-src', 'data-ks-lazyload', 'data-lazy-src', 'data-lazyload',
    'data-original', 'data-image', 'data-img', 'data-url', 'data-spm-src',
    'data-pin', 'lazy-src', 'data-lazyload-src', 'data-srcset'
  ];

  /** 判断字符串看起来像图片地址 */
  function looksLikeImage(url) {
    if (!url || typeof url !== 'string') return false;
    const u = url.trim();
    if (!u || u.startsWith('data:image/svg') || u.startsWith('blob:')) return false;
    if (u.startsWith('data:image/')) return true;
    return /\.(png|jpe?g|webp|gif|bmp|avif|tiff?)(\?|#|$)/i.test(u) ||
      /(alicdn|360buyimg|jd\.com|pinduoduo|yangkeduo|taobaocdn|tbcdn|img\.alicdn)/i.test(u) && /^https?:/i.test(u);
  }

  /** 补全相对路径 -> 绝对 URL */
  function toAbsolute(url) {
    try {
      return new URL(url, location.href).href;
    } catch {
      return null;
    }
  }

  /** 从 srcset 字符串中挑出分辨率最大的那一张 */
  function pickLargestFromSrcset(srcset) {
    if (!srcset) return null;
    const parts = String(srcset).split(',').map((s) => s.trim()).filter(Boolean);
    let best = null;
    let bestScore = -1;
    for (const part of parts) {
      const [url, descriptor] = part.split(/\s+/);
      if (!url) continue;
      let score = 1;
      if (descriptor) {
        const m = descriptor.match(/^([\d.]+)(w|x)$/);
        if (m) score = parseFloat(m[1]) * (m[2] === 'x' ? 1000 : 1);
      }
      if (score > bestScore) {
        bestScore = score;
        best = url;
      }
    }
    return best;
  }

  /** 从 CSS background-image 中取出 URL（可能有多层） */
  function urlsFromBackground(value) {
    if (!value || value === 'none') return [];
    return [...value.matchAll(/url\((['"]?)(.*?)\1\)/g)].map((m) => m[2]).filter(Boolean);
  }

  /**
   * 扫描整个页面，返回候选图片列表。
   * 同时从 DOM 元素与 CSS 规则（含伪元素常见写法）两个来源收集。
   */
  function collectCandidates() {
    /** @type {Map<string, {url:string, width:number, height:number, source:string, el?:Element}>} */
    const map = new Map();

    const add = (rawUrl, source, el) => {
      if (!looksLikeImage(rawUrl)) return;
      const abs = toAbsolute(rawUrl);
      if (!abs) return;
      // 去掉明显的缩略图后缀（阿里 CDN 常见的 _50x50.jpg / _q75.jpg）
      const normalized = abs.replace(/_\d+x\d+(xz)?\.(jpg|jpeg|png|webp)/i, '');
      const rect = el && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
      const width = Math.round(rect?.width || 0) ||
        Number(el?.naturalWidth || 0) || Number(el?.width || 0) || 0;
      const height = Math.round(rect?.height || 0) ||
        Number(el?.naturalHeight || 0) || Number(el?.height || 0) || 0;
      const prev = map.get(normalized);
      if (!prev) {
        map.set(normalized, { url: normalized, width, height, source, el });
      } else {
        // 同一个 URL 出现多次时，保留信息更全的一条
        if (!prev.width && width) prev.width = width;
        if (!prev.height && height) prev.height = height;
        if (prev.source === 'css' && source !== 'css') prev.source = source;
      }
    };

    // 3.1 <img> 标签及其全部懒加载属性
    document.querySelectorAll('img').forEach((img) => {
      for (const attr of LAZY_ATTRS) {
        const v = img.getAttribute(attr);
        if (!v) continue;
        if (attr === 'srcset' || attr === 'data-srcset') {
          const best = pickLargestFromSrcset(v);
          if (best) add(best, `img[${attr}]`, img);
          continue;
        }
        // data-srcset 之类可能存了多张，用逗号切分
        if (v.includes(',') && /https?:/.test(v)) {
          v.split(',').forEach((one) => add(one.trim().split(/\s+/)[0], `img[${attr}]`, img));
        } else {
          add(v, `img[${attr}]`, img);
        }
      }
      // currentSrc 是浏览器实际加载的那张，优先级最高
      if (img.currentSrc) add(img.currentSrc, 'img.currentSrc', img);
    });

    // 3.2 <source> / <picture>
    document.querySelectorAll('source[srcset], source[data-srcset]').forEach((s) => {
      const best = pickLargestFromSrcset(s.getAttribute('srcset') || s.getAttribute('data-srcset'));
      if (best) add(best, 'source[srcset]', s);
    });

    // 3.3 内联 style 与 CSS background-image
    document.querySelectorAll('[style*="background"]').forEach((el) => {
      urlsFromBackground(el.style.backgroundImage).forEach((u) => add(u, 'inline-css', el));
    });

    // 3.4 <a href> 指向图片的链接（有些详情页大图只在链接里）
    document.querySelectorAll('a[href]').forEach((a) => {
      const href = a.getAttribute('href');
      if (href && /\.(png|jpe?g|webp|gif|avif)(\?|#|$)/i.test(href)) add(href, 'a[href]', a);
    });

    // 3.5 遍历样式表规则，找出选择器命中的元素上的背景图
    for (const sheet of Array.from(document.styleSheets)) {
      let rules;
      try {
        rules = sheet.cssRules; // 跨域样式表会抛异常，忽略即可
      } catch {
        continue;
      }
      if (!rules) continue;
      for (const rule of Array.from(rules)) {
        if (!rule.style || !rule.selectorText) continue;
        const bg = rule.style.backgroundImage || rule.style.getPropertyValue('background-image');
        const urls = urlsFromBackground(bg);
        if (!urls.length) continue;
        try {
          document.querySelectorAll(rule.selectorText).forEach((el) => {
            urls.forEach((u) => add(u, 'css', el));
          });
        } catch {
          /* 选择器不被支持时跳过 */
        }
      }
    }

    // 3.6 兜底：页面里出现过的、写在脚本字符串中的图片地址
    const html = document.documentElement.innerHTML;
    const re = /https?:\/\/[^\s"'<>\\]+?\.(?:png|jpe?g|webp|gif|avif)(?:\?[^\s"'<>\\]*)?/gi;
    const found = html.match(re) || [];
    found.slice(0, 400).forEach((u) => add(u, 'inline-script', null));

    return [...map.values()];
  }

  /**
   * 过滤：去掉图标、logo、占位图、1x1 像素图、过小的图。
   * 对于拿不到尺寸的图片保留（交给画廊页按需验证），避免误杀大图。
   */
  function filterCandidates(list) {
    const IGNORE_WORDS = /(logo|icon|sprite|avatar|qrcode|erweima|placeholder|blank|loading|spacer|pixel|btn_|bg_|arrow|share_)/i;
    return list.filter((item) => {
      if (IGNORE_WORDS.test(item.url)) return false;
      // 1x1 或极小尺寸
      if (item.width && item.height && (item.width < MIN_SIZE || item.height < MIN_SIZE)) return false;
      if (item.width === 1 || item.height === 1) return false;
      // 头像类 URL 参数
      if (/[?&](wh|size)=\d{1,2}(_\d{1,2})?/i.test(item.url)) return false;
      return true;
    });
  }

  /** 用 canvas 二次校验图片真实尺寸与文件体积，过滤掉伪装成商品图的小图 */
  async function verifyByImage(list, limit = 60) {
    const sample = list.slice(0, limit);
    const rest = list.slice(limit);
    const results = await Promise.all(sample.map((item) => new Promise((resolve) => {
      if (item.width >= MIN_SIZE && item.height >= MIN_SIZE) return resolve(item);
      const probe = new Image();
      probe.crossOrigin = 'anonymous';
      const timer = setTimeout(() => resolve(null), 6000);
      probe.onload = () => {
        clearTimeout(timer);
        if (probe.naturalWidth < MIN_SIZE || probe.naturalHeight < MIN_SIZE) return resolve(null);
        item.width = probe.naturalWidth;
        item.height = probe.naturalHeight;
        resolve(item);
      };
      probe.onerror = () => {
        clearTimeout(timer);
        resolve(null);
      };
      probe.src = item.url;
    })));
    return [...results.filter(Boolean), ...rest];
  }

  /* ------------------------------------------------------------------ */
  /* 4. 主流程                                                           */
  /* ------------------------------------------------------------------ */

  async function runExtract() {
    setBusy(true, '提取中');
    try {
      const site = detectSite();
      if (!isDetailPage()) {
        toast('当前可能不是商品详情页，仍将继续扫描页面图片', 'warn');
      }

      // 先把懒加载图片「骗」出来：滚动一遍页面，触发平台自己的懒加载
      await autoScroll();

      const raw = collectCandidates();
      const filtered = filterCandidates(raw);
      const verified = await verifyByImage(filtered);

      // 按面积从大到小排序，商品主图排在最前面
      verified.sort((a, b) => (b.width * b.height) - (a.width * a.height));

      const payload = {
        site,
        pageUrl: location.href,
        pageTitle: document.title,
        extractedAt: Date.now(),
        images: verified.map((it, idx) => ({
          id: `img_${idx + 1}`,
          url: it.url,
          width: it.width,
          height: it.height,
          source: it.source,
          name: guessName(it.url, idx + 1)
        }))
      };

      if (!payload.images.length) {
        toast('没有找到符合条件的图片，请确认已滚动到详情页图片区域', 'warn');
        return;
      }

      badge.hidden = false;
      badge.textContent = String(payload.images.length);

      // 交给 Service Worker，由它打开画廊页
      const resp = await chrome.runtime.sendMessage({ type: 'EXTRACT_DONE', payload });
      if (resp?.ok) {
        toast(`已提取 ${payload.images.length} 张图片，正在打开预览页`, 'ok');
      } else {
        toast('打开预览页失败，请在扩展页面的画廊中重试', 'warn');
      }
    } catch (err) {
      console.error('[ImageGrab] 提取失败', err);
      toast(`提取失败：${err.message}`, 'warn');
    } finally {
      setBusy(false, '获取图片');
    }
  }

  /** 从 URL 里猜一个可读的文件名 */
  function guessName(url, idx) {
    try {
      const path = new URL(url).pathname;
      const base = decodeURIComponent(path.split('/').pop() || '');
      const noExt = base.replace(/\.[a-z0-9]+$/i, '').slice(0, 40);
      return noExt || `image_${idx}`;
    } catch {
      return `image_${idx}`;
    }
  }

  /** 滚动整页，触发懒加载图片进入视口 */
  function autoScroll() {
    return new Promise((resolve) => {
      const step = Math.round(window.innerHeight * 0.9);
      let y = 0;
      let ticks = 0;
      const timer = setInterval(() => {
        y += step;
        window.scrollTo({ top: y, behavior: 'instant' in window ? 'instant' : 'auto' });
        ticks += 1;
        if (y >= document.body.scrollHeight - window.innerHeight || ticks > 40) {
          clearInterval(timer);
          window.scrollTo({ top: 0, behavior: 'auto' });
          setTimeout(resolve, 600); // 给图片加载留一点时间
        }
      }, 180);
    });
  }

  /** 轻量 toast 提示 */
  let toastTimer = null;
  function toast(text, kind = 'ok') {
    let el = document.getElementById('imagegrab-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'imagegrab-toast';
      document.documentElement.appendChild(el);
    }
    el.className = `imagegrab-toast imagegrab-toast--${kind} is-show`;
    el.textContent = text;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('is-show'), 3600);
  }

  /** 点击按钮触发提取 */
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    runExtract();
  });

  /** 支持来自 popup 的主动触发 */
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === 'EXTRACT_NOW') {
      runExtract();
      sendResponse({ ok: true });
    }
    if (msg?.type === 'PING') {
      sendResponse({ ok: true, site: detectSite() });
    }
    return true;
  });

  console.log(`[ImageGrab] 已注入，当前平台：${detectSite()}`);
})();
