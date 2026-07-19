#!/usr/bin/env python3
"""PicGo Core CLI setup helper.

This helper never stores credentials itself. It delegates optional interactive actions to
the official ``picgo`` CLI:

    setup_picgo.py --status
    setup_picgo.py --login
    setup_picgo.py --configure-uploader
    setup_picgo.py --sync-config

Exit codes: 0 success / 1 delegated command failed / 2 CLI missing or unsupported.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def find_picgo() -> str | None:
    override = os.environ.get("PICGO_CLI", "").strip()
    if override:
        candidate = Path(override).expanduser()
        return str(candidate) if candidate.is_file() else None
    return shutil.which("picgo")


def run_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def version_of(cli: str) -> tuple[str, int | None]:
    result = run_capture([cli, "--version"])
    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(output or "无法读取 PicGo 版本")
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    return output, int(match.group(1)) if match else None


def delegate(cli: str, args: list[str]) -> int:
    try:
        return subprocess.run([cli, *args], check=False).returncode
    except OSError as exc:
        print(f"PicGo 命令启动失败：{exc}", file=sys.stderr)
        return 1


def show_status(cli: str, version: str, major: int | None) -> int:
    print(f"PicGo CLI: {cli}")
    print(f"Version: {version}")
    if major is None:
        print("无法判断主版本；请运行 `picgo -h` 确认是否支持 login。")
        return 0
    if major < 2:
        print("当前版本不支持 PicGo Cloud 浏览器登录；需要 PicGo Core 2.0+。")
        return 2
    if major < 3:
        print("PicGo Core 2.x 支持 `picgo login`，但没有非交互式 cloud auth status 命令。")
        return 0

    auth = subprocess.run(
        [cli, "cloud", "auth", "status", "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    message = (auth.stdout or auth.stderr).strip()
    print(f"Cloud auth: {message or 'unknown'}")

    uploader = run_capture([cli, "get", "uploader", "--format", "json"])
    uploader_message = (uploader.stdout or uploader.stderr).strip()
    print(f"Uploader: {uploader_message or 'unknown'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="检查或引导配置官方 PicGo Core CLI")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--status", action="store_true", help="检查 CLI、Cloud 登录状态和当前 uploader")
    actions.add_argument("--login", action="store_true", help="调用 picgo login，启动官方浏览器 OAuth")
    actions.add_argument(
        "--configure-uploader",
        action="store_true",
        help="调用 picgo set uploader，交互配置第三方图床",
    )
    actions.add_argument(
        "--sync-config",
        action="store_true",
        help="调用 picgo config sync；可能上传本地配置并要求解决冲突",
    )
    args = parser.parse_args()

    cli = find_picgo()
    if not cli:
        print(
            "未找到 PicGo Core CLI。可运行 `npm install -g picgo`；"
            "若 PicGo GUI 的 Server 已可用，则无需安装 CLI。",
            file=sys.stderr,
        )
        return 2

    try:
        version, major = version_of(cli)
    except RuntimeError as exc:
        print(f"PicGo CLI 检查失败：{exc}", file=sys.stderr)
        return 2

    if args.login:
        if major is not None and major < 2:
            print("PicGo Cloud OAuth 需要 PicGo Core 2.0+。", file=sys.stderr)
            return 2
        print("即将调用官方 `picgo login`。登录 token 由 PicGo 自己保存，本脚本不会读取。")
        return delegate(cli, ["login"])
    if args.configure_uploader:
        return delegate(cli, ["set", "uploader"])
    if args.sync_config:
        if major is not None and major < 2:
            print("PicGo Cloud config sync 需要 PicGo Core 2.0+。", file=sys.stderr)
            return 2
        print("警告：首次同步可能上传本地 PicGo 配置；冲突时请人工选择。")
        return delegate(cli, ["config", "sync"])
    return show_status(cli, version, major)


if __name__ == "__main__":
    raise SystemExit(main())
