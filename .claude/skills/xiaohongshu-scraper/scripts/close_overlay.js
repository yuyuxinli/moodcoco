/**
 * close_overlay.js — 关闭帖子弹窗/详情浮层
 *
 * 逻辑：依次尝试多种关闭方式
 * 返回：{success: true, method: '...'} 或 {error: '...'}
 */
(() => {
  try {
    // 策略1：点击关闭按钮
    const closeSelectors = [
      '.close-circle', '.close-btn', '[class*="close"]',
      '.reds-icon-close', 'svg.close', '[aria-label="close"]',
      '[aria-label="关闭"]', '.note-detail-mask'
    ];

    for (const sel of closeSelectors) {
      const el = document.querySelector(sel);
      if (el) {
        el.click();
        return JSON.stringify({ success: true, method: 'click:' + sel });
      }
    }

    // 策略2：按 Escape 键
    document.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true
    }));
    document.dispatchEvent(new KeyboardEvent('keyup', {
      key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true
    }));

    // 策略3：history.back()
    // 不在这里调用，因为可能导致离开搜索页
    // 留给调用方决定是否 navigate back

    return JSON.stringify({
      success: true,
      method: 'escape',
      note: '已发送 Escape 键事件。如弹窗未关闭，请使用 navigate back'
    });

  } catch (e) {
    return JSON.stringify({ error: e.message, stack: e.stack });
  }
})()
