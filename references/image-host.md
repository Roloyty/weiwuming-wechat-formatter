# 图床上传配置（PicGo Server）

## 工作方式

公众号编辑器无法访问 `./images/x.jpg` 这类本地路径。`scripts/upload_image.py` 会把本地图片路径发送给用户自己的 PicGo Server，由 PicGo 当前选中的图床完成上传，再把公网 URL 返回给排版流程。

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
- 缓存保存在 `~/.weiwuming/picgo-upload-cache.json`，按 PicGo 接口和图片内容 hash 隔离。
- 如果沙箱不允许写入缓存，脚本会发出警告但仍返回已经上传成功的 URL，避免重试造成重复上传。
- 退出码：`0` 成功；`2` 配置无效或服务不可用；`1` 至少一张图片上传失败。

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

## 安全须知

- 不要把 PicGo Server 暴露到公网；优先监听 `127.0.0.1`。
- 如需监听局域网地址，应启用 Server secret 和防火墙限制。
- 不要把 secret、图床 Token 或账号密钥提交到仓库。
- 上传后的图片是公网资源，不要上传隐私或未公开图片。
