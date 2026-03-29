---
name: web-to-markdown
description: 把网页文章提取为 Markdown 格式保存到本地。用于阅读长文章、保存参考资料。触发词：'读这篇文章', '提取文章', '网页转markdown', '保存这个网页', '把这篇存下来', 'web to markdown', 'extract article', '读一下这个链接'
---

# Web to Markdown

把网页文章完整提取为 Markdown 格式，保存到本地文件。

## 前置条件

- 需要 `mcp__claude-in-chrome__*` 工具
- Chrome 浏览器已打开

## 工作流

### Step 1: 初始化浏览器

```
tabs_context_mcp (createIfEmpty: true)
tabs_create_mcp → 拿到 tabId
```

### Step 2: 导航到目标 URL

```
navigate → {url} → tabId
等待 5 秒（让页面完全加载）
```

### Step 3: 提取文章

读取 `scripts/extract_article.js` 的内容，用 `javascript_tool` 注入执行。

```javascript
// 直接注入 extract_article.js 的全部内容
// 返回：{success, title, author, date, wordCount, totalChunks, chunk, content}
```

校验：
- `success === true`
- `wordCount > 200`（内容足够长）
- 如果 `error`，检查是否需要手动指定选择器

### Step 4: 读取后续 chunk（如有）

如果 `totalChunks > 1`，逐个读取剩余 chunk：

```javascript
window.__ARTICLE_CHUNK_INDEX = 2; // 然后注入 read_chunk.js
```

重复直到所有 chunk 读完。

### Step 5: 保存为 Markdown 文件

把所有 chunk 拼接，保存到指定路径：

```bash
# 方法1：直接用 Write 工具写入
# 方法2：用 Python 脚本
python3 scripts/save_article.py --output /path/to/article.md --chunks chunk1.txt chunk2.txt
```

**默认保存路径**：与当前工作目录相关，如 `./参考文章/{标题}.md`

### Step 6: 输出结果

告诉用户：
- 文章标题
- 作者/日期
- 字数
- 保存路径
- 简要摘要（1-2 句话描述文章主题）

## 支持的网站

脚本通过智能选择器自动适配大多数网站：

| 网站类型 | 选择器 |
|----------|--------|
| 微信公众号 | `.rich_media_content`, `#js_content` |
| Medium | `article` |
| BuzzFeed | `.article-body`, `article` |
| 一般博客 | `.post-content`, `.entry-content` |
| 新闻网站 | `[itemprop="articleBody"]`, `.story-body` |
| 通用 | 自动找最大文本块 |

## 故障处理

| 问题 | 解法 |
|------|------|
| 提取内容太短 | 手动用 `get_page_text` 获取，或指定 CSS 选择器 |
| 页面需要登录 | 提示用户先在 Chrome 中登录 |
| 页面动态加载 | 增加等待时间到 10 秒 |
| JS 执行超时 | 文章极长时分页提取 |

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `extract_article.js` | 提取文章 + 转 Markdown + 分 chunk |
| `read_chunk.js` | 读取后续 chunk |
| `save_article.py` | 保存为 .md 文件 |
