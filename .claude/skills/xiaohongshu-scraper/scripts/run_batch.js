/**
 * run_batch.js — 批量提取搜索结果并存入 window 变量
 *
 * 预设配置：
 *   window.__SCRAPER_CONFIG = {
 *     keyword: '节后返工',    // 当前搜索关键词
 *     minLikes: 100,          // 最低点赞数（默认 0）
 *     maxPosts: 20            // 最多提取数（默认 20）
 *   }
 *
 * 输出：
 *   window.__SCRAPER_RESULTS = { keyword, results: [...], timestamp }
 *
 * 返回：结果摘要 {success, count, topLikes, keyword}
 *
 * 注意：此脚本只处理搜索结果（Phase 1），
 *       帖子详情需要逐个点击，由调用方循环执行 open_post.js + extract_post_detail.js
 */
(() => {
  try {
    const cfg = window.__SCRAPER_CONFIG || {};
    const keyword = cfg.keyword || '';
    const minLikes = cfg.minLikes || 0;
    const maxPosts = cfg.maxPosts || 20;

    function parseCount(s) {
      if (typeof s === 'number') return s;
      s = String(s);
      if (s.includes('万')) return Math.round(parseFloat(s) * 10000);
      if (s.includes('千')) return Math.round(parseFloat(s) * 1000);
      return parseInt(s) || 0;
    }

    function unwrap(obj) {
      for (let i = 0; i < 5; i++) {
        if (obj && obj._rawValue !== undefined) obj = obj._rawValue;
        else if (obj && obj._value !== undefined) obj = obj._value;
      }
      return obj;
    }

    const state = window.__INITIAL_STATE__;
    if (!state) return JSON.stringify({ error: '__INITIAL_STATE__ 不存在' });

    let feeds = unwrap(state?.search?.feeds);
    if (!Array.isArray(feeds)) {
      return JSON.stringify({ error: 'feeds 不是数组', type: typeof feeds });
    }

    const results = feeds
      .filter(f => f.modelType === 'note' || f.model_type === 'note')
      .map(f => {
        const nc = f.noteCard || f.note_card || {};
        const likes = parseCount(nc.interactInfo?.likedCount || nc.interact_info?.liked_count || 0);
        return {
          noteId: f.id,
          title: (nc.displayTitle || nc.display_title || '').slice(0, 80),
          type: nc.type || 'normal',
          likes: likes,
          user: nc.user?.nickName || nc.user?.nickname || nc.user?.nick_name || '',
          keyword: keyword
        };
      })
      .filter(r => r.likes >= minLikes)
      .sort((a, b) => b.likes - a.likes)
      .slice(0, maxPosts);

    // 存入 window 变量供后续使用
    window.__SCRAPER_RESULTS = {
      keyword: keyword,
      results: results,
      timestamp: Date.now()
    };

    return JSON.stringify({
      success: true,
      count: results.length,
      keyword: keyword,
      topLikes: results.length > 0 ? results[0].likes : 0,
      topTitle: results.length > 0 ? results[0].title : '',
      preview: results.slice(0, 3).map(r => `${r.title} (${r.likes}赞)`),
      note: '结果已存入 window.__SCRAPER_RESULTS，可逐个执行 open_post.js + extract_post_detail.js 提取详情'
    });

  } catch (e) {
    return JSON.stringify({ error: e.message, stack: e.stack });
  }
})()
