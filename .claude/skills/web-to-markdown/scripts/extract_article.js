/**
 * extract_article.js — 从网页提取文章正文，转为 Markdown 格式
 *
 * 使用方法：
 *   直接在 javascript_tool 中注入执行（无需配置）
 *
 * 返回：
 *   {
 *     success: true,
 *     title: "文章标题",
 *     author: "作者（如有）",
 *     date: "日期（如有）",
 *     wordCount: 1234,
 *     totalChunks: 3,
 *     chunk: 1,
 *     content: "## 标题\n\n正文..." (当前 chunk 的 Markdown)
 *   }
 *
 * 如果文章过长（>12000字符），会分 chunk 存入 window.__ARTICLE_CHUNKS
 * 用 read_chunks.js 读取后续 chunk
 */
(() => {
  try {
    // ========== HTML → Markdown 转换器 ==========
    function htmlToMd(node) {
      if (!node) return '';
      if (node.nodeType === 3) { // Text node
        return node.textContent.replace(/\s+/g, ' ');
      }
      if (node.nodeType !== 1) return ''; // Not element

      const tag = node.tagName.toLowerCase();
      const children = Array.from(node.childNodes).map(htmlToMd).join('');

      switch (tag) {
        case 'h1': return '\n\n# ' + children.trim() + '\n\n';
        case 'h2': return '\n\n## ' + children.trim() + '\n\n';
        case 'h3': return '\n\n### ' + children.trim() + '\n\n';
        case 'h4': return '\n\n#### ' + children.trim() + '\n\n';
        case 'h5': return '\n\n##### ' + children.trim() + '\n\n';
        case 'h6': return '\n\n###### ' + children.trim() + '\n\n';
        case 'p': return '\n\n' + children.trim() + '\n\n';
        case 'br': return '\n';
        case 'hr': return '\n\n---\n\n';
        case 'strong': case 'b': return '**' + children.trim() + '**';
        case 'em': case 'i': return '*' + children.trim() + '*';
        case 'u': return children; // no markdown underline
        case 'del': case 's': return '~~' + children.trim() + '~~';
        case 'a': {
          const href = node.getAttribute('href');
          const text = children.trim();
          if (!text) return '';
          if (!href || href.startsWith('#') || href.startsWith('javascript:')) return text;
          return '[' + text + '](' + href + ')';
        }
        case 'img': {
          const alt = node.getAttribute('alt') || '';
          const src = node.getAttribute('src') || '';
          if (!src) return '';
          return '![' + alt + '](' + src + ')';
        }
        case 'blockquote': return '\n\n> ' + children.trim().replace(/\n/g, '\n> ') + '\n\n';
        case 'ul': return '\n\n' + children + '\n\n';
        case 'ol': return '\n\n' + children + '\n\n';
        case 'li': {
          const parent = node.parentElement;
          const isOrdered = parent && parent.tagName.toLowerCase() === 'ol';
          const prefix = isOrdered
            ? (Array.from(parent.children).indexOf(node) + 1) + '. '
            : '- ';
          return prefix + children.trim() + '\n';
        }
        case 'code': {
          const parent = node.parentElement;
          if (parent && parent.tagName.toLowerCase() === 'pre') {
            const lang = node.className.replace(/language-/, '').split(/\s/)[0] || '';
            return '\n\n```' + lang + '\n' + node.textContent + '\n```\n\n';
          }
          return '`' + children.trim() + '`';
        }
        case 'pre': {
          if (node.querySelector('code')) return children;
          return '\n\n```\n' + node.textContent + '\n```\n\n';
        }
        case 'figure': return children;
        case 'figcaption': return '\n*' + children.trim() + '*\n';
        case 'table': return '\n\n' + tableToMd(node) + '\n\n';
        // Skip non-content elements
        case 'script': case 'style': case 'nav': case 'footer':
        case 'aside': case 'iframe': case 'noscript': case 'svg':
        case 'button': case 'input': case 'form': case 'select':
          return '';
        default:
          return children;
      }
    }

    function tableToMd(table) {
      const rows = Array.from(table.querySelectorAll('tr'));
      if (rows.length === 0) return '';
      const result = [];
      rows.forEach((row, i) => {
        const cells = Array.from(row.querySelectorAll('th, td'));
        const line = '| ' + cells.map(c => c.textContent.trim()).join(' | ') + ' |';
        result.push(line);
        if (i === 0) {
          result.push('| ' + cells.map(() => '---').join(' | ') + ' |');
        }
      });
      return result.join('\n');
    }

    // ========== 寻找主要内容区域 ==========
    function findArticle() {
      // 按优先级尝试各种选择器
      const selectors = [
        'article[role="main"]',
        'article .post-content',
        'article .entry-content',
        '.post-content',
        '.entry-content',
        '.article-content',
        '.article-body',
        '.story-body',
        '.news-body',
        '[itemprop="articleBody"]',
        '.content-body',
        '.post-body',
        '.rich_media_content',  // 微信公众号
        '#js_content',           // 微信公众号
        '.article__body',
        '.article-text',
        'main article',
        'article',
        '[role="article"]',
        'main',
        '.content',
        '#content',
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          const text = el.textContent.trim();
          if (text.length > 200) return el; // 内容够多才算找到
        }
      }

      // 最后手段：找最大的文本块
      const candidates = document.querySelectorAll('div, section');
      let best = null;
      let bestLen = 0;
      candidates.forEach(el => {
        const len = el.textContent.trim().length;
        const children = el.querySelectorAll('p');
        if (children.length >= 3 && len > bestLen) {
          bestLen = len;
          best = el;
        }
      });
      return best || document.body;
    }

    // ========== 提取元数据 ==========
    function getMeta() {
      const title = document.querySelector('h1')?.textContent?.trim()
        || document.querySelector('meta[property="og:title"]')?.content
        || document.title;

      const author = document.querySelector('meta[name="author"]')?.content
        || document.querySelector('[rel="author"]')?.textContent?.trim()
        || document.querySelector('.author-name')?.textContent?.trim()
        || document.querySelector('.byline')?.textContent?.trim()
        || document.querySelector('[itemprop="author"]')?.textContent?.trim()
        || '';

      const date = document.querySelector('time')?.getAttribute('datetime')
        || document.querySelector('meta[property="article:published_time"]')?.content
        || document.querySelector('.date')?.textContent?.trim()
        || document.querySelector('[itemprop="datePublished"]')?.content
        || '';

      return { title, author, date };
    }

    // ========== 主逻辑 ==========
    const article = findArticle();
    const meta = getMeta();

    // 转换为 Markdown
    let md = htmlToMd(article);

    // 清理：去除多余空行
    md = md.replace(/\n{3,}/g, '\n\n').trim();

    // 如果提取到的内容太短，可能找错了容器
    if (md.length < 100) {
      return JSON.stringify({
        error: '提取到的内容太短（' + md.length + ' 字符），可能需要手动指定选择器',
        title: meta.title,
        bodyLength: document.body.textContent.length
      });
    }

    // 添加元数据头
    let fullMd = '# ' + meta.title + '\n\n';
    if (meta.author) fullMd += '**作者**: ' + meta.author + '\n';
    if (meta.date) fullMd += '**日期**: ' + meta.date + '\n';
    if (meta.author || meta.date) fullMd += '\n---\n\n';
    fullMd += md;

    // 分 chunk（每 chunk ~12000 字符，按段落边界切）
    const CHUNK_SIZE = 12000;
    const chunks = [];
    if (fullMd.length <= CHUNK_SIZE) {
      chunks.push(fullMd);
    } else {
      let remaining = fullMd;
      while (remaining.length > 0) {
        if (remaining.length <= CHUNK_SIZE) {
          chunks.push(remaining);
          break;
        }
        // 在 CHUNK_SIZE 附近找段落边界
        let cut = remaining.lastIndexOf('\n\n', CHUNK_SIZE);
        if (cut < CHUNK_SIZE * 0.5) cut = CHUNK_SIZE; // 没找到好的切点就硬切
        chunks.push(remaining.slice(0, cut));
        remaining = remaining.slice(cut);
      }
    }

    // 存入 window 供后续读取
    window.__ARTICLE_CHUNKS = chunks;
    window.__ARTICLE_META = meta;

    return JSON.stringify({
      success: true,
      title: meta.title,
      author: meta.author,
      date: meta.date,
      wordCount: fullMd.length,
      totalChunks: chunks.length,
      chunk: 1,
      content: chunks[0]
    });

  } catch (e) {
    return JSON.stringify({ error: e.message, stack: e.stack?.slice(0, 200) });
  }
})()
