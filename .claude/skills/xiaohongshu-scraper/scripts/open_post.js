/**
 * open_post.js — 在搜索页中点击指定帖子，触发 Vue 路由导航到详情页
 *
 * 预设配置：
 *   window.__SCRAPER_TARGET = { noteId: 'xxx' }
 *
 * 原理：
 *   找到 section 内的 <a class="cover"> 元素，派发完整鼠标事件序列
 *   (mousedown → mouseup → click)，触发 Vue Router 导航。
 *
 *   ⚠️ 不能用 el.click()（会触发 <a> href 整页导航而非 Vue 路由）
 *   ⚠️ 不能用 computer tool 坐标点击（坐标可能超出视口、不稳定）
 *   ✅ 在 cover <a> 上派发 MouseEvent 序列 = 最可靠方案
 *
 * 返回：{success: true, noteId} 或 {error: '...'}
 *
 * 调用方接下来只需等待 3 秒，然后执行 extract_post_detail.js
 */
(() => {
  try {
    const target = window.__SCRAPER_TARGET || {};
    const noteId = target.noteId;

    if (!noteId) {
      return JSON.stringify({ error: '未设置 __SCRAPER_TARGET.noteId' });
    }

    // 找包含 noteId 的 <a> 链接
    const links = Array.from(document.querySelectorAll('a[href*="' + noteId + '"]'));
    if (links.length === 0) {
      return JSON.stringify({ error: '未找到链接', noteId: noteId });
    }

    // 找到最近的 section 容器
    const link = links[0];
    const section = link.closest('section') || link.parentElement?.parentElement?.parentElement;

    // 优先找 cover <a>（class 含 "cover"），其次用找到的 link
    const cover = section ? (section.querySelector('a.cover') || section.querySelector('.cover') || link) : link;

    // 滚动到视口中央
    cover.scrollIntoView({ behavior: 'instant', block: 'center' });

    // 派发完整鼠标事件序列（模拟真实鼠标点击）
    const rect = cover.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const eventOpts = {
      bubbles: true, cancelable: true, view: window,
      clientX: cx, clientY: cy, button: 0
    };

    cover.dispatchEvent(new MouseEvent('mousedown', eventOpts));
    cover.dispatchEvent(new MouseEvent('mouseup', eventOpts));
    cover.dispatchEvent(new MouseEvent('click', eventOpts));

    return JSON.stringify({
      success: true,
      noteId: noteId,
      tag: cover.tagName,
      className: (cover.className || '').slice(0, 60)
    });

  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
})()
