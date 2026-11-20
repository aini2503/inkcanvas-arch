#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_to_github.py —— 一键推送到 GitHub（双击 3-推送到GitHub.bat 运行）

它会：
  1. 问你的 GitHub 用户名和仓库名
  2. 配好远程地址
  3. 推送（第一次会弹浏览器让你登录 GitHub）
  4. 告诉你结果

前提：你已经在这个网址建好一个空仓库
      https://github.com/new
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent


def run(args, check=False):
    r = subprocess.run(args, cwd=str(HERE), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    print("=" * 60)
    print("   把项目推送到 GitHub")
    print("=" * 60)
    print()

    # 检查是不是 git 仓库
    code, _ = run(["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0:
        print("❌ 这个目录不是 git 仓库。")
        print("   请确认 3-推送到GitHub.bat 和这个脚本放在项目根目录。")
        return 1

    # 检查有没有提交
    code, out = run(["git", "log", "--oneline", "-1"])
    if code != 0:
        print("❌ 还没有提交记录。")
        return 1
    print(f"本地已有提交：{out.strip()}")
    print()

    print("【第 1 步】先建仓库（如果还没建）")
    print("   1. 浏览器打开  https://github.com/new")
    print("   2. Repository name 填：inkcanvas-arch")
    print("   3. 下面什么都不要勾（不要勾 README、不要勾 .gitignore）")
    print("   4. 点绿色的 Create repository")
    print("   5. 建好后这个页面可以直接关掉")
    print()
    input("   建好了，按回车继续...")
    print()

    # 问信息
    print("【第 2 步】填两个信息")
    username = input("   你的 GitHub 用户名（英文，不是邮箱）: ").strip()
    if not username:
        print("❌ 用户名不能为空")
        return 1
    if not re.fullmatch(r"[A-Za-z0-9-]+", username):
        print("❌ 用户名只能包含字母、数字、减号")
        return 1

    repo = input("   仓库名（默认 inkcanvas-arch，直接回车即可）: ").strip() or "inkcanvas-arch"

    url = f"https://github.com/{username}/{repo}.git"
    print()
    print(f"   目标仓库：{url}")
    print()

    # 配远程
    code, out = run(["git", "remote", "get-url", "origin"])
    if code == 0:
        print(f"   已有远程地址 ({out.strip()})，改为新的")
        run(["git", "remote", "set-url", "origin", url])
    else:
        run(["git", "remote", "add", "origin", url])
        print("   已设置远程地址")

    # 推送
    print()
    print("【第 3 步】推送中...")
    print("   如果弹出 GitHub 登录窗口：")
    print("     → 点「Sign in with your browser」")
    print("     → 浏览器里登录/授权")
    print("     → 回到这个黑窗口，它会自动继续")
    print()
    print("   第一次可能要等 10-60 秒，别关窗口。")
    print()

    # 用继承 stdio，让 git 的交互式登录能正常工作
    r = subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(HERE))
    print()

    if r.returncode == 0:
        print("=" * 60)
        print("   ✅ 推送成功！")
        print("=" * 60)
        print()
        print(f"   打开看看： https://github.com/{username}/{repo}")
        print()
        print("   如果仓库是 Private，别人看不到。要给别人看的话：")
        print("   仓库页 → Settings → 最下面 Danger Zone → Change visibility → Public")
        print()
        return 0

    print("=" * 60)
    print("   ❌ 推送失败")
    print("=" * 60)
    print()
    print("   常见原因：")
    print("   1. 仓库名或用户名打错了 → 重新运行本脚本再试")
    print("   2. 仓库里已经有文件（比如你勾了 Add a README）")
    print("      → 回 GitHub 把那个仓库删了，重新建一个空的")
    print("   3. 没有登录 GitHub → 再运行一次，注意弹窗要点同意")
    print("   4. 网络问题 → 挂梯子再试，或者明天再试")
    print()
    print("   还是不行，把这一整屏截图发给我。")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
