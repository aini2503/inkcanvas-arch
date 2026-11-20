#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_to_github.py —— 一键推送到 GitHub（双击 3-推送到GitHub.bat 运行）

需要：一个 GitHub Personal Access Token（脚本里有获取步骤）
Token 只在内存里用一次，不会写进 .git/config，不会留在磁盘上。
"""

from __future__ import annotations

import getpass
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent


def run(args, capture=True):
    kw = {"cwd": str(HERE), "text": True, "encoding": "utf-8", "errors": "replace"}
    if capture:
        kw["capture_output"] = True
    r = subprocess.run(args, **kw)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def main():
    print("=" * 64)
    print("   把项目推送到 GitHub")
    print("=" * 64)
    print()

    code, _ = run(["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0:
        print("❌ 这个目录不是 git 仓库。请确认 bat 和脚本在项目根目录。")
        return 1

    code, head = run(["git", "log", "--oneline", "-1"])
    if code != 0:
        print("❌ 还没有提交记录。")
        return 1
    print(f"本地提交：{head}")
    print()

    # ---------- 读取/填写仓库信息 ----------
    code, url = run(["git", "remote", "get-url", "origin"])
    default_user, default_repo = "", "inkcanvas-arch"
    if code == 0 and "github.com" in url:
        m = re.search(r"github\.com[/:]([^/]+)/([^/.]+)", url)
        if m:
            default_user, default_repo = m.group(1), m.group(2)
        print(f"已配置仓库：https://github.com/{default_user}/{default_repo}")
        print()

    print("【第 1 步】仓库地址")
    u = input(f"   GitHub 用户名 [{default_user or '必填'}]: ").strip() or default_user
    if not u:
        print("❌ 用户名不能为空")
        return 1
    r = input(f"   仓库名 [{default_repo}]: ").strip() or default_repo
    repo_url = f"https://github.com/{u}/{r}.git"
    print(f"   → {repo_url}")
    print()

    # ---------- Token ----------
    print("【第 2 步】Token")
    print("   如果还没有，按这个做（1 分钟）：")
    print("     1. 浏览器打开  https://github.com/settings/tokens/new")
    print("     2. Note 随便填，比如 inkcanvas-upload")
    print("     3. Expiration 选 30 days")
    print("     4. 下面勾选框里，只勾最上面那个  repo")
    print("     5. 拉到最下面点 Generate token")
    print("     6. 复制那一串 ghp_ 开头的字符（只显示一次！）")
    print()
    print("   粘贴时看不到字符是正常的（防偷看），粘完直接回车。")
    print()
    token = getpass.getpass("   Token: ").strip()
    if not token:
        print("❌ Token 为空")
        return 1
    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        print("⚠️  这看起来不像 GitHub Token（通常以 ghp_ 或 github_pat_ 开头）")
        if input("   仍然继续？(y/N): ").strip().lower() != "y":
            return 1
    print()

    # ---------- 配置远程（临时带 token） ----------
    auth_url = f"https://{token}@github.com/{u}/{r}.git"
    code, _ = run(["git", "remote", "get-url", "origin"])
    if code == 0:
        run(["git", "remote", "set-url", "origin", auth_url])
    else:
        run(["git", "remote", "add", "origin", auth_url])

    print("【第 3 步】推送中...")
    print()

    push_ok = False
    try:
        rc, out = run(["git", "push", "-u", "origin", "main"])
        if rc == 0:
            push_ok = True
            for line in out.splitlines()[-6:]:
                print("   " + line)
        else:
            print("   失败输出：")
            for line in out.splitlines()[:10]:
                # 别把 token 打出来
                print("   " + line.replace(token, "***"))
    finally:
        # 无论如何，把 token 从 .git/config 里清掉
        run(["git", "remote", "set-url", "origin", repo_url])
        print()
        print("   （Token 已从本地配置中清除）")

    print()
    if push_ok:
        print("=" * 64)
        print("   ✅ 推送成功！")
        print("=" * 64)
        print()
        print(f"   打开看看： https://github.com/{u}/{r}")
        print()
        return 0

    print("=" * 64)
    print("   ❌ 没有推成功")
    print("=" * 64)
    print()
    print("   对照下面的症状：")
    print()
    print("   · 401 / Authentication failed")
    print("     → Token 复制错了或过期了，重新生成一个再试")
    print()
    print("   · 403 / Permission denied")
    print("     → Token 没勾 repo 权限，重新生成，勾上 repo")
    print()
    print("   · 404 / Repository not found")
    print("     → 仓库名或用户名打错了；或者仓库还没建")
    print()
    print("   · 502 / 连接失败")
    print("     → 加速器又改回 hosts 了，找我要修复脚本")
    print()
    print("   · 其他")
    print("     → 把这一整屏截图发给我")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
