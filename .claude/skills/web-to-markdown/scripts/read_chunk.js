/**
 * read_chunk.js — 读取 extract_article.js 存储的后续 chunk
 *
 * 预设配置：
 *   window.__ARTICLE_CHUNK_INDEX = 2  (从 1 开始，1 已在 extract 时返回)
 *
 * 返回：
 *   {
 *     success: true,
 *     chunk: 2,
 *     totalChunks: 3,
 *     content: "..." (该 chunk 的 Markdown 内容)
 *   }
 */
(() => {
  try {
    const chunks = window.__ARTICLE_CHUNKS;
    if (!chunks || !Array.isArray(chunks)) {
      return JSON.stringify({ error: '未找到文章数据，请先执行 extract_article.js' });
    }

    const idx = (window.__ARTICLE_CHUNK_INDEX || 2) - 1; // 转为 0-based
    if (idx < 0 || idx >= chunks.length) {
      return JSON.stringify({
        error: 'chunk 索引超出范围',
        requested: idx + 1,
        totalChunks: chunks.length
      });
    }

    return JSON.stringify({
      success: true,
      chunk: idx + 1,
      totalChunks: chunks.length,
      content: chunks[idx]
    });

  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
})()
