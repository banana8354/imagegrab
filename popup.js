/**
 * 图提取 ImageGrab —— popup.js
 * 弹窗逻辑：识别当前标签页平台、触发提取、查看最近记录
 */

const SUPPORTED = /(taobao|tmall|jd|pinduoduo|yangkeduo)\.com$/;

const $ = (s) => document.querySelector(s);

/** 判断 host 属于哪个平台 */
function platformOf(host) {
  if (/taobao\.com$/.test(host)) return '淘宝';
  if (/tmall\.com$/.test(host)) return '天猫';
  if (/jd\.com$/.test(host)) return '京东';
  if (/(pinduoduo|yangkeduo)\.com$/.test(host)) return '拼多多商家版';
  return null;
}

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  let host = '';
  try { host = new URL(tab.url).hostname; } catch { /* 忽略 */ }

  const platform = platformOf(host);
  const siteInfo = $('#siteInfo');
  const btnExtract = $('#btnExtract');

  if (platform) {
    siteInfo.textContent = `已识别：${platform} 商品页`;
    siteInfo.classList.add('is-ok');
  } else {
    siteInfo.textContent = host ? `当前页面（${host}）不在支持列表内` : '请先打开商品详情页';
    siteInfo.classList.add('is-warn');
    btnExtract.disabled = true;
    btnExtract.textContent = '仅支持淘宝 / 京东 / 拼多多商家版';
  }

  btnExtract.addEventListener('click', async () => {
    if (!platform) return;
    btnExtract.disabled = true;
    btnExtract.textContent = '正在提取…';
    try {
      await chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT_NOW' });
      window.close(); // 提取后画廊页会自动打开
    } catch (err) {
      btnExtract.textContent = '提取失败，请刷新商品页重试';
    }
  });

  $('#btnGallery').addEventListener('click', async () => {
    await chrome.runtime.sendMessage({ type: 'OPEN_GALLERY' });
    window.close();
  });

  renderHistory();
}

async function renderHistory() {
  const resp = await chrome.runtime.sendMessage({ type: 'GET_HISTORY' });
  const history = resp?.history || [];
  const ul = $('#history');
  if (!history.length) {
    ul.innerHTML = '<li class="pop-empty">暂无记录</li>';
    return;
  }
  ul.innerHTML = history.map((h) => `
    <li>
      <span class="pop-history__site">${h.site}</span>
      <span class="pop-history__count">${h.count} 张</span>
      <time>${new Date(h.extractedAt).toLocaleString('zh-CN', { hour12: false })}</time>
    </li>
  `).join('');
}

init();
