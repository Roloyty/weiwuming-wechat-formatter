#!/usr/bin/env python3
"""给没配过图床的用户用的配置引导。

    setup_image_host.py                      # 打印小白配置步骤和申请链接
    setup_image_host.py --provider imgbb     # 看备用图床的步骤
    setup_image_host.py --save               # 保存密钥（终端里隐藏输入，也可从标准输入读）
    setup_image_host.py --save --provider imgbb

--save 会先校验密钥，再传一张 1 像素测试图走通上传，都通过才写入
~/.weiwuming/image-host.json。密钥只从标准输入读，避免留在命令行历史和进程列表里，
脚本也不会把它打印出来。

退出码: 0 成功 / 1 密钥无效或输入有误 / 2 网络或图床不可用。
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import upload_image

GUIDES: dict[str, dict[str, Any]] = {
    "superbed": {
        "role": "推荐",
        "why": "支持微信扫码登录，有中文界面；免费 500 MB，每小时可传 100 张。",
        "steps": [
            "打开 https://www.superbed.cn/login ，点「微信扫码登录」。不用微信的话，点页面底部「立即注册」用邮箱注册。",
            "登录后打开 https://www.superbed.cn/dashboard/settings ，找到「API密钥管理」，生成并复制 API Key。",
        ],
    },
    "imgbb": {
        "role": "备用",
        "why": "海外老牌图床，单张最大 32 MB。聚合图床用不了时再换它；页面是英文，需要邮箱注册。",
        "steps": [
            "打开 https://imgbb.com/signup 注册账号并登录。",
            "打开 https://api.imgbb.com/ ，点「Get API key」，复制显示的 API key。",
        ],
    },
}

# 1x1 透明 PNG，只用来走通一次真实上传
TEST_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def script_command(provider: str) -> str:
    return f'python "{Path(__file__).resolve()}" --save --provider {provider}'


def print_guide(provider: str) -> None:
    guide = GUIDES[provider]
    label = upload_image.TOKEN_PROVIDERS[provider]["label"]
    print("【图床是什么】")
    print("把图片放到网上、换来一个网址的地方。公众号后台只认网址，认不出你电脑里的图片，")
    print("所以书封、人物照要先传到图床，文章里才显示得出来。")
    print()
    print(f"【{guide['role']}：{label}】{guide['why']}")
    print()
    for index, step in enumerate(guide["steps"], start=1):
        print(f"第 {index} 步：{step}")
    print(f"第 {len(guide['steps']) + 1} 步：保存密钥，二选一：")
    print("  · 用 AI 助手排版的，把密钥发给它，它会帮你存好。")
    print(f"  · 想自己操作的，在终端运行下面这条命令，粘贴密钥后回车（输入时看不到字符，是正常的）：")
    print(f"    {script_command(provider)}")
    print()
    print("【请注意】")
    print("· 密钥相当于这个图床账号的上传钥匙，只存在你自己电脑上，不要发到公开场合；泄露了可以回到第 2 步的页面重新生成。")
    print("· 传上去的图片任何人拿到网址都能看，不要传隐私图片。")
    print("· 这是别人运营的第三方服务，额度和规则可能调整，原图请自己留一份。")


def read_token() -> str:
    if sys.stdin is not None and sys.stdin.isatty():
        raw = getpass.getpass("粘贴密钥后回车（输入时看不到字符）：")
    else:
        raw = sys.stdin.read()
    return raw.strip().lstrip("﻿").strip()


def verify_public_url(url: str) -> str | None:
    """确认图片网址真的打得开。返回问题描述，没问题返回 None。"""
    request = urllib.request.Request(url, headers={"User-Agent": upload_image.TOKEN_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"打不开（{getattr(exc, 'reason', exc)}）"
    if not content_type.startswith("image/"):
        return f"返回的不是图片（{content_type or '没有类型'}）"
    return None


def trial_upload(config: dict[str, Any]) -> str:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "weiwuming-setup-test.png"
        path.write_bytes(TEST_PNG)
        return upload_image.token_upload(config, str(path))


def write_config(provider: str, token: str) -> str | None:
    """写入配置，保留其他后端的设置。返回被替换掉的默认后端。"""
    config_file = upload_image.CONFIG_FILE
    existing: dict[str, Any] = {}
    if config_file.exists():
        # 解析失败时绝不能覆盖：里面可能有用户别的凭据
        existing = json.loads(config_file.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            raise ValueError("顶层不是 JSON 对象")
    previous = existing.get("backend")
    section = existing.get(provider)
    section = section if isinstance(section, dict) else {}
    existing[provider] = {**section, "token": token}
    existing["backend"] = provider

    config_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_file.with_name(config_file.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(json.dumps(existing, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, config_file)
    return previous if isinstance(previous, str) and previous != provider else None


def save(provider: str) -> int:
    label = upload_image.TOKEN_PROVIDERS[provider]["label"]
    token = read_token()
    if not token or any(char.isspace() for char in token):
        print("✗ 没读到有效的密钥。请确认只复制了密钥本身，中间没有空格或换行。", file=sys.stderr)
        return 1

    config = {"provider": provider, "token": token}
    try:
        upload_image.check_token(config)
        public_url = trial_upload(config)
    except upload_image.TokenAuthError as exc:
        print(f"✗ {exc}配置没有保存。请回到申请页面重新复制一次。", file=sys.stderr)
        return 1
    except upload_image.TokenHostError as exc:
        print(f"✗ 没能走通上传，配置没有保存：{exc}", file=sys.stderr)
        return 2

    try:
        previous = write_config(provider, token)
    except (OSError, ValueError) as exc:
        print(f"✗ 上传没问题，但写不了配置文件 {upload_image.CONFIG_FILE}：{exc}", file=sys.stderr)
        print("  文件没有改动。如果它已损坏，请修好或移走后再运行一次。", file=sys.stderr)
        return 2

    print(f"✓ {label} 配置成功，测试图已上传。")
    print(f"  配置文件：{upload_image.CONFIG_FILE}")
    if previous:
        print(f"  默认图床已从 {previous} 切换为 {provider}。")
    problem = verify_public_url(public_url)
    if problem:
        print(f"⚠ 测试图的网址暂时{problem}，可能是当前网络或代理的原因：{public_url}", file=sys.stderr)
        print("  配置已保存。如果粘贴进公众号后图片也显示不出来，请换备用图床。", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="配置谓无名排版用的图床")
    parser.add_argument("--provider", choices=sorted(upload_image.TOKEN_PROVIDERS), default="superbed")
    parser.add_argument("--save", action="store_true", help="校验并保存密钥（从终端或标准输入读取）")
    args = parser.parse_args()
    if args.save:
        return save(args.provider)
    print_guide(args.provider)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
