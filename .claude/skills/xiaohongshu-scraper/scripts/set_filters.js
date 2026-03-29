/**
 * ⚠️ 不推荐使用 — 2026-02 实测，此脚本在当前小红书 UI 下不可靠。
 *
 * 原因：小红书搜索页的筛选面板默认折叠（需先点击「筛选 ∨」按钮展开），
 * 且 CSS class 名称使用 CSS Modules hash，经常变化，导致 DOM 选择器匹配失败。
 * 脚本通常返回 applied 中含 "(未找到)"。
 *
 * 推荐替代方案：使用 computer tool 截图 + 坐标点击流程：
 *   1. 点击页面顶部「图文」tab
 *   2. 点击右上角「筛选 ∨」按钮（约 x=1420, y=108）展开筛选面板
 *   3. 截图确认选项位置后，逐个点击目标选项
 *   4. 点击「收起」关闭面板
 * 详见 SKILL.md「筛选功能」章节。
 *
 * ---
 *
 * set_filters.js — 设置小红书搜索页筛选条件
 *
 * 预设配置：
 *   window.__SCRAPER_CONFIG = {
 *     sort: '最多点赞',       // '综合排序' | '最多点赞' | '最新发布' | '最多评论' | '最多收藏'
 *     noteType: '图文',       // '全部类型' | '视频' | '图文'
 *     time: '一周内'          // '全部时间' | '一天内' | '一周内' | '半年内'
 *   }
 *
 * 返回：{success: true, applied: [...]} 或 {error: '...'}
 */
(() => {
  try {
    const cfg = window.__SCRAPER_CONFIG || {};
    const applied = [];

    // 找到筛选面板的容器
    const filterPanel = document.querySelector('.filter-panel, .search-filter, [class*="filter"]');

    // 方法1：通过 DOM 点击筛选按钮
    // 小红书搜索页筛选在顶部 tab 区域
    const allButtons = Array.from(document.querySelectorAll(
      '.filter-item, .search-tab, [class*="sort"], [class*="filter"] span, ' +
      '.dropdown-item, .option-item, [role="option"], [role="tab"], ' +
      'button, .reds-tab-item, .css-1d8bxgb, .css-sdu1w4'
    ));

    // 辅助函数：点击包含指定文本的元素
    function clickByText(text, elements) {
      if (!text) return false;
      for (const el of elements) {
        const elText = (el.textContent || '').trim();
        if (elText === text || elText.includes(text)) {
          el.click();
          return true;
        }
      }
      return false;
    }

    // 尝试方法2：通过下拉菜单
    // 小红书搜索页的筛选通常是下拉样式
    function openAndSelect(triggerText, optionText) {
      // 先找到触发下拉的元素
      const allClickable = Array.from(document.querySelectorAll(
        'div[class*="filter"], div[class*="sort"], div[class*="dropdown"], ' +
        'span[class*="filter"], span[class*="sort"], ' +
        '.reds-dropdown, .reds-select, [class*="select"]'
      ));

      // 也收集所有可见的 span 和 div
      const allSpans = Array.from(document.querySelectorAll('span, div'));
      const clickable = [...allClickable, ...allSpans].filter(el => {
        const text = (el.textContent || '').trim();
        return text.length < 20 && text.length > 0;
      });

      // 直接尝试点击目标选项
      if (clickByText(optionText, clickable)) {
        return true;
      }

      // 先点触发器，再点选项
      if (triggerText && clickByText(triggerText, clickable)) {
        // 等一帧让下拉展开
        return new Promise(resolve => {
          setTimeout(() => {
            const newElements = Array.from(document.querySelectorAll(
              '[class*="option"], [class*="item"], [role="option"], li, span, div'
            )).filter(el => {
              const text = (el.textContent || '').trim();
              return text === optionText;
            });
            if (newElements.length > 0) {
              newElements[0].click();
              resolve(true);
            } else {
              resolve(false);
            }
          }, 300);
        });
      }

      return false;
    }

    // 应用排序
    const sortResult = cfg.sort ? clickByText(cfg.sort, allButtons) : false;
    if (cfg.sort) {
      applied.push(cfg.sort + (sortResult ? '' : '(未找到)'));
    }

    // 应用笔记类型
    const typeResult = cfg.noteType ? clickByText(cfg.noteType, allButtons) : false;
    if (cfg.noteType) {
      applied.push(cfg.noteType + (typeResult ? '' : '(未找到)'));
    }

    // 应用时间筛选
    const timeResult = cfg.time ? clickByText(cfg.time, allButtons) : false;
    if (cfg.time) {
      applied.push(cfg.time + (timeResult ? '' : '(未找到)'));
    }

    return JSON.stringify({
      success: true,
      applied: applied,
      note: applied.some(a => a.includes('未找到'))
        ? '部分筛选未找到对应按钮，可能需要手动点击'
        : '所有筛选已应用'
    });

  } catch (e) {
    return JSON.stringify({ error: e.message, stack: e.stack });
  }
})()
