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

## 安全须知

- 不要把 PicGo Server 暴露到公网；优先监听 `127.0.0.1`。
- 如需监听局域网地址，应启用 Server secret 和防火墙限制。
- 不要把 secret、图床 Token 或账号密钥提交到仓库。
- 上传后的图片是公网资源，不要上传隐私或未公开图片。
