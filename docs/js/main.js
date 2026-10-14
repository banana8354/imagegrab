/**
 * 图提取 ImageGrab 官网 —— 交互脚本
 * 功能：
 *   1. 移动端汉堡菜单展开 / 收起；
 *   2. 导航栏滚动吸顶样式与当前区块高亮；
 *   3. IntersectionObserver 实现滚动进入视口的淡入上移动画；
 *   4. 平滑锚点跳转（避开被固定导航栏遮挡）；
 *   5. 页脚年份自动更新。
 */
(() => {
  'use strict';

  const navbar = document.getElementById('navbar');
  const navMenu = document.getElementById('navMenu');
  const hamburger = document.getElementById('hamburger');
  const navLinks = [...document.querySelectorAll('.nav__link')];

  /* ---------------------------------------------------------------- */
  /* 1. 移动端菜单                                                     */
  /* ---------------------------------------------------------------- */

  function closeMenu() {
    navMenu.classList.remove('is-open');
    hamburger.setAttribute('aria-expanded', 'false');
    hamburger.setAttribute('aria-label', '打开菜单');
  }

  hamburger.addEventListener('click', () => {
    const open = navMenu.classList.toggle('is-open');
    hamburger.setAttribute('aria-expanded', String(open));
    hamburger.setAttribute('aria-label', open ? '关闭菜单' : '打开菜单');
  });

  // 点击菜单项后自动收起
  navMenu.addEventListener('click', (e) => {
    if (e.target.closest('a')) closeMenu();
  });

  // 点击菜单外部或按 Esc 关闭
  document.addEventListener('click', (e) => {
    if (!navMenu.classList.contains('is-open')) return;
    if (e.target.closest('#navMenu') || e.target.closest('#hamburger')) return;
    closeMenu();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenu();
  });

  /* ---------------------------------------------------------------- */
  /* 2. 平滑锚点跳转（补偿固定导航栏高度）                              */
  /* ---------------------------------------------------------------- */

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener('click', (e) => {
      const id = link.getAttribute('href');
      if (!id || id === '#') return;
      const target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      const top = target.getBoundingClientRect().top + window.scrollY - 72;
      window.scrollTo({ top, behavior: 'smooth' });
      history.replaceState(null, '', id);
    });
  });

  /* ---------------------------------------------------------------- */
  /* 3. 滚动：导航栏样式 + 当前区块高亮                                 */
  /* ---------------------------------------------------------------- */

  const sections = navLinks
    .map((l) => document.querySelector(l.getAttribute('href')))
    .filter(Boolean);

  let ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      // 3.1 吸顶样式
      navbar.classList.toggle('is-scrolled', window.scrollY > 12);

      // 3.2 高亮当前区块（取最后一个已滚过顶部 1/3 屏幕的区块）
      const line = window.scrollY + window.innerHeight * 0.32;
      let current = null;
      for (const sec of sections) {
        if (sec.offsetTop <= line) current = sec.id;
      }
      navLinks.forEach((link) => {
        link.classList.toggle('is-active', link.getAttribute('href') === `#${current}`);
      });

      ticking = false;
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------------------------------------------------------------- */
  /* 4. 滚动进入视口的淡入上移动画                                      */
  /* ---------------------------------------------------------------- */

  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    // 同一组的元素依次延迟出现，形成错落的节奏感
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const siblings = [...(entry.target.parentElement?.children || [])];
        const idx = Math.max(0, siblings.indexOf(entry.target));
        entry.target.style.transitionDelay = `${Math.min(idx, 5) * 70}ms`;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -60px 0px' });
    reveals.forEach((el) => observer.observe(el));
  } else {
    // 老浏览器兜底：直接显示
    reveals.forEach((el) => el.classList.add('is-visible'));
  }

  /* ---------------------------------------------------------------- */
  /* 5. 其它                                                           */
  /* ---------------------------------------------------------------- */

  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  console.log('%c图提取 ImageGrab%c 官网已加载 ✓', 'color:#4f6bff;font-weight:700', 'color:#8a93a8');
})();
