# WeChat Article → DOCX

将 Markdown 格式的公众号文章转换为排版好的 .docx 文件，可直接导入微信公众号编辑器。

## 触发词

'生成docx', '导出docx', '转docx', '公众号排版', 'wechat docx', '生成文档'

## 输入

- 一个 Markdown 格式的公众号文章文件路径
- （可选）配图文件夹路径

## 排版规范

基于心情可可公众号已发布文章的排版标准。

### 文字样式

| 元素 | 字号 (half-points) | 颜色 | 对齐 | 加粗 | 字体 |
|------|-------------------|------|------|------|------|
| 正文 | sz=32 (16pt) | #000000 | 左对齐 | 否 | Arial Unicode MS |
| 章标题 | sz=36 (18pt) | #2AAE67 | 居中 | 否 | Arial Unicode MS |
| 加粗句 | sz=32 (16pt) | #000000 | 左对齐 | 是 | Arial Unicode MS |
| 参考文献标题 | sz=20 (10pt) | #B2B2B2 | 左对齐 | 否 | Arial Unicode MS |
| 参考文献条目 | sz=20 (10pt) | #B2B2B2 | 左对齐 | 否 | Arial Unicode MS |

### 段落间距

- 正文段落：`spacing before=0 after=320 line=240 lineRule=auto`
- 章标题段落：`spacing before=480 after=320 line=240 lineRule=auto`
- 参考文献：`spacing before=0 after=160 line=240 lineRule=auto`

### 结构规则

1. **章标题格式**：`一、副标题文字`（数字 + 顿号 + 副标题），居中绿色，不加粗
2. **图片位置**：每章最后一个段落之后、下一章标题之前，插入一张配图，居中
3. **最后一章不插图**：全文最后一章（通常是收束/温柔着陆章）不插入配图
4. **最后一句**：以可可的口吻引导用户聊天，如"来找可可聊聊啊"
5. **参考文献**：放在文章最末，10pt 浅灰色，与正文明显区分
6. **加粗句**：Markdown 中 `**粗体**` 的句子，docx 中用 bold 渲染，字号不变

### Markdown → DOCX 映射

| Markdown 元素 | DOCX 处理 |
|---------------|----------|
| `# 标题` | 跳过（公众号标题在编辑器里单独填） |
| `### 一、副标题文字` | 绿色居中段落 18pt：`一、副标题文字` |
| 普通段落 | 16pt 黑色左对齐 |
| `**粗体文字**` | 16pt 黑色左对齐加粗 |
| `<sup>[1]</sup>` | 上标引用标记 |
| `![alt](path)` | 居中图片 |
| `---` | 忽略（不生成分割线） |
| `**参考文献**` | 10pt 浅灰色 |
| `[1] xxx` | 10pt 浅灰色 |

**注意**：Markdown 中章标题统一用 `###`（H3），不用 `##`（H2），因为 H2 在部分渲染器会自带横线。

## 工作流程

```
Step 1: 读取 Markdown 文件
Step 2: 解析结构（章节、段落、加粗、图片、参考文献）
Step 3: 用 docx-js 生成 .docx
Step 4: 验证文件
```

### Step 1: 读取与解析

读取 Markdown 文件，识别以下元素：
- H1 标题（跳过）
- H2 章标题 + H3 副标题（合并）
- 普通段落
- 加粗段落（`**...**` 包裹的整段）
- 行内加粗（段落内部分文字加粗）
- 上标引用 `<sup>[N]</sup>`
- 图片 `![alt](path)`
- 分割线 `---`
- 参考文献区域（`**参考文献**` 之后的所有内容）

### Step 2: 生成 DOCX

用 Node.js + `docx` 库生成。关键代码模板：

```javascript
const { Document, Packer, Paragraph, TextRun, ImageRun, AlignmentType } = require('docx');
const fs = require('fs');

// 正文段落
function bodyParagraph(runs) {
  return new Paragraph({
    spacing: { before: 0, after: 320, line: 240, lineRule: 'auto' },
    alignment: AlignmentType.LEFT,
    children: runs.map(r => new TextRun({
      text: r.text,
      bold: r.bold || false,
      font: 'Arial Unicode MS',
      size: 32,  // 16pt
      color: '000000',
      superScript: r.superScript || false,
    }))
  });
}

// 章标题段落
function chapterTitle(text) {
  return new Paragraph({
    spacing: { before: 480, after: 320, line: 240, lineRule: 'auto' },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({
      text: text,
      font: 'Arial Unicode MS',
      size: 36,  // 18pt
      color: '2AAE67',
    })]
  });
}

// 参考文献段落
function refParagraph(text) {
  return new Paragraph({
    spacing: { before: 0, after: 160, line: 240, lineRule: 'auto' },
    alignment: AlignmentType.LEFT,
    children: [new TextRun({
      text: text,
      font: 'Arial Unicode MS',
      size: 20,  // 10pt
      color: 'B2B2B2',
    })]
  });
}

// 图片段落（居中）
function imageParagraph(imagePath) {
  const imageData = fs.readFileSync(imagePath);
  const ext = imagePath.split('.').pop().toLowerCase();
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 320, after: 320 },
    children: [new ImageRun({
      type: ext === 'jpg' ? 'jpeg' : ext,
      data: imageData,
      transformation: { width: 600, height: 400 },  // 根据实际图片调整
      altText: { title: 'illustration', description: 'Article illustration', name: 'img' },
    })]
  });
}
```

### Step 3: 组装文档

```javascript
const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      // ... 按顺序放入所有段落
    ]
  }]
});

const buffer = await Packer.toBuffer(doc);
fs.writeFileSync('output.docx', buffer);
```

### Step 4: 验证

```bash
python3 scripts/office/validate.py output.docx
```

## 注意事项

- `sz` 值是 half-points（半磅），所以 16pt = sz=32, 18pt = sz=36, 10pt = sz=20
- 绿色色值 `#2AAE67` 是心情可可品牌色
- 图片宽度建议 600px 左右，不要超出页面内容区域
- 最后一章（收束章）不插入配图
- 参考文献和正文之间不需要分割线，仅靠字号和颜色区分
