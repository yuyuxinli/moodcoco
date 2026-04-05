# 考研知识库格式说明

## 文件结构

```
kaoyan-knowledge/
├── national-lines.yml          # 国家线（2023-2025 三年）
├── region-mapping.yml          # A/B 区省份映射表
├── self-eval-mapping.yml       # 自评分 → 预估卷面分映射表
├── schools/                    # 院校专业数据（一校一文件）
│   ├── index.yml               # 院校索引（校名/别名 → 文件名映射）
│   ├── 10001.yml               # 北京大学
│   ├── 10003.yml               # 清华大学
│   └── ...
├── FORMAT.md                   # 本文件
└── SOURCES.md                  # 数据来源汇总 + 更新日志
```

## 数据格式约定

### 院校文件（schools/{code}.yml）

- 文件名：院校代码.yml（如 10269.yml）
- `subjects[]` 和 `subject_avg[]` 按索引一一对齐
- `scores[]` 按 year 降序排列，scores[0] 永远是最新年份
- `admission_ratio` 为数字类型，无数据时为 `null`
- 专业名称以研招网专业库为准（如 045400 = "应用心理"，非"应用心理学"）

### 国家线（national-lines.yml）

- 分为 `academic`（统一划线）和 `separate`（单独划线子类）
- 字段：`total`（总分线）、`single_100`（满分=100分科目单科线）、`single_gt_100`（满分>100分科目单科线）
- 管理类联考额外字段：`exam_total: 300`

### 国家线子类选择规则

Skill 在查询国家线时，按以下优先级：

1. **先查 separate**：用 major.code 匹配单独划线子类
   - 体育学_体育：code 以 0403 或 0452 开头
   - 教育_国际中文教育：code 以 0451 或 0453 开头
   - 工学照顾专业：code 在照顾专业清单中
   - 中医学_中西医结合_中医：code 以 1005/1006/1057 开头
   - 管理类专业学位：code 以 1251-1257 开头
2. **无匹配 → 查 academic**：用 major.discipline 匹配学科门类统一线

### 自评分映射（self-eval-mapping.yml）

按科目 full_score 选映射表：
- full_score=100 → score_100
- full_score=150 → score_150
- full_score=200 → score_200
- full_score=300 → score_300

## OpenClaw Skill 中的引用示例

```markdown
当用户说出目标院校后：
1. 读取 `references/kaoyan-knowledge/schools/index.yml`，模糊匹配院校名或别名
2. 匹配成功 → 读取 `references/kaoyan-knowledge/schools/{code}.yml`
3. 匹配失败 → 回复"没找到这个学校，你再确认一下名字？或者说全称试试"
4. 读取 school.province → 查 `references/kaoyan-knowledge/region-mapping.yml` 确定 A/B 区
5. 用户说出专业后 → 在该校 majors 列表中匹配
6. 专业匹配失败 → 列出该校已收录的专业供选择
7. 读取 `references/kaoyan-knowledge/national-lines.yml`：
   - 先用 major.code 尝试匹配 separate 子类
   - 无匹配 → 用 major.discipline 匹配 academic 统一线
8. 读取 `references/kaoyan-knowledge/self-eval-mapping.yml`，按科目 full_score 选映射表
```

## 新增院校流程

1. 在 index.yml 中添加院校条目（code/name/aliases/tier/province）
2. 创建 schools/{code}.yml，填入 school 和 majors 数据
3. 每个专业必须包含 source 字段（校名+年份+公告链接）
4. scores[] 按 year 降序排列
5. subject_avg[] 长度必须与 subjects[] 一致
6. 在 SOURCES.md 中记录更新日志
