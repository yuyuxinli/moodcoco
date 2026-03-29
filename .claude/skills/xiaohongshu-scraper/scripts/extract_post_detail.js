/**
 * extract_post_detail.js — 从弹窗/详情页提取帖子完整数据
 *
 * 无需预设配置，自动从 URL 获取 noteId
 *
 * 返回：{success: true, data: {...}} 或 {error: '...'}
 */
(() => {
  try {
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

    // 从 URL 获取 noteId（⚠️ 必须用 URL 中的，不能用 keys[0]）
    const urlPath = location.pathname + location.search + location.hash;
    // 匹配模式：/explore/noteId 或 /search_result/noteId 或 ?noteId=xxx 或 弹窗 URL
    let nid = '';

    // 尝试从 hash 中获取（弹窗模式下 URL 可能是 /search_result?...#/explore/noteId）
    const hashMatch = location.hash.match(/\/explore\/([a-f0-9]+)/);
    if (hashMatch) {
      nid = hashMatch[1];
    }

    // 尝试从 pathname 获取
    if (!nid) {
      const pathMatch = location.pathname.match(/\/explore\/([a-f0-9]+)/);
      if (pathMatch) nid = pathMatch[1];
    }

    // 尝试从 search params 获取
    if (!nid) {
      const params = new URLSearchParams(location.search);
      nid = params.get('noteId') || params.get('note_id') || '';
    }

    // 最后手段：遍历 noteDetailMap 找最近添加的
    let dm = unwrap(state?.note?.noteDetailMap);
    if (!dm || typeof dm !== 'object') {
      return JSON.stringify({ error: 'noteDetailMap 不存在或非对象' });
    }

    const dmKeys = Object.keys(dm);
    if (!nid && dmKeys.length === 1) {
      nid = dmKeys[0];
    }

    // 如果还没找到，用最后一个 key（最可能是当前打开的）
    if (!nid && dmKeys.length > 0) {
      nid = dmKeys[dmKeys.length - 1];
    }

    if (!nid) {
      return JSON.stringify({ error: '无法确定 noteId', url: location.href, dmKeys: dmKeys });
    }

    let d = unwrap(dm[nid]);
    if (!d) {
      return JSON.stringify({
        error: `noteDetailMap 中不存在 noteId=${nid}`,
        availableKeys: dmKeys.slice(0, 5)
      });
    }

    const n = d.note;
    if (!n) {
      return JSON.stringify({ error: '数据中无 note 字段', noteId: nid });
    }

    const it = n.interactInfo || {};

    // 评论解包
    let cmts = unwrap(d.comments);
    let cl = unwrap(cmts?.list);
    const comments = Array.isArray(cl) ? cl.slice(0, 10).map(c => {
      let cc = unwrap(c);
      return {
        userName: cc?.userInfo?.nickname || '',
        content: (cc?.content || '').slice(0, 300),
        likes: parseCount(cc?.likeCount),
        subCommentCount: parseInt(cc?.subCommentCount) || 0
      };
    }) : [];

    // 标签解包
    let tags = [];
    try {
      let tl = unwrap(n.tagList);
      if (Array.isArray(tl)) tags = tl.map(t => t?.name || t).filter(Boolean);
    } catch (e) { }

    // 图片列表
    let imageCount = 0;
    try {
      let imgs = unwrap(n.imageList);
      if (Array.isArray(imgs)) imageCount = imgs.length;
    } catch (e) { }

    const data = {
      noteId: nid,
      title: n.title || '',
      type: n.type || '',
      desc: (n.desc || '').slice(0, 3000),
      likes: parseCount(it.likedCount),
      collected: parseCount(it.collectedCount),
      comments_count: parseCount(it.commentCount),
      shared: parseCount(it.shareCount),
      userName: n.user?.nickname || '',
      userId: n.user?.userId || '',
      time: n.time || 0,
      ipLocation: n.ipLocation || '',
      tags: tags,
      imageCount: imageCount,
      comments: comments
    };

    return JSON.stringify({
      success: true,
      data: data
    });

  } catch (e) {
    return JSON.stringify({ error: e.message, stack: e.stack });
  }
})()
