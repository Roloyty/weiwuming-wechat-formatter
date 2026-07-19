# 谓无名公众号排版助手

`weiwuming-wechat-formatter` 是一套面向「谓无名」公众号编辑器的 AI Agent Skill。它把 Word 文档或粘贴文本转换成编辑器专用 Markdown，并通过编辑器同源渲染流程生成可粘贴到微信公众号后台的内联样式 HTML。

## 主要能力

- 解析 `.docx` 的标题、段落、样式、表格、脚注、尾注和图片关系。
- 在安装 LibreOffice 时自动将 legacy `.doc` 转换为 `.docx`。
- 生成编者按、章节标题、注释、作者简介、人物卡片、书籍卡片和延伸阅读等编辑器语法。
- 将图片交给用户自己的 PicGo Server，使用用户在 PicGo 中配置并选中的图床。
- 使用随 Skill 打包的编辑器快照和本地 `marked`、`jsdom` 生成微信粘贴版 HTML。
- 校验公网图片 URL、语法块配对和未渲染的语法残留。
- 将疑似错别字、标点和合规问题作为校对提醒列出，不静默修改原文。

## 工作流程

```text
Word / 文本
    ↓
提取并分析文章结构
    ↓
生成谓无名 Markdown
    ↓
本地图片 → PicGo Server → 用户自选图床 → 公网 URL
    ↓
编辑器同源渲染与校验
    ↓
Markdown + 微信粘贴版 HTML + 浏览器预览
```

## 仓库结构

```text
.
├── SKILL.md                       # Skill 工作规则
├── README.md                      # 项目介绍与使用说明
├── assets/
│   └── editor-index.html          # 谓无名编辑器快照，作为渲染兜底
├── references/
│   ├── image-host.md              # PicGo Server 配置说明
│   └── syntax_rules.md            # 编辑器语法参考
├── scripts/
│   ├── extract_docx.py            # Word 结构提取
│   ├── upload_image.py            # PicGo Server API 上传客户端
│   └── render_html.js             # 编辑器同源 HTML 渲染与校验
├── tests/
│   └── test_upload_image.py        # PicGo API 客户端模拟服务测试
├── package.json
└── package-lock.json
```

## 环境要求

- Python 3.9+，只使用标准库。
- Node.js 18+。
- LibreOffice，可选，仅处理 `.doc` 时需要。
- PicGo GUI 2.2+ 或提供兼容 `/upload`、`/heartbeat` 接口的 PicGo Server。

安装 Node 依赖：

```bash
npm ci
```

## 安装 Skill

克隆仓库：

```bash
git clone https://github.com/Roloyty/weiwuming-wechat-formatter.git
```

然后按所用 Agent 的 Skill 加载方式安装本目录。Claude Code 用户也可以尝试：

```bash
claude skills add https://github.com/Roloyty/weiwuming-wechat-formatter
```

## 配置 PicGo 图床

本项目不再直连某个固定图床，也不保存图床 AK、SK、Token 或 Bucket。用户需要先在 PicGo 中配置自己的图床并将其设为当前图床。

PicGo GUI 默认上传接口：

```text
http://127.0.0.1:36677/upload
```

默认地址可以直接使用。若用户修改了 PicGo Server 地址，请创建 `~/.weiwuming/image-host.json`：

```json
{
  "picgo": {
    "api_url": "http://127.0.0.1:36677/upload",
    "server_secret": "",
    "timeout": 90
  }
}
```

也可以使用环境变量：

```text
PICGO_API_URL=http://127.0.0.1:36677/upload
PICGO_SERVER_SECRET=可选的服务密钥
PICGO_TIMEOUT=90
```

首次使用先检查接口：

```bash
python scripts/upload_image.py --check
```

上传图片：

```bash
python scripts/upload_image.py images/cover.jpg
python scripts/upload_image.py --json images/*.jpg
```

脚本向 PicGo 发送官方格式的 JSON 请求：

```json
{"list":["图片绝对路径"]}
```

PicGo 返回的公网 URL 会写入书籍卡片、人物卡片等语法块。详细配置和故障排查见 [`references/image-host.md`](references/image-host.md)。API 依据为 [PicGo GUI Server 文档](https://docs.picgo.app/gui/guide/advance) 和 [PicGo Core API Reference](https://docs.picgo.app/core/api/)。

## 脚本用法

### 提取 Word 结构

```bash
python scripts/extract_docx.py article.docx
```

脚本输出 JSON，供 Agent 根据样式、段落、表格和注释信息生成谓无名 Markdown。

### 渲染微信 HTML

```bash
node scripts/render_html.js article.md --preview
```

输出：

- `article.html`：微信粘贴版内联样式 HTML。
- `article.preview.html`：浏览器预览页。

渲染器会拒绝本地图片路径、未成对语法块和无法识别的残留语法。

## 常用编辑器语法

| 语法 | 用途 |
|---|---|
| `### 标题 / 作者` | 主标题和作者 |
| `## 小标题` | 章节标题 |
| `---[dot]` | 标题视觉分隔 |
| `>>> 内容` ... `<<<` | 编者按 |
| `---[notes]` ... `---[/notes]` | 注释区域 |
| `[book:封面URL\|书名\|作者\|出版社\|年份]` | 中文书籍卡片 |
| `[universal:图片URL\|名称\|简介]` | 人物、事件、图片等通用卡片 |
| `---[reading-title:延伸阅读]` ... `---[/reading]` | 延伸阅读 |
| `---[bio-title:作者简介]` ... `---[/bio]` | 作者简介 |
| `[staff:姓名\|职位]` | 工作人员署名 |
| `---[follow]` ... `---[/follow]` | 关注引导 |

完整规则见 [`references/syntax_rules.md`](references/syntax_rules.md)。

## 图片与安全说明

- Word 中的 `word/media/image1.png` 是文档包内部路径，不是公网 URL，不能直接写入微信文章。
- 远程 `http(s)` 图片会直接沿用；本地图片才会调用 PicGo。
- PicGo Server 建议只监听 `127.0.0.1`。若监听局域网地址，请启用 shared secret 和防火墙限制。
- PicGo 图床凭据只保存在 PicGo 自身配置中，不应提交到本仓库。
- 上传后的图片通常可以公网访问，请勿上传隐私或未公开资料。

## License

MIT
