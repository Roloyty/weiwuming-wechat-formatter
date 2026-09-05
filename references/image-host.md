# 图床上传配置

公众号编辑器无法访问 `./images/x.jpg` 这类本地路径，本地图必须先换成公网 URL。`scripts/upload_image.py` 提供两种后端：

| 后端 | 说明 | 凭据存放 |
|---|---|---|
| `picgo`（默认） | 把路径交给用户自己的 PicGo Server，由 PicGo 当前选中的图床完成上传 | PicGo 自己的配置，本 Skill 完全不接触 |
| `r2`（可选） | 用 S3 兼容接口直传用户自己的 Cloudflare R2 存储桶 | 本地 `~/.weiwuming/image-host.json` 或环境变量 |

两种后端都上传到**用户自己的**图床，本 Skill 不提供也不代管任何公共图床。

## 选哪个后端

按以下顺序决定，先命中先生效：

1. 命令行 `--backend picgo|r2`
2. 环境变量 `WEIWUMING_IMAGE_BACKEND`
3. 配置文件里的 `"backend"` 字段
4. 自动：R2 五项配置齐全则用 `r2`，否则用 `picgo`

因此**不配 R2 的用户完全不受影响**，行为与以前一致。

---

# 后端一：PicGo Server

## 工作方式

`scripts/upload_image.py` 会把本地图片路径发送给用户自己的 PicGo Server，由 PicGo 当前选中的图床完成上传，再把公网 URL 返回给排版流程。

本 Skill 不保存任何具体图床的账号或密钥。用户需要先在 PicGo 中配置并选中自己的图床。

PicGo GUI 2.2+ 默认开启本地 Server：

- 上传接口：`http://127.0.0.1:36677/upload`
- 健康检查：`http://127.0.0.1:36677/heartbeat`
- 上传请求：`POST /upload`，JSON body 为 `{"list":["本地图片绝对路径"]}`
- 成功响应：`{"success":true,"result":["https://图片地址"]}`

官方文档：

- [PicGo GUI Server 用法](https://docs.picgo.app/gui/guide/advance)
- [PicGo Core API Reference](https://docs.picgo.app/core/api/)

## 第一步：配置 PicGo

1. 安装并启动 PicGo GUI，或启动支持 Server API 的 PicGo Core。
2. 在 PicGo 中配置目标图床，例如 GitHub、S3、阿里云 OSS、腾讯云 COS 等。
3. 将该图床设为当前图床。
4. 确认 PicGo Server 已启动，并记录 `/upload` 接口地址。

实际图床的账号、Bucket、Token 等都由 PicGo 管理，不写进本 Skill。

### 未配置时：PicGo Cloud OAuth（可选）

PicGo Core 2.0+ 支持 PicGo Cloud 的浏览器登录流程：本地启动一次性回调服务并打开 `https://cloud.picgo.app`，登录成功后把 token 保存在 PicGo 自己的 `settings.picgoCloud.token` 中。本 Skill 不读取或保存该 token。

```bash
python <SKILL_ROOT>/scripts/setup_picgo.py --status
python <SKILL_ROOT>/scripts/setup_picgo.py --login
```

- `--login` 等价于调用官方 `picgo login`，会打开浏览器；执行前必须征得用户确认。
- OAuth 只登录 **PicGo Cloud**。它不能替 GitHub、S3、阿里云 OSS、腾讯云 COS 等第三方图床生成凭据。
- 第三方图床使用 `python <SKILL_ROOT>/scripts/setup_picgo.py --configure-uploader`（调用 `picgo set uploader`）或 PicGo GUI 配置。
- 本地已有云端配置时，可由用户明确选择 `--sync-config` 调用 `picgo config sync`。首次同步可能把本地配置上传到 PicGo Cloud，冲突时还会要求交互选择，因此禁止自动执行。
- 若找不到 `picgo` 命令，安装 PicGo Core CLI 后再运行：`npm install -g picgo`。PicGo GUI 已配置且 Server 可用时无需安装 CLI。

官方依据：

- [PicGo CLI login / config sync](https://docs.picgo.app/core/guide/commands)
- [PicGo Cloud API](https://docs.picgo.app/core/api/#cloud)

## 第二步：配置接口

默认接口为 `http://127.0.0.1:36677/upload`。如果端口、主机或路径不同，请使用以下任一方式覆盖。

### 配置文件

创建 `~/.weiwuming/image-host.json`：

```json
{
  "picgo": {
    "api_url": "http://127.0.0.1:36677/upload",
    "server_secret": "",
    "timeout": 90
  }
}
```

- `api_url`：完整的 PicGo `/upload` 接口 URL。
- `server_secret`：可选。PicGo Server 启用鉴权时填写 shared secret。
- `timeout`：单张图片上传超时秒数，默认 `90`。

### 环境变量

环境变量优先于配置文件：

```text
PICGO_API_URL=http://127.0.0.1:36677/upload
PICGO_SERVER_SECRET=可选的服务密钥
PICGO_TIMEOUT=90
```

启用 `PICGO_SERVER_SECRET` 后，脚本按照官方 API 使用 `Authorization: Bearer <secret>` 请求头。

## 第三步：检查与上传

```bash
python <SKILL_ROOT>/scripts/upload_image.py --check
python <SKILL_ROOT>/scripts/upload_image.py images/example.jpg
python <SKILL_ROOT>/scripts/upload_image.py --json images/*.jpg
```

- `--check` 会调用 PicGo `/heartbeat`，确认接口可访问。
- 远程 `http(s)` 图片原样返回，不重复上传。
- 本地图片会转换为绝对路径后发送给 PicGo。
- 缓存保存在 `~/.weiwuming/upload-cache.json`，按后端实例和图片内容 hash 隔离；旧文件名 `picgo-upload-cache.json` 仍会被读取，升级后缓存不会失效。
- 如果沙箱不允许写入缓存，脚本会发出警告但仍返回已经上传成功的 URL，避免重试造成重复上传。
- 退出码：`0` 成功；`2` 配置无效或服务不可用；`1` 至少一张图片上传失败。

---

# 后端二：Cloudflare R2（可选）

适合不想常驻 PicGo GUI、或需要在没有桌面环境的机器上跑的用户。走 S3 兼容接口，AWS SigV4 签名，只用 Python 标准库，不需要装 boto3。

## 前提

1. 一个自己的 Cloudflare R2 存储桶。
2. 给该桶绑定一个**公开访问域名**（R2 自定义域名或 r2.dev 子域）。对象上传后靠这个域名拼出公网 URL，没有它图片仍然不可公开访问。
3. 一对 R2 的 S3 API 凭据（Access Key ID / Secret Access Key）。

## 配置

`~/.weiwuming/image-host.json`：

```json
{
  "backend": "r2",
  "r2": {
    "account_id": "你的 Cloudflare account id",
    "access_key_id": "",
    "secret_access_key": "",
    "bucket": "你的桶名",
    "domain": "https://img.example.com"
  }
}
```

或用环境变量（优先于配置文件）：

```text
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=...
R2_DOMAIN=https://img.example.com
```

五项齐全时会被自动选中；也可以显式 `--backend r2` 或 `WEIWUMING_IMAGE_BACKEND=r2`。想临时切回 PicGo 用 `--backend picgo`。

## 检查与上传

```bash
python <SKILL_ROOT>/scripts/upload_image.py --check --backend r2
python <SKILL_ROOT>/scripts/upload_image.py --backend r2 images/example.jpg
```

- `--check` 会对存储桶发一个签名 HEAD 请求，同时验证凭据有效和桶存在。
- 对象键为 `weiwuming/<内容hash前16位><后缀>`，返回 `<domain>/<对象键>`。
- 同内容的图片键相同，重复上传只是覆盖同一对象，不会堆垃圾文件。
- 远程 `http(s)` 图片原样返回，行为与 PicGo 后端一致。

## 安全须知

- R2 的 Access Key 有写权限，**以明文存在本地配置文件里**。请确保该文件不被提交到任何仓库，也不要放进会同步到公开位置的目录。
- 建议为此用途单独签发一对只对该桶有写权限的凭据，不要复用账号级密钥。
- 绑定的域名是公开的，上传即公开，不要传隐私或未公开资料。

---

## 常见问题

### 无法连接 PicGo

- 确认 PicGo 正在运行。
- 确认 Server 功能已开启。
- 核对接口端口，PicGo GUI 默认端口是 `36677`。
- 先运行 `python scripts/upload_image.py --check` 查看明确错误。

### 返回 401 Unauthorized

PicGo Server 已启用鉴权。请把同一个 shared secret 写入 `server_secret` 或 `PICGO_SERVER_SECRET`。

### PicGo 能访问但上传失败

检查 PicGo 当前图床是否已正确配置并设为启用状态，然后查看 PicGo 日志。具体图床错误由 PicGo 返回，本脚本不会接触或代管图床凭据。

如果计划使用 PicGo Cloud 且 CLI 2.0+ 已安装，可先运行 `python scripts/setup_picgo.py --status`，未登录时再经用户确认运行 `--login`。

### R2 返回 403

凭据无效或没有该桶的写权限。核对 `access_key_id` / `secret_access_key`，并确认这对凭据的权限范围覆盖目标桶。

### R2 返回 404

桶名写错，或 `account_id` 不对。`--check` 的 HEAD 请求会直接暴露这两类问题。

### R2 上传成功但图片打不开

`domain` 没有正确绑定到该桶，或桶未开启公开访问。上传本身只保证对象写入，公开可读取决于域名与桶的访问设置。

## 安全须知

- 不要把 PicGo Server 暴露到公网；优先监听 `127.0.0.1`。
- 如需监听局域网地址，应启用 Server secret 和防火墙限制。
- 不要把 secret、图床 Token 或账号密钥提交到仓库。
- 上传后的图片是公网资源，不要上传隐私或未公开图片。
