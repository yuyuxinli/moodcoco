---
name: xiaohongshu-scraper
description: Scrape Xiaohongshu (小红书) search results and post data (likes, comments, content, images) by keyword. Use when user requests to search, extract, or analyze 小红书 content for competitor research or content inspiration. Handles complete workflow from keyword search to structured data export.
---

# 小红书 Scraper

通过 Chrome 扩展 + 小红书 SSR 数据（`window.__INITIAL_STATE__`）抓取搜索结果和帖子详情。

## 前置条件

- 用户已在 Chrome 登录小红书
- 需要 `mcp__claude-in-chrome__*` 工具

---

## 脚本化自动工作流（推荐）

**核心思路：大模型不做决策，只做「读脚本→注入→等待→校验→下一个」的机械循环。**

所有操作已封装为独立 JS 脚本文件（`scripts/*.js`），大模型只需：
1. 用 Read 工具读取脚本内容
2. 用 `javascript_tool` 注入执行
3. 校验返回值的 `success` 字段
4. 出错时介入修复

### 脚本文件清单

| 脚本 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `set_filters.js` | 设置筛选条件 | `__SCRAPER_CONFIG.{sort,noteType,time}` | `{success, applied}` |
| `extract_search_results.js` | 提取搜索结果 | `__SCRAPER_CONFIG.{keyword,minLikes}` | `{success, count, results}` |
| `run_batch.js` | 批量提取+存 window | `__SCRAPER_CONFIG.{keyword,minLikes,maxPosts}` | `{success, count}` + `__SCRAPER_RESULTS` |
| `open_post.js` | JS派发鼠标事件打开帖子 | `__SCRAPER_TARGET.noteId` | `{success, noteId}` |
| `extract_post_detail.js` | 提取帖子详情 | 无（自动从 URL 获取） | `{success, data}` |
| `close_overlay.js` | 关闭弹窗 | 无 | `{success, method}` |

### 完整流程

```
Step 0: 初始化
  tabs_context_mcp → navigate 小红书 → 确认已登录

Step 1: 搜索（每个关键词执行一次）
  navigate → 搜索 URL
  等 3s
  [可选] 筛选（仅首个关键词时需要）：
    推荐：screenshot → click「图文」tab → click「筛选∨」→ click 选项 → click「收起」
    备选：JS: set_filters.js（当前 UI 下不可靠，常返回"未找到"）
  等 3s（筛选后页面刷新）
  JS: extract_search_results.js     → 拿到 results 列表
  Bash: 追加到 search_results.jsonl

Step 2: 逐帖提取（在同一搜索页循环，不需要重新搜索）
  for each noteId in results:
    JS: window.__SCRAPER_TARGET = {noteId}; → open_post.js
    等 3s
    JS: extract_post_detail.js      → 校验 success + data.desc
    Bash: 追加到 post_details.jsonl
    JS: close_overlay.js            → 或 navigate back
    等 1s

Step 3: 换关键词 → 回到 Step 1（Step 2 的循环不受影响）

Step 4: Python 汇总
  python3 scripts/process_posts.py ...
```

### Step 0: 初始化

```
tabs_context_mcp (createIfEmpty: true)
navigate → https://www.xiaohongshu.com/explore  # 确认已登录
```

### Step 1: 搜索 + 筛选 + 提取列表

**1a. 导航到搜索页**

```
navigate → https://www.xiaohongshu.com/search_result?keyword={编码关键词}&source=web_search_result_notes
等待 3 秒
```

**1b. 设置筛选（可选，仅需一次）**

> **注意：** `set_filters.js` 在当前小红书 UI 下不可靠（经常返回"未找到"），推荐使用手动坐标点击流程。

**推荐流程（computer tool 坐标点击）：**

```
1. 点击页面顶部「图文」tab（在「全部」「图文」「视频」「用户」tab 栏中）
   → 先截图确认 tab 位置，然后 left_click 对应坐标
   → 等待 2s 页面刷新

2. 点击右上角「筛选 ∨」按钮（坐标约 x=1420, y=108，以实际截图为准）
   → 筛选面板展开，显示以下选项组：
     - 排序依据：综合、最新、最多点赞、最多评论、最多收藏
     - 发布时间：不限、一天内、一周内、半年内
     - 搜索范围：不限、已看过、未看过、已关注
     - 位置距离：不限、同城、附近

3. 截图确认面板布局，然后 left_click 目标选项（如「最多点赞」「一周内」）
   → 每点一个选项，结果会立即刷新

4. 点击「收起」关闭筛选面板
   → 等待 2s 让结果稳定
```

**备选流程（JS 脚本，可能失败）：**

```javascript
// 先设置配置
window.__SCRAPER_CONFIG = {sort: '最多点赞', noteType: '图文', time: '一周内'};
// 然后注入 set_filters.js 的内容
// ⚠️ 如果返回值中 applied 含 "(未找到)"，需切换到上面的手动点击流程
```

校验：返回 `success: true` 且 `applied` 中无 `(未找到)`。等待 3 秒让页面刷新。

**1c. 提取搜索结果**

```javascript
// 先设置配置
window.__SCRAPER_CONFIG = {keyword: '不想上班', minLikes: 100};
// 然后注入 extract_search_results.js 的内容
```

校验：`count > 0`，每条 `noteId` 非空。

用 Bash `printf '%s\n' '{json}' >> search_results.jsonl` 逐条追加。

### Step 2: 逐帖提取详情（循环，不需要重新搜索）

**对 Step 1c 拿到的每个 noteId 执行：**

**2a. 打开帖子**

```javascript
window.__SCRAPER_TARGET = {noteId: 'xxxxx'};
// 注入 open_post.js 的内容
```

校验：`success: true`。等待 3 秒让弹窗/详情加载。

**2b. 提取详情**

```javascript
// 直接注入 extract_post_detail.js 的内容（无需配置）
```

校验：
- `success: true`
- `data.desc.length > 0`（正文非空）
- `data.noteId` 匹配预期

立即用 Bash 追加到 `post_details.jsonl`。

**2c. 关闭弹窗**

```javascript
// 注入 close_overlay.js 的内容
```

如果弹窗未关闭，改用 `navigate → back`。等待 1 秒。

**然后继续下一个 noteId，回到 2a。**

### Step 3: 换关键词

导航到新搜索 URL，回到 Step 1。Step 2 的循环独立于搜索。

### Step 4: 生成 CSV + .md

```bash
cd 竞品/xiaohongshu_{topic}
python3 {SKILL_DIR}/scripts/process_posts.py \
  --search-input search_results.jsonl \
  --detail-input post_details.jsonl \
  --output-dir posts \
  --csv xiaohongshu_data.csv
```

---

## 筛选功能

### 当前 UI 结构（2026-02 实测）

小红书搜索页的筛选分为两层：

1. **顶部 tab 栏**：`全部` `图文` `视频` `用户` — 直接点击即切换内容类型
2. **筛选面板**：点击右上角「筛选 ∨」按钮展开，包含以下选项组：

| 选项组 | 可选值 |
|--------|--------|
| 排序依据 | `综合` `最新` `最多点赞` `最多评论` `最多收藏` |
| 发布时间 | `不限` `一天内` `一周内` `半年内` |
| 搜索范围 | `不限` `已看过` `未看过` `已关注` |
| 位置距离 | `不限` `同城` `附近` |

### 推荐筛选流程（computer tool 坐标点击）

`set_filters.js` 脚本在当前小红书 UI 下不可靠，因为筛选面板默认折叠，且 DOM class 名称经常变化（CSS Modules hash）。**推荐使用 computer tool 截图 + 坐标点击：**

```
1. 截图 → 确认顶部 tab 栏位置
2. left_click「图文」tab → 等 2s
3. 截图 → 确认「筛选 ∨」按钮位置（通常在搜索结果区域右上角，约 x=1420, y=108）
4. left_click「筛选 ∨」 → 筛选面板展开
5. 截图 → 确认面板中各选项的坐标
6. left_click 目标选项（如「最多点赞」）→ 结果立即刷新
7. left_click 其他目标选项（如「一周内」）→ 结果再次刷新
8. left_click「收起」→ 关闭面板 → 等 2s
```

**关键点：**
- 每次点击选项后结果会立即刷新，不需要额外确认按钮
- 坐标会因浏览器窗口大小变化，**每一步都先截图确认再点击**
- 「图文」tab 的筛选和「视频」tab 的筛选选项可能不同

### 备选方案：set_filters.js（不推荐）

`set_filters.js` 通过 DOM 文本匹配找按钮并 click，但在当前 UI 下经常返回 `(未找到)`。仅当手动点击流程不可用时尝试。如果 `applied` 数组中出现 `(未找到)`，需立即切换到手动点击流程。

---

## 纠错机制

### 常见错误及自动修复

| 错误 | 原因 | 自动修复 |
|------|------|----------|
| `feeds 不是数组` | 页面未加载完成 | 等 3s 重试，最多 3 次 |
| `未找到包含 noteId 的链接` | 帖子不在当前视口 | 滚动页面后重试 |
| `noteDetailMap 中不存在` | 弹窗未加载完成 | 等 3s 重试 |
| `data.desc` 为空 | 视频帖无文字描述 | 记录但不阻断，继续下一个 |
| `__INITIAL_STATE__ 不存在` | 页面未完成 SSR | 刷新页面后重试 |
| 筛选 `(未找到)` | 筛选面板默认折叠 + CSS class 变化 | 改用 computer tool 截图+坐标点击流程（见「筛选功能」章节） |
| `close_overlay` 无效 | 弹窗样式变化 | 改用 `navigate → back` |

### 跳过策略

- noteId 找不到 → 跳过，记录到 skipped 列表
- desc 为空 → 保存但标记 `desc_empty: true`
- 连续 3 个 noteId 找不到 → 停止当前关键词，换下一个

---

## 关键陷阱速查

| 陷阱 | 解法 |
|------|------|
| 直接导航 `/explore/{noteId}` → 404 | 必须从搜索页点击（含 xsecToken） |
| 点击用户名 → 打开用户主页 | 点帖子**图片区域**（y≈300） |
| `noteDetailMap` 返回旧帖数据 | 用 URL 中的 noteId 作 key，不用 `keys[0]` |
| `JSON.stringify(vueProxy)` 返回 `{}` | 直接访问属性，不序列化 proxy |
| `parseInt("1.4万")` 返回 1 | 用 `parseCount()` 处理万/千后缀 |
| Vue ref 解包不够深 | 最多 **5 层** `._rawValue` / `._value` |
| JS tool 返回含 xsecToken 的 URL → BLOCKED | 不要在返回值中包含 URL，单独取 noteId |

---

## 技术原理

### `__INITIAL_STATE__` 数据模型（核心）

小红书网页版用 Vue 3 SSR，**所有数据**都在 `window.__INITIAL_STATE__` 中。

```
window.__INITIAL_STATE__ = {
  search: {
    feeds: Ref<Array<{           // 搜索结果列表（需 unwrap）
      id: string,                // = noteId
      modelType: 'note',
      noteCard: {
        displayTitle: string,
        type: 'normal' | 'video',
        user: { nickName, nickname },
        interactInfo: {
          likedCount: string | number,  // ⚠️ 可能是 "1.4万"
        }
      }
    }>>
  },
  note: {
    noteDetailMap: Ref<{         // 帖子详情（需 unwrap）
      [noteId]: {
        note: {
          title, desc, type, time,
          user: { nickname, userId },
          interactInfo: { likedCount, collectedCount, commentCount, shareCount },
          ipLocation, tagList, imageList
        },
        comments: { list: Array<{content, userInfo, likeCount, subCommentCount}> }
      }
    }>
  }
}
```

#### `__INITIAL_STATE__` vs DOM 的关键区别

| | `__INITIAL_STATE__` | DOM |
|---|---|---|
| 数据范围 | SSR 时生成的**全部**搜索结果（~30-50条） | 只渲染**视口内**的卡片（虚拟滚动/懒加载） |
| 更新时机 | 页面导航时整体替换 | 滚动时动态增删 DOM 节点 |
| 稳定性 | ⚠️ 其他脚本/AI 可能触发页面导航导致 state 变化 | 相对稳定但不完整 |

**关键后果：**
- `extract_search_results.js` 从 `__INITIAL_STATE__` 提取的 noteId，**不一定在 DOM 中有对应的 `<a>` 链接**
- `open_post.js` 通过 `a[href*=noteId]` 查找链接，如果帖子不在视口内，会返回 `{error: '未找到链接'}`
- **解决方案：** 提取搜索结果后，用 JS 交叉匹配 `__INITIAL_STATE__` 数据与 DOM 中实际存在的链接，只对 DOM 中可点击的帖子执行 open→extract→close 循环
- 如需提取不在视口的帖子，先滚动页面让其渲染到 DOM 中

### parseCount 函数（必须使用）

```javascript
function parseCount(s) {
  if (typeof s === 'number') return s;
  s = String(s);
  if (s.includes('万')) return Math.round(parseFloat(s) * 10000);
  if (s.includes('千')) return Math.round(parseFloat(s) * 1000);
  return parseInt(s) || 0;
}
```

互动数据可能是中文格式（`"1.4万"`、`"3千"`），`parseInt()` 会返回错误值。

### unwrap 函数（Vue reactive 解包）

```javascript
function unwrap(obj) {
  for (let i = 0; i < 5; i++) {
    if (obj && obj._rawValue !== undefined) obj = obj._rawValue;
    else if (obj && obj._value !== undefined) obj = obj._value;
  }
  return obj;
}
```

### 与 Instagram 的区别

| | Instagram | 小红书 |
|---|---|---|
| 数据源 | API fetch | SSR state |
| 正文 | API 返回 / 图片 OCR | desc 字段（图片 OCR 通常不必要） |
| 变量持久性 | tab 内持久 | 导航后 map 累积（需指定 key） |
| 分页 | cursor API | 滚动加载 |

---

## 预计耗时

| 环节 | 耗时 |
|------|------|
| 筛选 | ~15s/关键词（截图+多次点击）；JS 脚本时 ~4s 但常失败 |
| 搜索结果提取 | ~3s |
| 每篇帖子详情 | ~7s（点开3s + 提取1s + 关闭1s + 保存2s） |
| 5篇帖子 | ~35s |
| **每个关键词总计** | **~40s** |

---

## 输出目录结构

```
竞品/xiaohongshu_{topic}/
├── search_results.jsonl    # 搜索结果（标题+赞数）
├── post_details.jsonl      # 帖子详情（正文+评论）
├── xiaohongshu_data.csv    # CSV 汇总
└── posts/                  # 每篇帖子 .md
```
