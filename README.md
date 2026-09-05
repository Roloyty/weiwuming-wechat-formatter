# 谓无名公众号排版助手

`weiwuming-wechat-formatter` 是一套面向「谓无名」公众号编辑器的 AI Agent Skill。它把 Word 文档或粘贴文本转换成编辑器专用 Markdown，并通过编辑器同源渲染流程生成可粘贴到微信公众号后台的内联样式 HTML。

## 主要能力

- 解析 `.docx` 的标题、段落、样式、表格、脚注、尾注和图片关系。
- 在安装 LibreOffice 时自动将 legacy `.doc` 转换为 `.docx`。
- 生成编者按、章节标题、注释、作者简介、人物卡片、书籍卡片和延伸阅读等编辑器语法。
- 将图片上传到用户自己的图床：默认交给用户的 PicGo Server，也可选择直传用户自己的 Cloudflare R2 存储桶。
- 使用随 Skill 打包的编辑器快照和本地 `marked`、`jsdom` 生成微信粘贴版 HTML。
- 校验编者按首位、模块严格排序、公网图片 URL、语法块配对和未渲染的语法残留。
- 将疑似错别字、标点和合规问题作为校对提醒列出，不静默修改原文。

## 工作流程

```text
Word / 文本
    ↓
提取并分析文章结构
    ↓
生成谓无名 Markdown
    ↓
本地图片 → PicGo Server（或 R2 直传）→ 用户自己的图床 → 公网 URL
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
│   ├── image-host.md              # 图床配置说明（PicGo / R2）
│   └── syntax_rules.md            # 编辑器语法参考
├── scripts/
│   ├── extract_docx.py            # Word 结构提取
│   ├── setup_picgo.py             # PicGo CLI 状态、OAuth 与 uploader 配置引导
│   ├── upload_image.py            # 图床上传客户端（PicGo / R2）
│   └── render_html.js             # 编辑器同源 HTML 渲染与校验
├── tests/
│   ├── test_setup_picgo.py         # PicGo CLI 引导测试
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

## 配置图床

上传支持两种后端，都指向**用户自己的**图床，本项目不提供也不代管任何公共图床：

| 后端 | 说明 | 凭据存放 |
|---|---|---|
| `picgo`（默认） | 交给用户自己的 PicGo Server | PicGo 自己的配置，本项目不接触 |
| `r2`（可选） | S3 兼容接口直传用户自己的 Cloudflare R2 | 本地 `~/.weiwuming/image-host.json` 或环境变量 |

后端按此顺序决定：命令行 `--backend` → 环境变量 `WEIWUMING_IMAGE_BACKEND` → 配置文件 `"backend"` 字段 → 自动（R2 配全了用 R2，否则 PicGo）。**不配 R2 的用户行为与以前完全一致。**

### PicGo（默认）

本项目不直连某个固定图床，也不保存图床 AK、SK、Token 或 Bucket。用户需要先在 PicGo 中配置自己的图床并将其设为当前图床。

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

如果尚未配置 PicGo，可先检查 PicGo Core CLI：

```bash
python scripts/setup_picgo.py --status
```

PicGo Core 2.0+ 可以通过官方浏览器流程登录 PicGo Cloud：

```bash
python scripts/setup_picgo.py --login
```

该 OAuth 只负责 PicGo Cloud 登录，token 由 PicGo 自己保存。GitHub、S3、OSS、COS 等第三方图床仍需使用 `python scripts/setup_picgo.py --configure-uploader` 或 PicGo GUI 配置各自凭据。`--sync-config` 会调用官方云配置同步，可能上传本地配置并要求解决冲突，因此不会自动执行。

上传图片：

```bash
python scripts/upload_image.py images/cover.jpg
python scripts/upload_image.py --json images/*.jpg
```

脚本向 PicGo 发送官方格式的 JSON 请求：

```json
{"list":["图片绝对路径"]}
```

### Cloudflare R2（可选）

适合不想常驻 PicGo GUI、或需要在没有桌面环境的机器上运行的用户。走 S3 兼容接口，AWS SigV4 签名，仅用 Python 标准库。

需要先准备：自己的 R2 存储桶、绑定到该桶的公开访问域名、一对 R2 的 S3 API 凭据。

```json
{
  "backend": "r2",
  "r2": {
    "account_id": "",
    "access_key_id": "",
    "secret_access_key": "",
    "bucket": "",
    "domain": "https://img.example.com"
  }
}
```

也可用环境变量 `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` / `R2_DOMAIN`。

```bash
python scripts/upload_image.py --check --backend r2
python scripts/upload_image.py --backend r2 images/cover.jpg
```

对象键为 `weiwuming/<内容hash前16位><后缀>`，返回 `<domain>/<对象键>`。R2 的 Access Key 有写权限且以明文存放在本地配置文件中，请勿提交到任何仓库。

### 结果去向

上传返回的公网 URL 会写入书籍卡片、人物卡片等语法块。详细配置和故障排查见 [`references/image-host.md`](references/image-host.md)。API 依据为 [PicGo GUI Server 文档](https://docs.picgo.app/gui/guide/advance) 和 [PicGo Core API Reference](https://docs.picgo.app/core/api/)。

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

渲染器会拒绝标题或其他内容出现在编者按上方、模块顺序错误、本地图片路径、未成对语法块和无法识别的残留语法。

文章固定顺序为：编者按 → 正文 → 目录（如有）→ 注释（如有）→ `---[note]` → 作者简介 → 译者简介（如有）→ 延伸阅读 → 两条 staff → 固定关注区。

## 常用编辑器语法

| 语法 | 用途 |
|---|---|
| `>>> 内容` ... `<<<` | 编者按；必须是首个非空内容，上方不放文章标题 |
| `## 小标题` | 章节标题，下一行必须是 `---[dot]` |
| `---[dot]` | `##` 标题视觉分隔 |
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

## 相关项目

- **「谓无名」公众号编辑器**：本 Skill 配套的在线排版工具（HTML 单页应用），支持实时预览和一键复制到公众号后台。
- 在线体验：tools.weiwuming.cn

## License

MIT
