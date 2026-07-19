#!/usr/bin/env python3
"""通过用户配置的 PicGo Server API 上传图片并返回公网 URL。

公众号编辑器无法访问本地图片路径。本脚本把本地图片路径交给 PicGo，
由用户在 PicGo 中选择并配置实际图床，再把 PicGo 返回的公网 URL 写入文章。

用法:
    upload_image.py <图1> [图2 ...]       # 输出「本地路径<TAB>公网URL」
    upload_image.py --json <图...>         # 输出 JSON: {"本地路径": "URL", ...}
    upload_image.py --check                # 检查配置并调用 PicGo heartbeat

配置来源（环境变量优先）:
  A. 环境变量:
       PICGO_API_URL=http://127.0.0.1:36677/upload
       PICGO_SERVER_SECRET=可选的服务密钥
       PICGO_TIMEOUT=90
  B. 本地配置文件 ~/.weiwuming/image-host.json:
       {"picgo":{"api_url":"http://127.0.0.1:36677/upload",
                  "server_secret":"","timeout":90}}

PicGo GUI 默认接口是 http://127.0.0.1:36677/upload。用户必须先在 PicGo
中配置并选中自己的图床，同时保持 PicGo Server 正在运行。若服务启用了
鉴权，脚本使用 Authorization: Bearer <server_secret>。

行为:
  - http/https 远程 URL 原样返回，不重复上传
  - 本地图通过 POST /upload 的 JSON {"list": ["绝对路径"]} 上传
  - 本地缓存 ~/.weiwuming/picgo-upload-cache.json，按接口和内容 hash 隔离
  - 单张失败不影响其余图片

退出码: 0 成功 / 2 配置无效或 PicGo 服务不可用 / 1 有图片上传失败。
"""

from __future__ import annotations

import hashlib
import json
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
CACHE_FILE = HOME_CFG / "picgo-upload-cache.json"
DEFAULT_API_URL = "http://127.0.0.1:36677/upload"
DEFAULT_TIMEOUT = 90.0


class PicGoError(RuntimeError):
    """PicGo 配置、连接或响应错误。"""


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


def load_config() -> dict[str, Any]:
    raw = _read_json(CONFIG_FILE)
    picgo = raw.get("picgo", {})
    if not isinstance(picgo, dict):
        picgo = {}
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


def file_hash(filepath: str) -> str:
    digest = hashlib.sha256()
    with open(filepath, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_key(config: dict[str, Any], filepath: str) -> str:
    endpoint = config["api_url"].rstrip("/")
    return hashlib.sha256(f"{endpoint}\0{file_hash(filepath)}".encode()).hexdigest()


def load_cache() -> dict[str, str]:
    raw = _read_json(CACHE_FILE)
    return {str(key): value for key, value in raw.items() if isinstance(value, str)}


def save_cache(cache: dict[str, str]) -> None:
    HOME_CFG.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def upload_one(path: str, config: dict[str, Any], cache: dict[str, str]) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    key = cache_key(config, path)
    if key in cache:
        return cache[key]
    url = picgo_upload(config, path)
    cache[key] = url
    return url


def main() -> int:
    args = sys.argv[1:]
    as_json = "--json" in args
    check = "--check" in args
    files = [arg for arg in args if not arg.startswith("--")]
    config = load_config()

    if check:
        try:
            check_picgo(config)
        except PicGoError as exc:
            print(f"✗ PicGo 检查失败：{exc}", file=sys.stderr)
            print(f"  配置文件：{CONFIG_FILE}", file=sys.stderr)
            return 2
        auth = "已启用" if config["server_secret"] else "未启用"
        print(f"✓ PicGo Server 可用 | api={config['api_url']} | 鉴权={auth}")
        print(f"缓存文件: {CACHE_FILE}")
        return 0

    if not files:
        print("用法: upload_image.py <图片...> | --check | --json <图片...>", file=sys.stderr)
        return 2

    try:
        validate_config(config)
    except PicGoError as exc:
        print(f"✗ PicGo 配置无效：{exc}", file=sys.stderr)
        print(f"  请设置 PICGO_API_URL 或修改 {CONFIG_FILE}", file=sys.stderr)
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
