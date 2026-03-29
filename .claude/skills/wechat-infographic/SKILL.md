---
name: wechat-infographic
description: Use when creating mobile-first infographic HTML pages for WeChat Moments sharing. Triggers: '配图', '信息图', 'infographic', '长图', '数据可视化', '微信图片', '手机截图', '朋友圈配图', '做张图'
---

# WeChat Infographic

## Overview

**金标准参考文件：`内容/公众号/20260325/pm-skills-infographic.html`** — 每次做新信息图前必读，严格对齐其设计语言。

用 HTML/CSS 制作手机端信息图，通过 Playwright 3x 截图生成超高清长图，用于微信朋友圈/群聊分享。

核心思路：**不做 App，做截图**。HTML 只是画布，最终产物是 PNG。

## When to Use

- 需要在微信分享数据可视化、排行榜、对比图、流程图
- 需要品牌统一的配图
- 需要超高清（3x Retina）长图

**不适用：** 需要交互的网页、需要动画的内容。

## Quick Reference

| 参数 | 值 |
|------|-----|
| 视口宽度 | 390px（iPhone 12 Pro） |
| 最大内容宽度 | 500px |
| 截图倍率 | 3x deviceScaleFactor |
| 输出分辨率 | 1170px 宽 |
| 标题字体 | Noto Serif SC, weight 900 |
| 正文字体 | Noto Sans SC, weight 300-500 |
| 数据字体 | JetBrains Mono, weight 700 |
| 本地预览 | `python3 -m http.server 8766` |
| Header 背景 | mascot.png 右下 + 渐变 + 半透明遮罩 |
| 吉祥物图片 | `docs/ai-teaching-plan/mascot.png`（复制到 HTML 同目录） |
| 品牌尾部 | 绿色渐变底 + 日期（YYYY.MM.DD），无 QR 无品牌名 |

## Design System

### Color Spectrum Design

**原则：相邻色相，平滑过渡，像彩虹一样**

设计多级色谱时，沿色轮选择相邻色相，确保：
- 相邻两色的色相差 20-40 度
- 明度逐级递减（浅 = 多/低，深 = 少/高）
- 饱和度保持在 35-55%

```css
/* 示例：绿蓝色谱（5 级） */
--level-1: #96C474;  /* H≈100 黄绿 */
--level-2: #7DC8A0;  /* H≈150 薄荷绿 */
--level-3: #4BB0A6;  /* H≈172 青绿 */
--level-4: #3892B6;  /* H≈198 海蓝 */
--level-5: #2E6BA4;  /* H≈210 深蓝 */
```

**关键规则：**
- 缩略图/代表色 = 展开后占比最大的颜色（如放大前的格子 = 放大后最多的格子颜色）
- 浅色（L>60%）只用于背景和大号数字，正文用深色（L<45%）
- 需要文字可读时，用色谱中更深的变体（如 `--accent-dark`）

### Spacing

```
页面内边距：28px 左右
Section 上下：36px
Header 上：48px 下：40px
组件间距：18-24px
```

## Components

### 1. Grid Visualization（格子图）

用 CSS Grid 生成 N 个彩色格子表示数量。

```html
<div class="grid" id="g1"></div>
<script>
function fill(id, map) {
  const g = document.getElementById(id);
  map.forEach(([n, cls]) => {
    for (let i = 0; i < n; i++) {
      const d = document.createElement('div');
      d.className = 'cell ' + cls;
      g.appendChild(d);
    }
  });
}
fill('g1', [[67,'c-gray'],[15,'c-green'],[1,'c-accent']]);
</script>
```

```css
.grid { display: grid; grid-template-columns: repeat(10, 1fr); gap: 3px; }
.cell { aspect-ratio: 1; border-radius: 4px; }
```

### 2. Stat Cards（数据卡片）

4 列等宽卡片，每张含：色点 + 大数字 + 标签 + 描述。

```css
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.stat { text-align: center; padding: 14px 4px; border: 1px solid var(--border); border-radius: 10px; background: white; }
.stat .n { font-family: 'JetBrains Mono'; font-size: 22px; font-weight: 700; }
.stat .unit { font-size: 12px; opacity: 0.7; }
.stat .tier { font-size: 12px; font-weight: 700; margin-top: 8px; }
.stat .tools { font-size: 8.5px; color: #9AA8B8; margin-top: 5px; line-height: 1.5; }
```

**注意：** 描述文字控制在 4 字/行，超出会折行变丑。

### 3. Callout（重点提示框）

```css
.callout { padding: 18px 20px; background: #F2F6FA; border-left: 3px solid var(--accent); border-radius: 0 8px 8px 0; }
.callout p { font-size: 13.5px; line-height: 1.85; color: #4A5A6A; }
.callout strong { color: var(--navy); }
.callout .hl { font-weight: 700; color: var(--accent-dark); }
```

### 4. Summary Cards（汇总卡片）

3 列大数字卡片，用于全页总结。

```css
.summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.summary-card { text-align: center; padding: 18px 6px; border-radius: 12px; background: white; border: 1px solid var(--border); }
.summary-card .big { font-family: 'JetBrains Mono'; font-size: 26px; font-weight: 700; }
.summary-card .label { font-size: 11px; color: #7A8A9A; margin-top: 8px; }
```

### 5. Legend（图例）

```css
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #5A6A7A; }
.lg { width: 12px; height: 12px; border-radius: 3px; }
```

### 6. Brand Footer（品牌尾部）

```css
.brand-footer { padding: 36px 28px 44px; text-align: center; background: linear-gradient(180deg, #D4F0E0, #C4E8D4); }
.brand-sub { font-size: 13px; color: var(--accent-dark); letter-spacing: 1px; }
```

## Workflow

### 1. 创建 HTML 文件

在目标目录创建 `.html`，用 Page Template（见下方）起步，根据需求组合 Components。

### 2. 启动本地服务

```bash
cd <html所在目录>
python3 -m http.server 8766
```

### 3. 实时预览

用 Chrome MCP 工具在 390px 视口下预览：
- `tabs_context_mcp` → `navigate` → `resize_window(390, 844)` → `screenshot`

### 4. 迭代调整

直接编辑 HTML/CSS → 刷新浏览器 → 截图确认。颜色、间距、文字都在这步反复调。

### 5. 导出 3x 高清图

```javascript
// Playwright run_code
async (page) => {
  const browser = page.context().browser();
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3
  });
  const p = await ctx.newPage();
  await p.goto('http://localhost:8766/your-page.html');
  await p.waitForLoadState('networkidle');
  await p.screenshot({
    fullPage: true,
    path: '/absolute/path/output-3x.png',
    type: 'png'
  });
  await ctx.close();
}
```

输出：1170px 宽的超高清 PNG，可直接在微信发送。

### 截图工具备选

- **首选 Playwright MCP**（`browser_run_code`）
- Playwright MCP 与 Chrome 冲突时，用 gstack 的 headless playwright：`node -e "const pw = require('/Users/jianghongwei/.claude/skills/gstack/node_modules/playwright'); ..."`
- 截图参数固定：`viewport: { width: 390, height: 844 }, deviceScaleFactor: 3`

## SVG 内联图表（推荐）

**微信公众号完整支持内联 SVG。** 做流程图、循环图、关系图时，优先用 SVG 而不是 CSS flex 拼凑。

优势：
- 箭头、连接线、三角形等图形元素用 SVG 画比 CSS hack 干净 100 倍
- 微信编辑器直接渲染，不需要转成图片
- 可以精确控制每个元素的位置，不受 flex 布局限制
- 缩放清晰，Retina 屏不模糊

用法：
```html
<!-- 直接在 section 里写 svg，不需要 img 标签 -->
<section style="text-align:center;margin:20px 0;">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 340 300" style="width:100%;max-width:340px;">
    <!-- 节点：圆角矩形 -->
    <rect x="95" y="16" width="150" height="60" rx="12" fill="#fff" stroke="#4AA882" stroke-width="1.5"/>
    <text x="170" y="52" text-anchor="middle" font-size="16" font-weight="900" fill="#1A2E1A">节点文字</text>

    <!-- 连接线 + 箭头 -->
    <line x1="170" y1="76" x2="170" y2="120" stroke="#B8D8C0" stroke-width="1.5"/>
    <polygon points="166,116 170,124 174,116" fill="#B8D8C0"/>

    <!-- 循环箭头：用 line + polygon 组合 -->
    <line x1="152" y1="180" x2="188" y2="180" stroke="#3892B6" stroke-width="1.5"/>
    <polygon points="184,176 192,180 184,184" fill="#3892B6"/>
  </svg>
</section>
```

注意事项：
- 必须加 `xmlns="http://www.w3.org/2000/svg"`，否则微信不渲染
- `viewBox` 控制画布大小，`style="width:100%;max-width:Npx"` 控制显示大小
- 字体用系统字体（SVG text 不支持 Google Fonts）
- 颜色直接写色值，不用 CSS 变量
- 适合：流程图、循环图、三角关系图、对比图
- 不适合：大段文字排版（用 section/p 更灵活）

参考：`内容/公众号/20260329/evolve-promo-wechat.html` 中的三角循环图

## 不要用的组件

- **Loop（循环流程）**：步骤节点 + 箭头的横排流程图，用 CSS flex 拼的，太丑。改用 SVG 画

## 文案规则

- 不用破折号（——/—），用逗号/冒号/换行
- 口语化，面向初级读者
- 流程步骤 `white-space: nowrap` 不折行

## Page Template

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>标题</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;900&family=Noto+Sans+SC:wght@300;400;500;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --dark: #2D3A50;
    --navy: #3A5670;
    --border: #D4DFE9;
    --light: #F2F6FA;
    --cream: #FAFCFD;
    --accent: #7DC8A0;
    --accent-dark: #4AA882;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Noto Sans SC', sans-serif; background: var(--cream); color: var(--dark); -webkit-font-smoothing: antialiased; }
  .page { max-width: 500px; margin: 0 auto; background: var(--cream); }

  /* Header: mascot 背景 + 半透明遮罩 */
  .header { text-align: center; padding: 32px 28px; background: url('mascot.png') right -30px bottom -20px / 280px auto no-repeat, linear-gradient(135deg, #D4F0E0 0%, #E8F8EE 50%, #F0FBF4 100%); min-height: 280px; display: flex; flex-direction: column; justify-content: center; position: relative; }
  .header::before { content: ''; position: absolute; inset: 0; background: rgba(232, 248, 238, 0.85); pointer-events: none; }
  .header > * { position: relative; z-index: 1; }
  .header h1 { font-family: 'Noto Serif SC', serif; font-weight: 900; font-size: 36px; color: #0A1A0A; line-height: 1.3; margin-bottom: 10px; white-space: nowrap; }
  .header .sub { font-size: 18px; color: #3A5A3A; line-height: 1.6; }
  .header .badge { display: inline-block; font-size: 12px; font-weight: 500; letter-spacing: 2px; color: var(--accent-dark); margin-top: 16px; }

  /* Section */
  .section { padding: 36px 28px; border-bottom: 1px solid var(--border); }
  .section-label { font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: var(--accent-dark); margin-bottom: 8px; }
  .section h2 { font-family: 'Noto Serif SC', serif; font-weight: 900; font-size: 22px; color: var(--navy); line-height: 1.35; margin-bottom: 8px; }
  .section .desc { font-size: 13px; color: #6B7B8D; line-height: 1.8; margin-bottom: 24px; }

  /* Brand Footer */
  .brand-footer { padding: 36px 28px 44px; text-align: center; background: linear-gradient(180deg, #D4F0E0, #C4E8D4); }
  .brand-sub { font-size: 13px; color: var(--accent-dark); letter-spacing: 1px; }
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <h1>标题</h1>
    <div class="sub">副标题说明文字</div>
    <div class="badge">心情可可</div>
  </div>

  <div class="section">
    <div class="section-label">Section Label</div>
    <h2>章节标题</h2>
    <p class="desc">描述文字。</p>
    <!-- 插入组件 -->
  </div>

  <div class="brand-footer">
    <div class="brand-sub">2026.03.26</div>
  </div>

</div>
</body>
</html>
```

## Common Mistakes

| 问题 | 解法 |
|------|------|
| 文字颜色太浅看不清 | 正文 L<45%，浅色只用于背景和大号数字 |
| 色谱过渡跳跃 | 相邻色相差 ≤ 40°，沿色轮单方向递进 |
| 放大前后颜色不匹配 | 缩略图颜色 = 展开后占比最大的颜色 |
| 卡片文字溢出折行 | 描述 ≤ 4 字/行，字号 8-9px |
| 截图模糊 | 必须 deviceScaleFactor: 3 |
| 手机端布局乱 | 固定 390px 视口开发，max-width: 500px |
| Google Fonts 加载慢 | 用 `rel="preconnect"` 加速 |

## 微信公众号内联 HTML 模式

信息图不仅可以截图分享，还可以**直接转为微信公众号内联 HTML**，复制粘贴到微信编辑器。

### 微信编辑器限制

| 支持 | 不支持 |
|------|--------|
| `style="..."` 内联样式 | `<style>` 标签（会被剥掉） |
| `data-darkmode-color/bgcolor` | CSS class（无效） |
| `section`, `p`, `span`, `img`, `h1-h6` | JavaScript |
| `display:flex`, `border-radius`, `linear-gradient` | CSS 变量 `var()` |
| `overflow-x:auto`（横向滑动） | `::before/::after` 伪元素 |
| 远程图片 URL（微信自动抓取到 CDN） | 本地图片、Google Fonts、`grid` 布局 |
| **内联 `<svg>`（完整支持）** | 外链 SVG 文件 |

### 转换清单

从信息图 HTML 转微信版：

1. **展开所有 CSS 变量** — `var(--accent)` → `#3DC88E`
2. **每个标签写 `style="..."`** — 去掉所有 class
3. **`div` → `section`** — 微信对 section 更友好
4. **去掉 Google Fonts** — 用 `-apple-system, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif`
5. **去掉伪元素** — 把效果直接写在父元素背景上
6. **`grid` → `flex`** — 微信不支持 grid
7. **加暗黑模式属性** — `data-darkmode-color="#xxx"` / `data-darkmode-bgcolor="#xxx"`
8. **图片用远程 URL** — 本地图片复制粘贴不生效，必须用 HTTPS URL

### 布局铁律（微信自带 padding）

**微信编辑器容器自带约 15px 左右 padding**，所以：

- **左右 padding 全部为 0** — `padding:40px 0` 而不是 `padding:40px 28px`
- **`flex:1` 必须搭配 `min-width:0`** — 否则内容会撑出容器（CSS flex 默认 `min-width:auto`）
- **flex 容器加 `overflow:hidden;width:100%`** — 双重保险防溢出
- **不要用固定百分比宽度替代 flex:1** — 会导致桌面端微信（宽屏）布局错乱
- **图片加 `max-width:100%`**

### 复制到微信的实现

```html
<!-- 可见预览区 -->
<div id="articleContent">{{微信 HTML}}</div>

<!-- 隐藏复制区（同样的 HTML） -->
<div id="wechatHtml" style="position:absolute;left:-9999px;">{{微信 HTML}}</div>

<script>
function copyToWechat() {
    const source = document.getElementById('wechatHtml');
    // 临时可见（浏览器不允许复制隐藏元素）
    source.style.position = 'fixed';
    source.style.left = '0';
    source.style.opacity = '0.01';
    source.style.width = '375px';
    const range = document.createRange();
    range.selectNodeContents(source);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand('copy');
    // 恢复隐藏
    source.style.position = 'absolute';
    source.style.left = '-9999px';
    sel.removeAllRanges();
}
</script>
```

### 图片方案

- **远程图片**：上传到 OSS（如 `yuyumao.oss-cn-beijing.aliyuncs.com`），用 HTTPS URL
- 微信编辑器粘贴时会自动抓取远程图片到微信 CDN
- 本地图片（`file://` 或相对路径）复制粘贴无效——浏览器能渲染但剪贴板不带图片数据
- 横向滑动画廊：`display:flex;overflow-x:auto;-webkit-overflow-scrolling:touch`，子元素 `flex-shrink:0`

### 参考作品

- `内容/公众号/20260326/ai-self-iteration-wechat.html` — 首个微信公众号内联 HTML（品牌绿色系 + 圆环可视化 + 图片画廊）
- `内容/公众号/20260326/ai-self-iteration.html` — 原始信息图版本（CSS 变量 + class + Google Fonts）

### xiaohu-wechat-format 工具

**路径**：`~/Documents/Github/xiaohu-wechat-format/`

Markdown → 微信内联 HTML 的转换工具，适合**纯文字文章排版**：

```bash
python3 ~/Documents/Github/xiaohu-wechat-format/scripts/format.py \
  --input article.md --theme moodcoco --format wechat
```

- 主题 JSON 在 `themes/` 目录，`moodcoco.json` 是心情可可品牌色（绿色主 + 蓝色辅）
- `--gallery` 模式可预览 20+ 主题
- 工具原理：Python markdown 转 HTML → 正则遍历标签注入 `style="..."` → 暗黑模式属性

**局限**：只能处理 Markdown 标准元素（标题/段落/列表/表格/引用/代码），无法做自定义布局（双列对比、圆环、卡片网格等）。复杂布局仍需手写内联 HTML。

## 参考作品

- `docs/ai-teaching-plan/ai-tier-pyramid.html` — AI 五段位全球人口分布（格子图 + 色谱 + 数据卡片 + 汇总）
