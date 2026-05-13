# 谓无名公众号排版助手 (weiwuming-wechat-formatter)

一个专为 **「谓无名」公众号** 设计的 Claude Skill，用于将 Word 文档（.doc/.docx）或粘贴文本自动转换为公众号编辑器兼容的 Markdown 排版格式。

---

## 功能介绍

- **Word 文档解析**：自动提取 `.docx` 文件内容，保留段落结构、标题层级、加粗/斜体样式、表格、脚注和图片关系。
- **legacy .doc 支持**：通过 LibreOffice 自动转换旧版 `.doc` 为 `.docx` 后解析。
- **专用语法转换**：将原文转换为「谓无名」编辑器支持的自定义 Markdown 语法（编者按、注释、书籍卡片、作者简介等）。
- **内容忠实原则**：不改写、不润色、不编造信息，严格保留原文措辞、标点、人名、日期和引用。
- **校对提醒**：自动识别可能的错别字、标点混用、政治/合规风险，并在排版结果后单独列出。

---

## 仓库结构

```
.
├── SKILL.md                  # Claude Skill 定义文件
├── README.md                 # 本说明文件
├── scripts/
│   ├── extract_docx.py       # Word 文档提取脚本（纯 Python 标准库，无需 python-docx）
│   └── make_wechat_article.py # 文章生成辅助脚本
└── references/
    └── syntax_rules.md       # 「谓无名」编辑器完整语法规则参考
```

---

## 安装方法（Claude Code 用户）

### 方式一：通过 URL 直接添加 Skill

在 Claude Code 中执行以下命令，即可让当前 Agent 加载并使用本 Skill：

```bash
claude skills add https://github.com/Roloyty/weiwuming-wechat-formatter
```

> 请将 `Roloyty` 替换为你的实际 GitHub 用户名。

### 方式二：手动放置到本地 Skill 目录

1. 克隆本仓库到本地：

```bash
git clone https://github.com/Roloyty/weiwuming-wechat-formatter.git
```

2. 将 `SKILL.md` 复制到 Claude Code 的 skills 目录：

```bash
# macOS / Linux
cp weiwuming-wechat-formatter/SKILL.md ~/.claude/skills/wechat-formatter.md

# Windows (PowerShell)
Copy-Item weiwuming-wechat-formatter/SKILL.md $env:USERPROFILE\.claude\skills\wechat-formatter.md
```

---

## 使用方法

加载 Skill 后，在 Claude Code 中直接上传 Word 文件或粘贴文章文本，Agent 会自动：

1. **识别输入类型**：区分 `.docx` / `.doc` / 纯文本
2. **提取文档结构**：解析标题、段落、样式、表格、注释
3. **应用排版语法**：转换为 `### 标题 / 作者`、`## 小标题`、`---[dot]`、`>>>` 编者按、`---[notes]` 注释等专用标记
4. **输出排版结果**：返回可直接粘贴到「谓无名」编辑器的 Markdown 文本

### 示例对话

**用户**：
> 帮我排版这篇文章，文件是 `article.docx`

**Agent（加载本 Skill 后）**：
> 1. 执行 `python scripts/extract_docx.py article.docx` 提取内容
> 2. 分析结构并应用编辑器语法
> 3. 输出排版后的 Markdown + 校对提醒

---

## 「谓无名」编辑器语法速查

| 语法 | 用途 |
|---|---|
| `### 标题 / 作者` | 主标题（含作者名） |
| `## 小标题` | 章节小标题 |
| `---[dot]` | 视觉分隔线 |
| `>>>` ... `<<<` | 编者按 |
| `> 原文` | 引用/blockquote |
| `---[notes]` ... `---[/notes]` | 注释区域，`^[① 内容]` 为条目 |
| `[book:封面URL|书名|作者|出版社|年份]` | 中文书籍卡片 |
| `[enbook:封面URL|Title|Author|Publisher|Year]` | 英文书籍卡片 |
| `[jpbook:封面URL|書名|著者|出版社|年]` | 日文书籍卡片 |
| `---[bio-title:作者简介]` ... `---[/bio]` | 作者简介区域 |
| `[staff:姓名|职位]` | 工作人员署名 |
| `---[follow]` ... `---[/follow]` | 关注引导语 |

完整语法规则请参考 [`references/syntax_rules.md`](references/syntax_rules.md)。

---

## 依赖环境

- **Python 3**（标准库即可，无需额外安装 `python-docx`）
- **LibreOffice**（可选，仅在处理 legacy `.doc` 文件时需要）

---

## 注意事项

1. **不编造内容**：Skill 不会主动搜索网络来补全缺失的书籍、人物或出版信息。
2. **图片处理**：Word 内嵌图片为本地路径，不是图床 URL，因此不会直接输出到正文。如需插入图片，请先在图床上传后提供链接。
3. **封面缺失**：书籍卡片若缺少封面 URL，请保留空字段（如 `[book:|书名|作者|出版社|年份]`），编辑器会自动显示空白封面占位图。
4. **校对独立**：所有疑似问题（错别字、标点、合规风险）均在 `校对提醒` 中列出，不会静默修改原文。

---

## 相关项目

- **「谓无名」公众号编辑器**：本 Skill 配套的在线排版工具（HTML 单页应用），支持实时预览和一键复制到公众号后台。

---

## License

MIT
