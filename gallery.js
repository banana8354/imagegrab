/**
 * 图提取 ImageGrab —— gallery.js
 * 画廊页逻辑：读取提取结果 -> 网格渲染 -> 勾选 -> 批量下载 PNG -> 进度与结果反馈
 */

const state = {
  images: [],
  selected: new Set(),
  meta: null,
  downloading: false
};

const $ = (sel) => document.querySelector(sel);
const grid = $('#grid');
const empty = $('#empty');
const counter = $('#counter');
const metaInfo = $('#metaInfo');
const checkAll = $('#checkAll');
const progress = $('#progress');
const progressFill = $('#progressFill');
const progressText = $('#progressText');
const resultBox = $('#result');

/* ------------------------------------------------------------------ */
/* 1. 载入数据                                                         */
/* ------------------------------------------------------------------ */

async function load() {
  const params = new URLSearchParams(location.search);
  const resp = await chrome.runtime.sendMessage({ type: 'GET_PAYLOAD' });
  const payload = resp?.payload;

  if (!payload || !payload.images?.length) {
    empty.hidden = false;
    metaInfo.textContent = params.get('welcome') ? '欢迎使用，请先在商品详情页提取图片' : '暂无数据';
    return;
  }

  state.meta = payload;
  state.images = payload.images;
  state.selected = new Set(payload.images.map((img) => img.id)); // 默认全选

  const platform = payload.site || '电商平台';
  const time = new Date(payload.extractedAt || Date.now()).toLocaleString('zh-CN', { hour12: false });
  metaInfo.textContent = `${platform} · ${payload.images.length} 张图片 · ${time}`;
  metaInfo.title = payload.pageUrl || '';

  render();
}

/* ------------------------------------------------------------------ */
/* 2. 渲染网格                                                         */
/* ------------------------------------------------------------------ */

function render() {
  grid.innerHTML = '';
  const frag = document.createDocumentFragment();

  state.images.forEach((img, idx) => {
    const card = document.createElement('figure');
    card.className = 'card';
    card.dataset.id = img.id;
    card.classList.toggle('is-selected', state.selected.has(img.id));

    // 用 CSS 变量占位，图片加载完成后淡入
    card.innerHTML = `
      <label class="card__check">
        <input type="checkbox" ${state.selected.has(img.id) ? 'checked' : ''} data-id="${img.id}"
               aria-label="选择第 ${idx + 1} 张图片">
      </label>
      <div class="card__thumb">
        <img src="${img.url}" alt="商品图 ${idx + 1}" loading="lazy" decoding="async">
        <span class="card__badge">${idx + 1}</span>
      </div>
      <figcaption class="card__meta">
        <span class="card__size">${img.width || '?'} × ${img.height || '?'}</span>
        <span class="card__source" title="${img.source}">${img.source}</span>
      </figcaption>
      <button class="card__dl" type="button" title="只下载这一张" data-dl="${img.id}">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3v12"></path><path d="M7 11l5 5 5-5"></path><path d="M5 21h14"></path>
        </svg>
      </button>
    `;

    const image = card.querySelector('img');
    image.addEventListener('load', () => card.classList.add('is-loaded'));
    image.addEventListener('error', () => {
      card.classList.add('is-error');
      image.replaceWith(Object.assign(document.createElement('div'), {
        className: 'card__broken',
        textContent: '图片无法预览（可尝试直接下载）'
      }));
    });

    frag.appendChild(card);
  });

  grid.appendChild(frag);
  updateCounter();
}

function updateCounter() {
  counter.textContent = `已选 ${state.selected.size} / ${state.images.length}`;
  checkAll.checked = state.images.length > 0 && state.selected.size === state.images.length;
  checkAll.indeterminate = state.selected.size > 0 && state.selected.size < state.images.length;
  $('#btnDownload').disabled = state.selected.size === 0 || state.downloading;
}

function setSelected(id, on) {
  if (on) state.selected.add(id); else state.selected.delete(id);
  const card = grid.querySelector(`.card[data-id="${id}"]`);
  if (card) {
    card.classList.toggle('is-selected', on);
    const box = card.querySelector('input[type="checkbox"]');
    if (box) box.checked = on;
  }
  updateCounter();
}

/* ------------------------------------------------------------------ */
/* 3. 事件绑定                                                         */
/* ------------------------------------------------------------------ */

grid.addEventListener('change', (e) => {
  const box = e.target.closest('input[type="checkbox"]');
  if (box) setSelected(box.dataset.id, box.checked);
});

grid.addEventListener('click', async (e) => {
  const dl = e.target.closest('[data-dl]');
  if (dl) {
    e.preventDefault();
    e.stopPropagation();
    const img = state.images.find((i) => i.id === dl.dataset.dl);
    if (!img) return;
    dl.classList.add('is-loading');
    const resp = await chrome.runtime.sendMessage({ type: 'DOWNLOAD_ONE', image: img, index: 1 });
    dl.classList.remove('is-loading');
    showResult(resp?.ok
      ? [{ ok: true, filename: resp.result.filename }]
      : [{ ok: false, error: resp?.error || '下载失败' }]);
  }
});

// 点击缩略图切换选中状态，操作更顺手
grid.addEventListener('click', (e) => {
  const thumb = e.target.closest('.card__thumb');
  if (!thumb) return;
  const card = thumb.closest('.card');
  const id = card.dataset.id;
  setSelected(id, !state.selected.has(id));
});

checkAll.addEventListener('change', () => {
  const on = checkAll.checked;
  state.images.forEach((img) => {
    if (on) state.selected.add(img.id); else state.selected.delete(img.id);
  });
  render();
});

$('#btnInvert').addEventListener('click', () => {
  const next = new Set();
  state.images.forEach((img) => { if (!state.selected.has(img.id)) next.add(img.id); });
  state.selected = next;
  render();
});

$('#btnReload').addEventListener('click', async () => {
  // 重新触发当前商品页的提取：切回来源标签页并发送消息
  const tabId = state.meta?.tabId;
  if (tabId == null) {
    location.reload();
    return;
  }
  try {
    await chrome.tabs.update(tabId, { active: true });
    await chrome.tabs.sendMessage(tabId, { type: 'EXTRACT_NOW' });
  } catch (err) {
    alert('无法重新提取：来源页面已关闭或未注入脚本。');
  }
});

$('#btnDownload').addEventListener('click', async () => {
  const list = state.images.filter((img) => state.selected.has(img.id));
  if (!list.length) return;
  state.downloading = true;
  updateCounter();
  showProgress(0, list.length);

  const resp = await chrome.runtime.sendMessage({ type: 'DOWNLOAD_MANY', images: list });
  state.downloading = false;
  updateCounter();
  hideProgress();

  const results = resp?.results || [];
  showResult(results);

  // 下载完成后保留选择，方便用户继续挑图
});

/* ------------------------------------------------------------------ */
/* 4. 进度与结果反馈                                                   */
/* ------------------------------------------------------------------ */

// Service Worker 推送的实时进度
chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.type === 'DOWNLOAD_PROGRESS') {
    showProgress(msg.done, msg.total);
  }
});

function showProgress(done, total) {
  progress.hidden = false;
  const pct = total ? Math.round((done / total) * 100) : 0;
  progressFill.style.width = `${pct}%`;
  progressText.textContent = `正在下载 ${done} / ${total}（${pct}%）`;
}

function hideProgress() {
  progressFill.style.width = '100%';
  setTimeout(() => { progress.hidden = true; progressFill.style.width = '0%'; }, 700);
}

let resultTimer = null;
function showResult(results) {
  const okCount = results.filter((r) => r.ok).length;
  const failCount = results.length - okCount;
  const head = failCount === 0
    ? `✅ 下载完成：成功 ${okCount} 张 PNG`
    : `⚠️ 下载结束：成功 ${okCount} 张，失败 ${failCount} 张`;
  const detail = results.slice(0, 6).map((r) => (r.ok
    ? `<li>${r.filename || '已保存'}</li>`
    : `<li class="is-fail">失败：${r.error}</li>`)).join('');

  resultBox.hidden = false;
  resultBox.innerHTML = `
    <strong>${head}</strong>
    <ul>${detail}</ul>
    ${results.length > 6 ? `<span class="result__more">…共 ${results.length} 个文件，其余已略去</span>` : ''}
    <button class="result__close" type="button" aria-label="关闭">×</button>
  `;
  resultBox.querySelector('.result__close').addEventListener('click', () => { resultBox.hidden = true; });
  clearTimeout(resultTimer);
  resultTimer = setTimeout(() => { resultBox.hidden = true; }, 8000);
}

load();
