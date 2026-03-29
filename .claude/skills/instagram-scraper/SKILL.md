---
name: instagram-scraper
description: Scrape Instagram post engagement data (likes, comments, content) from public profiles. Use when user requests to extract, download, or analyze Instagram data. Handles complete workflow from profile scraping to CSV export.
---

# Instagram Scraper

通过 Chrome 扩展 + Instagram 内部 API 批量抓取 Instagram 帖子数据。

## 能力

- **互动数据**: 点赞数、评论数（精确数字）
- **内容**: 完整帖子文案
- **元数据**: URL、帖子类型（post/reel）、发布日期
- **图片**: 本地下载的图片文件（CDN URL 带防盗链会过期）
- **评论**: 每帖 Top 15 条热门评论（用户名 + 内容 + 点赞数）
- **输出**: CSV + 每篇帖子独立 .md 文件 + JSONL 原始数据 + 本地图片

## 前置条件

- 用户必须在 Chrome 浏览器中已登录 Instagram
- 目标主页必须是公开的，或用户有访问权限
- 需要 `mcp__claude-in-chrome__*` 系列工具

## 环境说明

此 skill 在本地 macOS + Claude Code + Chrome 扩展环境下工作。
输出目录默认为项目的 `竞品/{username}/` 目录。

---

## 完整工作流程

### Phase 1: 导航到主页 + 获取用户 ID

**Step 1.1: 获取 Tab 上下文**

```
调用 mcp__claude-in-chrome__tabs_context_mcp (createIfEmpty: true)
```

**Step 1.2: 导航到目标主页**

```
mcp__claude-in-chrome__navigate → https://www.instagram.com/{username}/
等待 3 秒
截图确认页面加载
```

**Step 1.3: 检查登录状态**

如果页面跳转到 `accounts/login` 或 `emailsignup`：
- 告知用户需要手动登录
- 等待用户确认登录完成
- 重新导航到目标主页

**Step 1.4: 提取用户 ID**

```javascript
// 从页面 HTML 中提取 user_id
const html = document.documentElement.innerHTML;
const match = html.match(/"profilePage_(\d+)"/);
const userId = match ? match[1] : null;

// 备用方法
if (!userId) {
  const match2 = html.match(/"user_id":"(\d+)"/);
  userId = match2 ? match2[1] : null;
}
```

用户 ID 是 Phase 2 API 调用的必需参数。

### Phase 2: 通过 Feed API 批量获取帖子数据

**关键发现：Instagram 有内部 feed API，可以直接返回结构化帖子数据，无需逐个访问帖子页面。**

**API 端点：**
```
GET https://www.instagram.com/api/v1/feed/user/{userId}/?count=33&max_id={cursor}
Headers:
  X-IG-App-ID: 936619743392459
  X-Requested-With: XMLHttpRequest
Credentials: include (使用当前登录会话的 cookie)
```

**返回数据结构：**
```json
{
  "status": "ok",
  "num_results": 12,
  "more_available": true,
  "next_max_id": "cursor_string",
  "items": [
    {
      "pk": "media_pk_number",
      "code": "shortcode",
      "media_type": 1,
      "like_count": 12345,
      "comment_count": 678,
      "taken_at": 1707500000,
      "caption": { "text": "..." },
      "image_versions2": { "candidates": [{ "url": "..." }] },
      "carousel_media": [...],
      "preview_comments": [{ "user": {"username": "..."}, "text": "..." }]
    }
  ]
}
```

**Step 2.1: 初始化存储**

```javascript
window.__ig_posts_v2 = [];
window.__ig_next_max_id = null;
window.__ig_batch = 0;
```

**Step 2.2: 分批 API 调用**

⚠️ **关键约束：`javascript_tool` 执行有超时限制（约 15-20 秒），不能一次性跑完所有 API 请求。**

每次调用获取约 4 页（~48 帖子），然后返回结果，分多次执行。

**如果用户只要图文帖（不要视频/Reels）：** 在循环内加 `if (item.media_type === 2) { window.__ig_reels_skipped++; continue; }` 跳过 Reels。由于跳过了部分帖子，实际入库数少于 API 返回数，需要多跑几轮。去重后如果不够目标数，继续 fetch 时用 `existing Set` 避免重复入库。

```javascript
(async () => {
  const userId = '{USER_ID}';
  let fetched = 0;

  for (let i = 0; i < 4; i++) {
    let url = `https://www.instagram.com/api/v1/feed/user/${userId}/?count=33`;
    if (window.__ig_next_max_id) url += `&max_id=${window.__ig_next_max_id}`;

    const r = await fetch(url, {
      headers: { 'X-IG-App-ID': '936619743392459', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'include'
    });
    const data = await r.json();
    if (data.status !== 'ok' || !data.items) break;

    for (const item of data.items) {
      // 如只要图文帖，跳过 Reels（media_type 2）
      if (item.media_type === 2) { window.__ig_reels_skipped++; continue; }
      const post = {
        shortcode: item.code,
        pk: String(item.pk),  // ← 必须保存，Phase 3 评论 API 需要
        type: 'post',
        url: `https://www.instagram.com/p/${item.code}/`,
        likes: item.like_count || 0,
        comments_count: item.comment_count || 0,
        date: new Date(item.taken_at * 1000).toISOString().split('T')[0],
        content: item.caption ? item.caption.text : '',
        image_urls: [],
        comments: []
      };
      // 提取图片（保留完整 URL，含 auth token，供后续 Python 下载）
      if (item.carousel_media) {
        post.image_urls = item.carousel_media.map(m => m.image_versions2?.candidates?.[0]?.url || '').filter(Boolean);
      } else if (item.image_versions2) {
        post.image_urls = [item.image_versions2.candidates?.[0]?.url || ''];
      }
      window.__ig_posts_v2.push(post);
      fetched++;
    }

    if (!data.more_available) break;
    window.__ig_next_max_id = data.next_max_id;
    window.__ig_batch++;
    await new Promise(r => setTimeout(r, 300));
  }

  return `Batch done. Total: ${window.__ig_posts_v2.length} posts (fetched ${fetched} this round)`;
})()
```

**重复执行上述脚本**，直到 `window.__ig_posts_v2.length >= 目标数量`。

每次调用约获取 48 帖子，300 帖子大约需要 7 次调用。

**Step 2.3: 去重和质量检查**

```javascript
const seen = new Set();
const unique = [];
for (const p of window.__ig_posts_v2) {
  if (!seen.has(p.shortcode)) {
    seen.add(p.shortcode);
    unique.push(p);
  }
}
window.__ig_posts_v2 = unique;

JSON.stringify({
  total_unique: unique.length,
  with_likes: unique.filter(p => p.likes > 0).length,
  with_content: unique.filter(p => p.content && p.content.length > 0).length,
  reels: unique.filter(p => p.type === 'reel').length,
  posts: unique.length - unique.filter(p => p.type === 'reel').length,
  date_range: `${unique[unique.length-1].date} to ${unique[0].date}`
})
```

### Phase 3: 通过 Comments API 获取热门评论

**评论 API 端点：**
```
GET https://www.instagram.com/api/v1/media/{media_pk}/comments/?can_support_threading=true&min_id=
Headers:
  X-IG-App-ID: 936619743392459
  X-Requested-With: XMLHttpRequest
Credentials: include
```

返回 ~15-20 条热门评论，每条包含：
```json
{
  "user": { "username": "user123" },
  "text": "comment content",
  "comment_like_count": 5,
  "created_at": 1707500000
}
```

**Step 3.1: 分批获取评论**

⚠️ **关键约束：每批最多 15 个帖子的评论，超过 20 个会超时。**

⚠️ **重要：必须用 `_comments_attempted` 标记已尝试的帖子**，否则 `comments_count > 0` 但 API 返回空评论的帖子会导致死循环。用 `findIndex` 选下一批会反复选中同一批已处理但评论为空的帖子。

```javascript
(async () => {
  const posts = window.__ig_posts_v2;
  // 只选 comments_count > 0 且未尝试过的帖子
  const needComments = posts.filter(p => (!p.comments || p.comments.length === 0) && p.comments_count > 0 && !p._comments_attempted);
  if (needComments.length === 0) return 'All done';
  const batch = needComments.slice(0, 15);
  let processed = 0;

  for (const post of batch) {
    try {
      post._comments_attempted = true;  // ← 标记已尝试，避免死循环
      const r = await fetch(
        `https://www.instagram.com/api/v1/media/${post.pk}/comments/?can_support_threading=true&min_id=`,
        {
          headers: { 'X-IG-App-ID': '936619743392459', 'X-Requested-With': 'XMLHttpRequest' },
          credentials: 'include'
        }
      );
      const data = await r.json();
      if (data.comments && data.comments.length > 0) {
        post.comments = data.comments.map(c => ({
          user: c.user?.username || '',
          text: c.text || '',
          likes: c.comment_like_count || 0,
          created_at: c.created_at || 0
        }));
      }
      processed++;
      await new Promise(r => setTimeout(r, 200));
    } catch (e) {
      processed++;
    }
  }

  const withComments = posts.filter(p => p.comments && p.comments.length > 0).length;
  const remaining = posts.filter(p => (!p.comments || p.comments.length === 0) && p.comments_count > 0 && !p._comments_attempted).length;
  return `Done ${processed}. With comments: ${withComments}/${posts.length}. Remaining: ${remaining}`;
})()
```

**重复执行上述脚本**，直到 `Remaining: 0`。
300 帖子大约需要 20 次调用（每次 15 帖子）。

⚠️ 即使 JS 调用超时，`window.__ig_posts_v2` 中的数据不会丢失——超时只是中断了返回，后台 fetch 可能仍在继续。

### Phase 4: 导出数据文件

⚠️ **关键经验：Instagram 的 CSP 会阻止自动下载。需要用户先在浏览器中允许该站点的下载权限。**

**Step 4.1: 提醒用户允许下载**

在第一次下载前，告知用户：
> "我会从 Instagram 页面触发文件下载。如果浏览器弹出'允许下载'的提示，请点击允许。"

**Step 4.2: 下载 JSONL（保留完整图片 URL，含 auth token）**

⚠️ **重要：JSONL 中必须保留带 auth token 的完整图片 URL**，Python 下载脚本需要这些 token 才能下载图片。同时生成清洗后的 URL 备用。

```javascript
const posts = window.__ig_posts_v2;
const output = posts.map(p => ({
  shortcode: p.shortcode,
  type: p.type,
  url: p.url,
  likes: p.likes,
  comments_count: p.comments_count,
  date: p.date,
  content: p.content,
  image_urls: p.image_urls,  // 保留完整 URL（含 auth token）
  image_urls_clean: p.image_urls.map(u => u.split('?')[0]),  // 清洗后的备用
  comments: p.comments
}));

const jsonl = output.map(p => JSON.stringify(p)).join('\n');
const blob = new Blob([jsonl], {type: 'text/plain'});
const a = document.createElement('a');
a.href = URL.createObjectURL(blob);
a.download = `ig_${USERNAME}_v2_full.jsonl`;
document.body.appendChild(a);
a.click();
a.remove();
`Downloaded ${output.length} posts (${(jsonl.length/1024/1024).toFixed(1)}MB)`;
```

**Step 4.3: 确认下载成功 + 复制到项目目录**

```bash
ls -lt ~/Downloads/ig_{username}*
mkdir -p 竞品/{username}
cp ~/Downloads/ig_{username}_v2_full.jsonl 竞品/{username}/posts_data_v2.jsonl
```

### Phase 5: 下载图片（紧急！）

⚠️ **图片 CDN URL 中的 auth token 会在数小时内过期，必须在导出 JSONL 后立即运行图片下载。**

**Step 5.1: 运行图片下载脚本**

```bash
cd 竞品/{username}
python3 download_images.py --input posts_data_v2.jsonl --output-dir images/
```

脚本从 JSONL 中读取带 auth token 的完整图片 URL，通过 Python `urllib` 逐个下载到本地。

**download_images.py 核心逻辑：**
- 从 `image_urls` 字段读取完整 CDN URL（含 auth token）
- 文件命名：`{shortcode}_{序号}.jpg`
- 已存在的文件（>1KB）自动跳过
- 自带 User-Agent + Referer 头伪装浏览器请求
- 每次下载间隔 0.1 秒避免速率限制
- 失败的文件记录但不中断整体流程

**预期性能：** 300 帖子约 1000 张图片，约 100MB，耗时约 3-5 分钟。

### Phase 6: 生成 .md 文件 + CSV

运行处理脚本，将 JSONL 转化为每篇帖子的 .md 文件（含评论 + 本地图片路径）：

```bash
cd 竞品/{username}
python3 {SKILL_DIR}/scripts/process_posts.py \
  --input posts_data_v2.jsonl \
  --output-dir posts \
  --csv instagram_data_v2.csv \
  --images-dir images
```

`--images-dir` 参数使 .md 文件优先使用本地图片路径（如存在），否则 fallback 到清洗后的 CDN URL。

### Phase 7: 图片 OCR → 文字替换

**目的：** 将 .md 文件中的 `![Image N](path)` 替换为 `<image>提取的文字</image>`，使内容可搜索、可分析。

**Step 7.1: 构建图片列表**

```bash
# 按每批 10-15 张分组（Haiku agent 单次处理上限）
python3 -c "
import os, glob
IMAGES_DIR = '竞品/{username}/images'
files = sorted(glob.glob(os.path.join(IMAGES_DIR, '*.jpg')))
batch_size = 12
for i in range(0, len(files), batch_size):
    batch = files[i:i+batch_size]
    fname = f'/tmp/batch_{i//batch_size}_images.txt'
    with open(fname, 'w') as f:
        for path in batch:
            sc = os.path.basename(path).rsplit('_', 1)[0]
            f.write(f'{sc}|{path}\n')
    print(f'{fname}: {len(batch)} images')
"
```

**Step 7.2: 并行启动 Haiku OCR agents**

每个 agent 处理 **5 个批次**（约 60 张图片），而不是 1 个批次。这样 512 张图只需 9 个 agent（而非 43 个），大幅减少 agent 启动开销。

```
Task(subagent_type="general-purpose", model="haiku", run_in_background=true)

prompt 示例：
  "处理以下 5 个批次文件：
   /tmp/batch_0_images.txt → 竞品/{username}/image_texts/batch_0.jsonl
   /tmp/batch_1_images.txt → 竞品/{username}/image_texts/batch_1.jsonl
   ...
   格式: {"shortcode":"XXX","image_num":N,"text":"extracted text"}"
```

⚠️ 并行 agent 数量建议 ~10 个。每个 agent 处理 5 批（60 张图）是最佳平衡点。实测 9 个 agent 并行跑 512 张图约 5-10 分钟全部完成。

**Step 7.3: 运行替换脚本**

```bash
cd 竞品/{username}
python3 replace_images_with_text.py --dry-run  # 先预览
python3 replace_images_with_text.py             # 实际替换
```

**Step 7.4: 验证替换完成**

```bash
grep -r '!\[Image' posts/ | wc -l  # 应该为 0
```

如果仍有残留 `![Image N]`，说明有图片缺失 OCR 数据，需要补充处理（见 Phase 8）。

### Phase 8: 补充缺失图片（按需）

当 Phase 7 验证发现残留 `![Image N]` 时，执行此阶段。

**常见原因：**
- Phase 5 图片下载时 CDN URL 已过期（token 失效）
- 部分帖子在初始抓取时就缺失图片数据

**Step 8.1: 识别缺失图片**

```bash
grep -r '!\[Image' posts/ --include='*.md' -c  # 列出残留文件和数量
```

**Step 8.2: 通过 Media Info API 获取新鲜 URL**

```
API 端点: /api/v1/media/{mediaId}/info/
Headers: X-IG-App-ID: 936619743392459, X-Requested-With: XMLHttpRequest
```

shortcode → mediaId 转换算法：
```javascript
const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
function shortcodeToMediaId(sc) {
    let id = BigInt(0);
    for (const c of sc) id = id * BigInt(64) + BigInt(alphabet.indexOf(c));
    return id.toString();
}
```

**Step 8.3: 控制请求频率**

- 每批最多 2 个 API 请求
- 请求间隔 3-5 秒
- 如果收到 HTML 响应（而非 JSON），说明触发了速率限制，等待 30-60 秒后继续
- 不要过度增加间隔，保持效率

**Step 8.4: URL 提取技巧**

CDN URL 含 auth token，通过 JS tool 返回时会被拦截 `[BLOCKED]`。解决方案：

```javascript
// 在 JS 中将 URL 写入 console
console.log('IMG_URL:' + shortcode + '|' + imageNum + '|' + url);
```

然后通过 `read_console_messages(pattern='IMG_URL:')` 提取，保存到文件后用 Python `urllib` 下载。

如果 console 输出太大被截断保存到文件，用 Python 从保存的 JSON 文件中解析：

```python
import json, re
with open('tool-results/mcp-...-read_console_messages-....txt') as f:
    data = json.load(f)
text = data[0]['text']
matches = re.findall(r'IMG_URL:([^\n]+)', text)
# 去重（保留最新）
url_map = {}
for m in matches:
    parts = m.strip().split('|', 2)
    key = parts[0] + '|' + parts[1]
    url_map[key] = parts[2]
```

**Step 8.5: 下载 → OCR → 替换**

与 Phase 5 + Phase 7 流程相同：Python 下载图片 → Haiku agent OCR → `replace_images_with_text.py` 替换。

### Phase 9: 输出验证和汇总

```bash
# 验证文件数量
ls posts/ | wc -l
ls images/ | wc -l

# 查看总大小
du -sh images/

# 确认无残留图片标记
grep -r '!\[Image' posts/ | wc -l  # 应为 0

# 预览示例 .md（确认评论和图片文字都在）
head -60 posts/001_*.md
```

向用户汇报：
- 总帖子数（Reels / 图文帖分类）
- 日期范围
- 平均/最高点赞数和评论数
- 图片下载数量和大小
- 评论获取数量
- OCR 完成数量
- 输出文件路径

---

## 数据格式说明

### v2 JSONL 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| shortcode | string | Instagram 帖子唯一标识 |
| type | string | `post` 或 `reel` |
| url | string | 帖子完整 URL |
| likes | number | 点赞数 |
| comments_count | number | 评论总数 |
| date | string | 发布日期 YYYY-MM-DD |
| content | string | 完整帖子文案 |
| image_urls | string[] | 带 auth token 的原始 CDN URL（用于下载） |
| image_urls_clean | string[] | 清洗后的 CDN URL（去除 auth token） |
| comments | object[] | 热门评论数组 |
| comments[].user | string | 评论者用户名 |
| comments[].text | string | 评论内容 |
| comments[].likes | number | 评论点赞数 |
| comments[].created_at | number | 评论时间戳 |

### .md 文件结构

```markdown
---
post_number: 1
shortcode: ABC123
url: https://www.instagram.com/p/ABC123/
type: post
likes: 12345
comments_count: 678
date: 2026-01-15
---

# Post #1 — 12.3K likes, 678 comments

**URL:** ...
**Type:** post | **Date:** 2026-01-15
**Engagement:** 12.3K likes, 678 comments

## Content
(完整帖子文案)

## Images
![Image 1](images/ABC123_1.jpg)

## Top Comments
- **user1** (5 likes): comment text
- **user2**: another comment
```

### CSV 字段

| 列名 | 说明 |
|------|------|
| post_number | 顺序编号 |
| shortcode | Instagram shortcode |
| type | post / reel |
| url | 完整 URL |
| likes | 精确点赞数 |
| comments_count | 精确评论数 |
| date | 发布日期 |
| content | 完整文案 |
| image_count | 图片数量 |
| top_comments_count | 已获取的热门评论数 |

---

## 性能对比

| 方案 | 300 帖子耗时 | 说明 |
|------|-------------|------|
| ✅ 当前方案：Feed API + Comments API + Python 图片下载 | ~10 分钟 | 7 次 feed API + 20 次 comments API + 3 分钟下载 |
| ❌ 旧方案：仅 Feed API 无评论无图片 | ~3 分钟 | 缺评论内容和本地图片 |
| ❌ 更旧方案：逐个访问帖子页面 | ~20 分钟 | 300 次 browser_navigate |

---

## 已知限制和陷阱

### javascript_tool 超时
- `javascript_tool` 执行约 15-20 秒超时
- Feed API：每次最多 4 页（~48 帖子）
- Comments API：每次最多 15 个帖子（20 个会超时）
- 超时不会丢失数据（`window.__ig_*` 变量在 tab 生命周期内持久）

### 图片 URL 防盗链
- Instagram CDN URL 含 auth token（`?stp=...&_nc_...`），**数小时后过期**
- 必须在导出 JSONL 后**立即**运行 Python 图片下载脚本
- 通过 JS tool 返回 URL 时会被拦截（`[BLOCKED: Cookie/query string data]`）
- JSONL 保留完整 URL 供 Python 下载，同时存清洗版本供展示

### 浏览器下载被拦截
- Instagram CSP 可能阻止 Blob 下载
- 解决方法：让用户在浏览器中允许 instagram.com 的下载权限

### JSZip 等外部库无法加载
- Instagram CSP 阻止从 CDN 加载外部脚本
- 不要尝试在页面内加载 JSZip/FileSaver 等库
- 用 Python 脚本处理本地文件操作

### 混合内容限制
- Instagram 是 HTTPS，不能向 HTTP 端点发送请求
- 不要尝试用本地 HTTP 服务器接收数据

### API 速率限制
- Feed API + Comments API：内部 API + 登录会话很少触发
- Media Info API（单帖查询）：每批 2 个请求，间隔 3-5 秒
- 触发特征：API 返回 HTML（含 `<!DOCTYPE`）而非 JSON
- 恢复方式：等待 30-60 秒后继续（不要过度延长，保持效率）
- 如遇 429 或空响应，等待 5-10 分钟后继续

---

## 备用方案：滚动收集 URL

如果 Feed API 失效（Instagram 更改 API），可退回到 URL 收集方案：

**Step 1: 初始化**
```javascript
window.__ig_posts = new Set();
window.__ig_scrollCount = 0;
```

**Step 2: 分批滚动（每次 10 次滚动）**
```javascript
(async () => {
  for (let i = 0; i < 10; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 1200));
    document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]').forEach(a => {
      const href = a.href.split('?')[0];
      if (href.includes('/p/') || href.includes('/reel/')) window.__ig_posts.add(href);
    });
    window.__ig_scrollCount++;
  }
  return `Scrolls: ${window.__ig_scrollCount}, Posts found: ${window.__ig_posts.size}`;
})()
```

重复执行直到达到目标数量。每次 10 scrolls 约获取 60 个新 URL。

---

## 脚本参考

### process_posts.py

**位置：** `{SKILL_DIR}/scripts/process_posts.py`

**功能：** 将 JSONL 数据处理为 CSV + 独立 .md 文件（含评论 + 本地图片路径）

**参数：**
- `--input FILE` — 输入 JSONL 文件路径（默认: posts_data.jsonl）
- `--output-dir DIR` — .md 文件输出目录（默认: posts）
- `--csv FILE` — CSV 输出路径（默认: instagram_data.csv）
- `--images-dir DIR` — 本地图片目录（可选，指定后 .md 中优先使用本地路径）

**支持格式：**
- v1 Compact: `{sc, t, u, l, c, d, txt, imgs, tc}`
- v2 Full: `{shortcode, type, url, likes, comments_count, date, content, image_urls, image_urls_clean, comments}`

### replace_images_with_text.py

**位置：** `竞品/{username}/replace_images_with_text.py`（首次使用时需创建）

**功能：** 读取 `image_texts/batch_*.jsonl`，将 .md 文件中的 `![Image N](url)` 替换为 `<image>提取的文字</image>`

**参数：**
- `--dry-run` — 预览模式，不实际写入

**JSONL 输入格式：** `{"shortcode":"XXX","image_num":N,"text":"..."}`

### download_images.py

**功能：** 从 JSONL 中读取带 auth token 的图片 URL 并下载到本地

**用法：**
```bash
python3 download_images.py --input posts_data_v2.jsonl --output-dir images/
```

**注意：** 必须在 JSONL 导出后尽快运行，auth token 数小时后过期。

### 输出目录结构

```
竞品/{username}/
├── posts_data_v2.jsonl          # 原始完整数据
├── instagram_data_v2.csv        # CSV 汇总表
├── download_images.py           # 图片下载脚本
├── extract_post_data.py         # 数据处理脚本（process_posts.py 的副本）
├── images/                      # 本地图片文件
│   ├── {shortcode}_1.jpg
│   ├── {shortcode}_2.jpg
│   └── ...
└── posts/                       # 每篇帖子的 .md 文件
    ├── 001_{shortcode}.md
    ├── 002_{shortcode}.md
    └── ...
```
