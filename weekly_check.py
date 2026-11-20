#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weekly_check.py —— 每周五检查（由 3-周五检查.bat 调用）

一次做完：
  1. 跑三项自检
  2. 生成 contracts/互通检查-YYYY-MM-DD.md（A1/A2 已填真数据，其余留空给两个组）
  3. 在屏幕上告诉你三行结论 + 下周一该找谁要什么
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
PY = sys.executable
TODAY = time.strftime("%Y-%m-%d")
WEEKDAY = time.strftime("%A")


def run(args, timeout=180):
    cmd = [PY] + [str(HERE / args[0])] + args[1:]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, str(e)


def grab(out: str, pattern: str) -> str:
    for line in out.splitlines():
        if pattern in line:
            return line.strip()
    return ""


def main():
    print("=" * 58)
    print(f"   InkCanvas · 每周检查   {TODAY} ({WEEKDAY})")
    print("=" * 58)

    checks = [
        ("格式检查（.icink 契约）", ["contracts/tools/selftest.py"], "12/12"),
        ("AI 网关", ["gateway/server.py", "--selftest"], "10/10"),
        ("黄金测试向量", ["contracts/tools/gen_golden.py", "--check"], "通过"),
    ]

    results, details = [], {}
    for name, args, expect in checks:
        print(f"\n【{name}】正在跑…")
        ok, out = run(args)
        results.append((name, ok))
        details[name] = out
        print(f"   {'✅ 通过' if ok else '❌ 不通过'}" + (f"（应为 {expect}）" if ok else ""))
        if not ok:
            for line in out.strip().splitlines()[-8:]:
                print("      " + line)

    allok = all(ok for _, ok in results)

    # ---- 生成互通检查表 ----
    tpl = HERE / "templates" / "每周五互通检查表.md"
    out_md = HERE / "contracts" / f"互通检查-{TODAY}.md"
    if tpl.exists():
        text = tpl.read_text(encoding="utf-8")
        text = text.replace("2026-__-__", TODAY)
        lines = []
        for name, ok in results:
            lines.append(f"- **{name}**：{'✅ 通过' if ok else '❌ 不通过'}")
        block = "### 本机自检结果（自动填入）\n\n" + "\n".join(lines) + "\n"
        text = text.replace("## A. 文件格式（自动跑，别手填）",
                            "## A. 文件格式（自动跑，别手填）\n\n" + block)
        out_md.write_text(text, encoding="utf-8")
        print(f"\n📄 已生成检查表：contracts/互通检查-{TODAY}.md")
        # 顺手在桌面放一份，方便发群
        try:
            desk = Path.home() / "Desktop"
            if desk.exists():
                shutil.copy2(out_md, desk / f"互通检查-{TODAY}.md")
                print(f"📄 桌面也放了一份：互通检查-{TODAY}.md")
        except Exception:
            pass

    # ---- 结论 ----
    print("\n" + "=" * 58)
    if allok:
        print("   ✅ 三项全部通过")
    else:
        bad = [n for n, ok in results if not ok]
        print(f"   ❌ 有 {len(bad)} 项不通过：{'、'.join(bad)}")

    print("\n   这周要做的事：")
    print("   1. 把「互通检查-今天.md」发到群里")
    print("   2. 让刘子琦填 Windows 那半（跑 validate.py --digest 贴结果）")
    print("   3. 让顾天宇填鸿蒙那半（同上）")
    print("   4. 两边填完，用 --compare 比一次，不一致就进下周一议题")
    print("=" * 58)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
