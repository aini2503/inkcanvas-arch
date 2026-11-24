#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py —— 校验器自检（证明"它能抓错"，不只是"它能放行"）

用法：
  python selftest.py

跑这些用例：
  1. 三个黄金向量必须通过
  2. 缺必需文件 → 必须报错
  3. pageCount 与 pages 长度不符 → 必须报错
  4. 页码不连续 → 必须报错
  5. 坐标精度超过 3 位小数 → 必须出警告
  6. 未知字段 → 必须放行且列入 info（向前兼容）
  7. 高版本 schemaVersion → 必须拒绝
  8. round-trip：同一文件读两次 digest 必须完全一致
  9. 两端差异：改一个点 → compare 必须抓到

任何一条不符合预期 → 退出码 1。
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate as V  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
GV = HERE.parent / "golden-vectors"

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    icon = "✅" if cond else "❌"
    print(f"{icon} {name}" + (f"  ← {detail}" if detail and not cond else ""))


def load_zip(path: Path) -> dict:
    """把 .icink 读成 {name: bytes}，方便改坏再打包。"""
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def write_zip(path: Path, files: dict):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, data in files.items():
            info = zipfile.ZipInfo(n, date_time=(2026, 11, 19, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)


def mutate(files: dict, name: str, fn) -> dict:
    """对某个 json 文件做修改，返回新的 files。"""
    out = dict(files)
    obj = json.loads(out[name].decode("utf-8-sig"))
    fn(obj)
    out[name] = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return out


def run_one(path: Path):
    src = V.Source(path)
    try:
        return V.validate(src)
    finally:
        src.close()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="icink-selftest-"))
    try:
        basic = GV / "v1-basic.icink"
        check("黄金向量存在", basic.exists(), str(basic))
        if not basic.exists():
            return finish()

        files = load_zip(basic)

        # 1) 基线必须通过
        rep = run_one(basic)
        check("基线文件校验通过", not rep["errors"], "; ".join(rep["errors"][:2]))

        # 2) 缺必需文件
        f2 = {k: v for k, v in files.items() if k != "settings.json"}
        p2 = tmp / "no-settings.icink"
        write_zip(p2, f2)
        rep = run_one(p2)
        check("缺 settings.json 被检出",
              any("settings.json" in e for e in rep["errors"]), str(rep["errors"][:2]))

        # 3) pageCount 不符
        f3 = mutate(files, "manifest.json", lambda m: m.update({"pageCount": 5}))
        p3 = tmp / "bad-pagecount.icink"
        write_zip(p3, f3)
        rep = run_one(p3)
        check("pageCount 与实际页数不符被检出",
              any("pageCount" in e for e in rep["errors"]), str(rep["errors"][:2]))

        # 4) 页码不连续
        def bump_pages(m):
            m["pages"][2]["index"] = 7
        f4 = mutate(files, "manifest.json", bump_pages)
        p4 = tmp / "gap-page.icink"
        write_zip(p4, f4)
        rep = run_one(p4)
        check("页码不连续被检出",
              any("连续递增" in e for e in rep["errors"]), str(rep["errors"][:2]))

        # 5) 坐标精度超 3 位
        def looses_precision(pg):
            pg["strokes"][0]["points"][0][0] = 12.3456789
        f5 = mutate(files, "pages/page_0001.json", looses_precision)
        p5 = tmp / "precision.icink"
        write_zip(p5, f5)
        rep = run_one(p5)
        check("坐标精度超 3 位出警告",
              any("精度" in w for w in rep["warnings"]), str(rep["warnings"][:2]))

        # 6) 未知字段放行
        def add_unknown(m):
            m["superNewField"] = {"a": 1}
        f6 = mutate(files, "manifest.json", add_unknown)
        p6 = tmp / "unknown.icink"
        write_zip(p6, f6)
        rep = run_one(p6)
        check("未知字段不报错", not rep["errors"], str(rep["errors"][:2]))
        check("未知字段被记录为 info",
              any("superNewField" in i for i in rep["info"]), str(rep["info"][:2]))

        # 7) 高版本必须拒绝
        f7 = mutate(files, "manifest.json", lambda m: m.update({"schemaVersion": "5.0"}))
        p7 = tmp / "v5.icink"
        write_zip(p7, f7)
        rep = run_one(p7)
        check("v5 文件被拒绝并提示升级",
              any("必须拒绝打开" in e for e in rep["errors"]), str(rep["errors"][:2]))

        # 8) round-trip 幂等
        d1 = run_one(basic)["digest"]
        d2 = run_one(basic)["digest"]
        check("同一文件两次 digest 完全一致", V.compare(d1, d2) == [], str(V.compare(d1, d2)))

        # 9) 跨端差异被抓到
        def shift_point(pg):
            pg["strokes"][0]["points"][0][0] = 999.0
        f9 = mutate(files, "pages/page_0001.json", shift_point)
        p9 = tmp / "harmony.icink"
        write_zip(p9, f9)
        d9 = run_one(p9)["digest"]
        check("改一个点后 compare 能抓到差异",
              len(V.compare(d1, d9)) > 0, "compare 没发现差异，说明比对逻辑失效")

        # 10) 损坏的 zip
        p10 = tmp / "broken.icink"
        p10.write_bytes(b"PK\x03\x04this is not a real zip")
        try:
            run_one(p10)
            check("损坏文件被检出", False, "没有抛异常")
        except Exception:
            check("损坏文件被检出", True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return finish()


def finish():
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'=' * 46}\n{passed}/{total} 通过")
    if passed != total:
        print("❌ 校验器本身有问题，先修它再交给开发用")
        return 1
    print("✅ 校验器行为符合预期")
    return 0


if __name__ == "__main__":
    sys.exit(main())
