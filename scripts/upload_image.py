#!/usr/bin/env python3
"""把本地图片传到图床并返回公网 URL，供公众号文章引用。

公众号编辑器无法访问本地图片路径，所以本地图必须先换成公网 URL。
本脚本支持两种后端，默认走 PicGo：

  picgo（默认）
      把路径交给用户自己的 PicGo Server，由用户在 PicGo 里选择实际图床。
      脚本不接触任何图床凭据。
  r2（可选）
      直接用 S3 兼容接口传到用户自己的 Cloudflare R2 存储桶。适合不想常驻
      PicGo GUI、或需要在无桌面环境里跑的用户。凭据只保存在本地配置中。

用法:
    upload_image.py <图1> [图2 ...]       # 输出「本地路径<TAB>公网URL」
    upload_image.py --json <图...>         # 输出 JSON: {"本地路径": "URL", ...}
    upload_image.py --check                # 检查当前后端是否可用
    upload_image.py --backend r2 <图...>   # 本次强制使用指定后端

后端选择顺序:
  1. 命令行 --backend picgo|r2
  2. 环境变量 WEIWUMING_IMAGE_BACKEND
  3. 配置文件里的 "backend" 字段
  4. 自动：R2 五项配置齐全则用 r2，否则用 picgo

配置来源（环境变量优先于配置文件）:
  A. 环境变量:
       PICGO_API_URL=http://127.0.0.1:36677/upload
       PICGO_SERVER_SECRET=可选的服务密钥
       PICGO_TIMEOUT=90
       R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY
       R2_BUCKET / R2_DOMAIN
  B. 本地配置文件 ~/.weiwuming/image-host.json:
       {"backend": "picgo",
        "picgo": {"api_url": "http://127.0.0.1:36677/upload",
                   "server_secret": "", "timeout": 90},
        "r2": {"account_id": "", "access_key_id": "", "secret_access_key": "",
                "bucket": "", "domain": "https://img.example.com"}}

PicGo GUI 默认接口是 http://127.0.0.1:36677/upload。用户必须先在 PicGo
中配置并选中自己的图床，同时保持 PicGo Server 正在运行。若服务启用了
鉴权，脚本使用 Authorization: Bearer <server_secret>。

R2 走 AWS SigV4 签名的 S3 兼容接口（region 固定为 auto），对象键为
weiwuming/<内容hash>.<后缀>，返回 <domain>/<对象键>。domain 应是绑定到
该存储桶的公开访问域名。

行为:
  - http/https 远程 URL 原样返回，不重复上传
  - 本地缓存 ~/.weiwuming/upload-cache.json，按后端与内容 hash 隔离；
    找不到时回落读取旧文件名 picgo-upload-cache.json，避免升级后缓存失效
  - 单张失败不影响其余图片

退出码: 0 成功 / 2 配置无效或服务不可用 / 1 有图片上传失败。
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


HOME_CFG = Path.home() / ".weiwuming"
CONFIG_FILE = HOME_CFG / "image-host.json"
CACHE_FILE = HOME_CFG / "upload-cache.json"
LEGACY_CACHE_FILE = HOME_CFG / "picgo-upload-cache.json"
DEFAULT_API_URL = "http://127.0.0.1:36677/upload"
DEFAULT_TIMEOUT = 90.0

BACKENDS = ("picgo", "r2")
R2_KEY_PREFIX = "weiwuming"
R2_REQUIRED_KEYS = ("account_id", "access_key_id", "secret_access_key", "bucket", "domain")
R2_TIMEOUT = 120.0
# 仅为测试留的接缝：真实环境永远是 https，测试里指向本地 http 服务
R2_SCHEME = "https"


class PicGoError(RuntimeError):
    """PicGo 配置、连接或响应错误。"""


class R2Error(RuntimeError):
    """R2 配置、连接或响应错误。"""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _positive_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT
    return timeout if timeout > 0 else DEFAULT_TIMEOUT


def _section(name: str) -> dict[str, Any]:
    section = _read_json(CONFIG_FILE).get(name, {})
    return section if isinstance(section, dict) else {}


def load_config() -> dict[str, Any]:
    """PicGo 后端配置。保持原有返回结构，调用方与测试都依赖它。"""
    picgo = _section("picgo")
    return {
        "api_url": (
            os.environ.get("PICGO_API_URL")
            or picgo.get("api_url")
            or DEFAULT_API_URL
        ).strip(),
        "server_secret": (
            os.environ.get("PICGO_SERVER_SECRET")
            or picgo.get("server_secret")
            or ""
        ).strip(),
        "timeout": _positive_timeout(
            os.environ.get("PICGO_TIMEOUT") or picgo.get("timeout")
        ),
    }


def load_r2_config() -> dict[str, Any]:
    r2 = _section("r2")
    return {
        key: (os.environ.get(f"R2_{key.upper()}") or r2.get(key) or "").strip()
        for key in R2_REQUIRED_KEYS
    }


def r2_missing_keys(config: dict[str, Any]) -> list[str]:
    return [key for key in R2_REQUIRED_KEYS if not config.get(key)]


def select_backend(explicit: str | None = None) -> str:
    """决定用哪个后端。R2 属于自带凭据的可选项，只有配全了才会被自动选中。"""
    for candidate in (explicit, os.environ.get("WEIWUMING_IMAGE_BACKEND"), _read_json(CONFIG_FILE).get("backend")):
        if isinstance(candidate, str) and candidate.strip():
            name = candidate.strip().lower()
            if name not in BACKENDS:
                raise ValueError(f"未知的图床后端 {name!r}，可选：{', '.join(BACKENDS)}")
            return name
    return "r2" if not r2_missing_keys(load_r2_config()) else "picgo"


def validate_config(config: dict[str, Any]) -> None:
    parsed = urllib.parse.urlsplit(str(config.get("api_url", "")))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PicGoError("PICGO_API_URL 必须是有效的 http(s) URL。")
    if not parsed.path.rstrip("/").endswith("/upload"):
        raise PicGoError("PICGO_API_URL 必须指向 PicGo 的 /upload 接口。")


def heartbeat_url(api_url: str) -> str:
    parsed = urllib.parse.urlsplit(api_url)
    path = parsed.path.rstrip("/")
    path = path[: -len("/upload")] + "/heartbeat"
    return urllib.parse.urlunsplit(parsed._replace(path=path, query="", fragment=""))


def request_headers(config: dict[str, Any], *, json_body: bool = False) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if json_body:
        headers["Content-Type"] = "application/json"
    if config.get("server_secret"):
        headers["Authorization"] = f"Bearer {config['server_secret']}"
    return headers


def _request_json(url: str, config: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers=request_headers(config, json_body=payload is not None),
    )
    try:
        with urllib.request.urlopen(request, timeout=config["timeout"]) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise PicGoError(f"PicGo 返回 HTTP {exc.code}{suffix}") from exc
    except urllib.error.URLError as exc:
        raise PicGoError(f"无法连接 PicGo：{exc.reason}") from exc
    except TimeoutError as exc:
        raise PicGoError("连接 PicGo 超时。") from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PicGoError("PicGo 返回的内容不是有效 JSON。") from exc
    if not isinstance(result, dict):
        raise PicGoError("PicGo 返回的 JSON 结构无效。")
    return result


def check_picgo(config: dict[str, Any]) -> None:
    validate_config(config)
    response = _request_json(heartbeat_url(config["api_url"]), config, None)
    if response.get("success") is not True:
        raise PicGoError(str(response.get("message") or "PicGo heartbeat 失败。"))


def _extract_url(response: dict[str, Any]) -> str:
    if response.get("success") is not True:
        raise PicGoError(str(response.get("message") or "PicGo 上传失败。"))
    result = response.get("result")
    if not isinstance(result, list) or not result:
        raise PicGoError("PicGo 上传成功响应中没有 result URL。")
    value = result[0]
    if isinstance(value, dict):
        value = value.get("imgUrl") or value.get("url")
    if not isinstance(value, str) or not value.startswith(("http://", "https://")):
        raise PicGoError("PicGo 返回的图片地址不是有效的 http(s) URL。")
    return value


def picgo_upload(config: dict[str, Any], filepath: str) -> str:
    validate_config(config)
    absolute_path = str(Path(filepath).resolve())
    response = _request_json(config["api_url"], config, {"list": [absolute_path]})
    return _extract_url(response)


# ---------- R2（S3 兼容接口，AWS SigV4） ----------

def r2_validate(config: dict[str, Any]) -> None:
    missing = r2_missing_keys(config)
    if missing:
        raise R2Error("R2 配置缺少：" + "、".join(missing))


def r2_endpoint(config: dict[str, Any]) -> str:
    return f"{config['account_id']}.r2.cloudflarestorage.com"


def r2_public_url(config: dict[str, Any], key: str) -> str:
    domain = str(config["domain"]).rstrip("/")
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain
    return f"{domain}/{key}"


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def _r2_signing_key(secret: str, date_stamp: str, region: str, service: str) -> bytes:
    key = _hmac_sha256(("AWS4" + secret).encode(), date_stamp)
    key = _hmac_sha256(key, region)
    key = _hmac_sha256(key, service)
    return _hmac_sha256(key, "aws4_request")


def _r2_request(
    config: dict[str, Any],
    method: str,
    path: str,
    body: bytes = b"",
    content_type: str | None = None,
) -> int:
    """对 R2 发一个 SigV4 签名请求，返回 HTTP 状态码。"""
    r2_validate(config)
    host = r2_endpoint(config)
    canonical_uri = "/" + urllib.parse.quote(path.lstrip("/"), safe="/")
    region, service = "auto", "s3"
    payload_hash = hashlib.sha256(body).hexdigest()

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    if content_type:
        headers["content-type"] = content_type
    signed_headers = ";".join(sorted(headers))
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
    canonical_request = (
        f"{method}\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )

    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )
    signing_key = _r2_signing_key(config["secret_access_key"], date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    send_headers = {name: value for name, value in headers.items() if name != "host"}
    send_headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={config['access_key_id']}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    request = urllib.request.Request(
        f"{R2_SCHEME}://{host}{canonical_uri}",
        data=body if method in {"PUT", "POST"} else None,
        method=method,
        headers=send_headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=R2_TIMEOUT) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        # R2 的报错正文是 XML，直接抛太长，取前 200 字够定位问题
        suffix = f": {detail[:200]}" if detail else ""
        raise R2Error(f"R2 返回 HTTP {exc.code}{suffix}") from exc
    except urllib.error.URLError as exc:
        raise R2Error(f"无法连接 R2：{exc.reason}") from exc
    except TimeoutError as exc:
        raise R2Error("连接 R2 超时。") from exc


def check_r2(config: dict[str, Any]) -> None:
    """对存储桶发一个签名 HEAD，同时验证凭据有效和桶存在。"""
    _r2_request(config, "HEAD", config["bucket"])


def r2_object_key(filepath: str) -> str:
    digest = file_hash(filepath)[:16]
    extension = os.path.splitext(filepath)[1].lower() or ".jpg"
    return f"{R2_KEY_PREFIX}/{digest}{extension}"


def r2_upload(config: dict[str, Any], filepath: str) -> str:
    r2_validate(config)
    key = r2_object_key(filepath)
    content_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    body = Path(filepath).read_bytes()
    _r2_request(config, "PUT", f"{config['bucket']}/{key}", body, content_type)
    return r2_public_url(config, key)


# ---------- 缓存 ----------

def file_hash(filepath: str) -> str:
    digest = hashlib.sha256()
    with open(filepath, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_r2_config(config: dict[str, Any]) -> bool:
    return "account_id" in config


def cache_key(config: dict[str, Any], filepath: str) -> str:
    """按后端实例隔离缓存，换了图床不会命中旧 URL。"""
    if _is_r2_config(config):
        endpoint = f"r2:{config.get('bucket', '')}@{config.get('domain', '')}"
    else:
        endpoint = config["api_url"].rstrip("/")
    return hashlib.sha256(f"{endpoint}\0{file_hash(filepath)}".encode()).hexdigest()


def load_cache() -> dict[str, str]:
    raw = _read_json(CACHE_FILE) or _read_json(LEGACY_CACHE_FILE)
    return {str(key): value for key, value in raw.items() if isinstance(value, str)}


def save_cache(cache: dict[str, str]) -> bool:
    """Persist cache when possible without discarding successful upload results.

    Sandboxed runners may allow the upload request but deny writes under the user's home
    directory. Cache failure must not turn an already-successful upload into a failed run,
    otherwise a retry uploads the same files again.
    """
    try:
        HOME_CFG.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"⚠ 上传已完成，但缓存写入失败：{CACHE_FILE} ({exc})", file=sys.stderr)
        return False
    return True


def upload_one(path: str, config: dict[str, Any], cache: dict[str, str]) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    key = cache_key(config, path)
    if key in cache:
        return cache[key]
    url = r2_upload(config, path) if _is_r2_config(config) else picgo_upload(config, path)
    cache[key] = url
    return url


def _pop_option(args: list[str], name: str) -> str | None:
    """取出 --name value 或 --name=value，并从 args 中移除。"""
    for index, arg in enumerate(args):
        if arg == name and index + 1 < len(args):
            value = args[index + 1]
            del args[index : index + 2]
            return value
        if arg.startswith(name + "="):
            value = arg.split("=", 1)[1]
            del args[index]
            return value
    return None


def main() -> int:
    args = sys.argv[1:]
    backend_option = _pop_option(args, "--backend")
    as_json = "--json" in args
    check = "--check" in args
    files = [arg for arg in args if not arg.startswith("--")]

    try:
        backend = select_backend(backend_option)
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2

    config = load_r2_config() if backend == "r2" else load_config()
    error_type = R2Error if backend == "r2" else PicGoError

    if check:
        try:
            if backend == "r2":
                check_r2(config)
            else:
                check_picgo(config)
        except error_type as exc:
            print(f"✗ {backend} 检查失败：{exc}", file=sys.stderr)
            print(f"  配置文件：{CONFIG_FILE}", file=sys.stderr)
            return 2
        if backend == "r2":
            print(f"✓ R2 可用 | bucket={config['bucket']} | 域名={config['domain']}")
        else:
            auth = "已启用" if config["server_secret"] else "未启用"
            print(f"✓ PicGo Server 可用 | api={config['api_url']} | 鉴权={auth}")
        print(f"缓存文件: {CACHE_FILE}")
        return 0

    if not files:
        print(
            "用法: upload_image.py <图片...> | --check | --json <图片...> | --backend picgo|r2",
            file=sys.stderr,
        )
        return 2

    try:
        if backend == "r2":
            r2_validate(config)
        else:
            validate_config(config)
    except (PicGoError, R2Error) as exc:
        print(f"✗ {backend} 配置无效：{exc}", file=sys.stderr)
        print(f"  请检查环境变量或修改 {CONFIG_FILE}", file=sys.stderr)
        return 2

    cache = load_cache()
    result: dict[str, str] = {}
    failed: list[tuple[str, str]] = []
    for path in files:
        try:
            result[path] = upload_one(path, config, cache)
        except Exception as exc:  # 单张失败不影响其余
            failed.append((path, str(exc)))
    save_cache(cache)

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for path, url in result.items():
            print(f"{path}\t{url}")
    for path, error in failed:
        print(f"✗ 上传失败 {path}: {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
