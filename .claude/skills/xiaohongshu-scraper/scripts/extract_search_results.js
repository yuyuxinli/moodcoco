/**
 * extract_search_results.js — 从 __INITIAL_STATE__ 提取搜索结果
 *
 * 预设配置：
 *   window.__SCRAPER_CONFIG = {
 *     keyword: '节后返工',    // 当前搜索关键词（用于标记）
 *     minLikes: 100           // 最低点赞数过滤（默认 0）
 *   }
 *
 * 返回：{success: true, count: N, results: [{noteId, title, likes, user, type}]}
 *       或 {error: '...'}
 */
(() => {
  try {
    const cfg = window.__SCRAPER_CONFIG || {};
    const keyword = cfg.keyword || '';
    const minLikes = cfg.minLikes || 0;

    function parseCount(s) {
      if (typeof s === 'number') return s;
      s = String(s);
      if (s.includes('万')) return Math.round(parseFloat(s) * 10000);
      if (s.includes('千')) return Math.round(parseFloat(s) * 1000);
      return parseInt(s) || 0;
    }

    // 解包 Vue reactive ref
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
      .sort((a, b) => b.likes - a.likes);

    return JSON.stringify({
      success: true,
      count: results.length,
      totalFeeds: feeds.length,
      keyword: keyword,
      results: results
    });

  } catch (e) {
    return JSON.stringify({ error: e.message, stack: e.stack });
  }
})()
