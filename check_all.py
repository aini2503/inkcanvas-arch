#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_all.py —— 一键检查（由 1-一件检查.bat 调用）

小白友好：只输出「通过 / 不通过」，不通过才给细节。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
PY = sys.executable

ITEMS = [
    ("文件格式检查（.icink 契约）", ["contracts/tools/selftest.py"], "12/12"),
    ("AI 网关检查", ["gateway/server.py", "--selftest"], "10/10"),
    ("测试样本检查", ["contracts/tools/gen_golden.py", "--check"], "全部向量"),
]


def run(args) -> tuple[bool, str]:
    cmd = [PY] + [str(HERE / args[0])] + args[1:]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "超时（超过 3 分钟没跑完）"
    except Exception as e:
        return False, f"启动失败：{e}"


def main():
    print("=" * 56)
    print("   InkCanvas 项目 · 一键检查")
    print("=" * 56)

    results = []
    for i, (name, args, expect) in enumerate(ITEMS, 1):
        print(f"\n【第 {i} 项】 {name}")
        print("-" * 56)
        ok, out = run(args)
        results.append((name, ok, out))
        if ok:
            print(f"   ✅ 通过（{expect} 全部正常）")
        else:
            print("   ❌ 不通过，下面是要给我的信息：")
            for line in out.strip().splitlines()[-12:]:
                print("      " + line)

    print("\n" + "=" * 56)
    bad = [r for r in results if not r[1]]
    if not bad:
        print("   ✅ 三项全部通过。可以开始干活了。")
        print("=" * 56)
        return 0

    print(f"   ❌ 有 {len(bad)} 项不通过：")
    for name, _, _ in bad:
        print(f"      · {name}")
    print("\n   怎么办：把这一整屏截图发给我，我来修。")
    print("=" * 56)
    return 1


if __name__ == "__main__":
    sys.exit(main())
