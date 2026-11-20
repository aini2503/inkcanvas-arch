#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stress_test.py —— 性能压测数据生成 + 校验基准（给单小蔓用）

三件事：
  1. 生成 100 / 500 / 1000 / 2000 笔画的 .icink 压测样本
  2. 测校验器在各档位下的耗时（这是"文件能不能秒开"的下限参考）
  3. 导出「连续书写输入序列」JSON，给客户端模拟真人高速书写

用法：
  python stress_test.py                      # 默认 100/500/1000/2000
  python stress_test.py --counts 100 500     # 自定义档位
  python stress_test.py --out D:\\stress      # 自定义输出目录

产出：
  <out>/stress-{N}.icink          压测文件（拖进客户端看 FPS）
  <out>/stroke-feed-{N}.json      连续书写输入序列（client 读它模拟输入）
  <out>/REPORT.md                 本次报告

⚠️ 这些文件只用于压测，不要拿去演示。演示用 golden-demo 里的样板。
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_golden import FIXED_TIME, ZIP_DATE, manifest, page, pt, settings, stroke  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "stress"

PW, PH = 1200.0, 700.0


def gen_stroke(i: int, points_per_stroke: int = 40):
    """
    生成一条"像真人写的"笔画：贝塞尔弧线 + 压感起伏 + 时间戳。

    points_per_stroke 与实际点数：40 点 ≈ 一笔写一个字的一横，比较接近真实。
    """
    # 起点落在页面上，按黄金角分布，避免全挤在一处
    cx = 80 + ((i * 137.508) % (PW - 160))
    cy = 80 + ((i * 73.31) % (PH - 160))
    radius = 12 + (i % 7) * 6
    start = (i * 0.9) % (2 * math.pi)

    pts = []
    t = 0
    for k in range(points_per_stroke):
        f = k / (points_per_stroke - 1)
        ang = start + f * math.pi * (0.8 + (i % 5) * 0.3)
        x = cx + radius * math.cos(ang) * (1 - 0.3 * f)
        y = cy + radius * math.sin(ang) * 0.6
        # 压感：起笔轻、中段重、收笔轻
        pressure = 0.35 + 0.45 * math.sin(f * math.pi) + 0.05 * math.sin(i)
        pressure = max(0.1, min(1.0, pressure))
        pts.append(pt(x, y, pressure, t))
        t += 8 + (i % 4)   # 8–11 ms 一点，接近 120Hz 报点
    return pts


def build_doc(n_strokes: int):
    """n 条笔画，分页，每页最多 200 条（模拟真实课堂翻页）。"""
    per_page = 200
    pages = []
    sid = 0
    for p_idx in range(math.ceil(n_strokes / per_page)):
        s = []
        for _ in range(min(per_page, n_strokes - sid)):
            sid += 1
            s.append(stroke(f"s_{sid:04d}", gen_stroke(sid)))
        pages.append(page(p_idx + 1, s))
    return pages


def write_icink(path: Path, files: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            data = json.dumps(files[name], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)


def main(argv):
    import validate as V

    counts = [100, 500, 1000, 2000]
    if "--counts" in argv:
        i = argv.index("--counts")
        counts = []
        for a in argv[i + 1:]:
            if a.isdigit():
                counts.append(int(a))
            else:
                break

    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"{'笔画':>6} {'页数':>4} {'点数':>8} {'文件大小':>10} {'生成耗时':>9} {'校验耗时':>9}")
    print("-" * 62)

    for n in counts:
        t0 = time.perf_counter()
        pages = build_doc(n)
        mf = manifest(f"d_stress_{n}", f"压测样本 {n} 笔画", pages, subject="math")
        files = {"manifest.json": mf, "settings.json": settings()}
        for i, pg in enumerate(pages, 1):
            files[f"pages/page_{i:04d}.json"] = pg
        web = out / f"stress-{n}.icink"
        write_icink(web, files)
        t_gen = (time.perf_counter() - t0) * 1000

        # 校验计时
        t1 = time.perf_counter()
        src = V.Source(web)
        try:
            rep = V.validate(src)
        finally:
            src.close()
        t_val = (time.perf_counter() - t1) * 1000

        d = rep["digest"]
        size_kb = web.stat().st_size / 1024
        print(f"{n:>6} {d['pageCount']:>4} {d['totalPoints']:>8} "
              f"{size_kb:>9.1f}K {t_gen:>8.0f}ms {t_val:>8.0f}ms")

        if rep["errors"]:
            print(f"   ⚠️ {len(rep['errors'])} 个校验错误")
            for e in rep["errors"][:2]:
                print("     -", e)

        # 导出连续书写输入序列（给客户端模拟真人输入）
        feed = []
        for pg in pages:
            for st in pg["strokes"]:
                feed.append({"tool": "pen", "color": "#1A1A1A", "widthMm": 0.6,
                             "points": st["points"]})
        feed_path = out / f"stroke-feed-{n}.json"
        with open(feed_path, "w", encoding="utf-8") as f:
            json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))

        rows.append({
            "strokes": n, "pages": d["pageCount"], "points": d["totalPoints"],
            "fileKb": round(size_kb, 1), "genMs": round(t_gen), "validateMs": round(t_val),
            "feedMs": sum(len(s["points"]) * 9 for pg in pages for s in pg["strokes"]),
        })

    # 报告
    md = ["# 压测数据报告", "",
          f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}",
          f"输出目录：`{out}`", "",
          "| 笔画数 | 页数 | 点数 | 文件大小 | 生成耗时 | 校验耗时 | 数据生成耗时(模拟) |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['strokes']} | {r['pages']} | {r['points']} | {r['fileKb']} KB | "
                  f"{r['genMs']} ms | {r['validateMs']} ms | {r['feedMs']/1000:.0f} s |")
    md += ["", "## 怎么用", "",
           "1. `stress-{N}.icink` 拖进客户端 → 记录打开耗时、滚动是否掉帧",
           "2. `stroke-feed-{N}.json` 给客户端读 → 按点的时间戳回放，"
           "模拟真人高速书写，同时采集 FPS",
           "3. 把实测的 FPS / 打开耗时填进 `每周五互通检查表.md` 的性能栏",
           "",
           "## 判定参考", "",
           "| 指标 | 及格 | 好 | 惊艳 |",
           "|---|---|---|---|",
           "| 1000 笔画书写 FPS | ≥ 45 | ≥ 55 | ≥ 58 |",
           "| 1000 笔画打开耗时 | ≤ 3s | ≤ 2s | ≤ 1.5s |",
           "| 首笔出墨延迟 | ≤ 50ms | ≤ 30ms | ≤ 20ms |",
           "| 撤销/重做 50 次后 FPS | ≥ 45 | ≥ 55 | ≥ 58 |"]
    (out / "REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\n✅ 全部生成 → {out}")
    print(f"   REPORT.md 已写好")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
