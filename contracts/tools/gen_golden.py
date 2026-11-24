#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_golden.py —— 生成黄金测试向量（.icink 标准样本 + 期望摘要）

用法：
  python gen_golden.py            # 生成到 contracts/golden-vectors/
  python gen_golden.py --check    # 只校验已有向量是否与 expected 一致（CI 用）

产出：
  v1-basic.icink   3 页 / 20 笔画 / 1 个规整三角形 / 1 张 AI 卡片 / 1 张图片
  v1-shapes.icink  6 种图形各一个
  v1-edge.icink    边界：空页、超长笔画、未知字段、中文标题、带 BOM 的风险点
  expected/*.expected.json   每个文件的期望摘要

设计要点：
  - 确定性：所有时间戳、id、zip 时间都写死，重复生成得到逐字节相同的文件
  - 自校验：生成后立刻用 validate.py 验证，验证不过就退出 1
"""

from __future__ import annotations

import json
import math
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate as V  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "golden-vectors"
EXPECTED = OUT / "expected"

FIXED_TIME = "2026-11-19T09:00:00+08:00"
ZIP_DATE = (2026, 11, 19, 9, 0, 0)   # 固定，保证可重现


# --------------------------------------------------------------------------
def pt(x, y, p=0.5, t=0):
    return [round(x, 3), round(y, 3), round(p, 3), int(t)]


def line_points(x0, y0, x1, y1, n=12, p=0.55):
    out = []
    for i in range(n):
        k = i / (n - 1)
        out.append(pt(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, p, i * 12))
    return out


def circle_points(cx, cy, r, n=36):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        out.append(pt(cx + r * math.cos(a), cy + r * math.sin(a), 0.6, i * 8))
    return out


def stroke(sid, points, color="#1A1A1A", width=0.6, tool="pen", **extra):
    d = {"id": sid, "tool": tool, "color": color, "widthMm": width, "points": points}
    d.update(extra)
    return d


def manifest(doc_id, title, pages, **extra):
    m = {
        "schemaVersion": "4.0",
        "docId": doc_id,
        "title": title,
        "createdAt": FIXED_TIME,
        "updatedAt": FIXED_TIME,
        "appName": "InkTeach",
        "appVersion": "1.0.0",
        "platform": "windows",
        "pageCount": len(pages),
        "defaultPageSizeMm": {"w": 1200.0, "h": 700.0},
        "pages": [
            {"index": i + 1, "file": f"pages/page_{i + 1:04d}.json",
             **({"thumb": f"pages/page_{i + 1:04d}.thumb.png"} if p.pop("_thumb", False) else {})}
            for i, p in enumerate(pages)
        ],
        "producer": {"contractVersion": 4},
    }
    m.update(extra)
    return m


def settings(**extra):
    s = {
        "schemaVersion": "4.0",
        "locale": "zh-CN",
        "theme": "light",
        "penDefaults": {
            "pen": {"color": "#1A1A1A", "widthMm": 0.6},
            "highlighter": {"color": "#FFE066", "widthMm": 4.0, "alpha": 0.45},
            "eraser": {"sizeMm": 8.0, "mode": "stroke"},
        },
        "canvas": {"pageSizeMm": {"w": 1200.0, "h": 700.0}, "background": "grid",
                   "gridSpacingMm": 10.0, "palmRejection": True},
        "ai": {"enabled": True, "endpoint": "", "provider": "teach-v1", "streaming": True,
               "timeoutMs": 8000,
               "features": {"lassoSolve": True, "sketchToShape": True, "boardToHandout": True}},
        "export": {"defaultFormat": "icink", "imageLongEdgePx": 2048,
                   "includeOriginalHandwriting": False},
        "privacy": {"uploadRawInk": False, "anonymizeTeacherName": True},
    }
    s.update(extra)
    return s


def page(index, strokes, shapes=None, images=None, textboxes=None, background=None):
    return {
        "pageIndex": index,
        "sizeMm": {"w": 1200.0, "h": 700.0},
        "background": background or {"type": "grid", "param": {"spacingMm": 10.0}},
        "strokes": strokes,
        "shapes": shapes or [],
        "images": images or [],
        "textBoxes": textboxes or [],
    }


# --------------------------------------------------------------------------
# 向量 1：基础（3 页 / 20 笔画 / 1 三角形 / 1 AI 卡片）
# --------------------------------------------------------------------------
def build_basic():
    p1_strokes = [
        stroke("s_0001", line_points(120, 120, 520, 120)),                  # 长横
        stroke("s_0002", line_points(120, 120, 120, 360)),                  # 竖
        stroke("s_0003", line_points(120, 360, 520, 360)),                  # 底横
        stroke("s_0004", line_points(120, 360, 520, 120)),                  # 斜边
        stroke("s_0005", line_points(600, 100, 900, 100), color="#D32F2F", width=0.8),
        stroke("s_0006", line_points(600, 160, 900, 160), color="#D32F2F", width=0.8),
    ]
    p1 = page(1, p1_strokes,
              shapes=[{
                  "id": "sh_0001",
                  "shapeType": "triangle",
                  "params": {"verticesMm": [[120.0, 120.0], [520.0, 120.0], [120.0, 360.0]],
                             "isRightAngle": True},
                  "sourceStrokeIds": ["s_0001", "s_0002", "s_0003", "s_0004"],
                  "rawPoints": p1_strokes[0]["points"][:6],
                  "decidedBy": "local",
                  "autoLabels": [{"type": "right_angle", "at": [120.0, 120.0]}],
              }],
              textboxes=[{"id": "t_0001", "rectMm": [40.0, 40.0, 200.0, 30.0],
                          "text": "第三课时 因式分解", "fontSizeMm": 6.0}])
    # 标记第 1 笔已被规整
    p1["strokes"][0]["renderedAs"] = "sh_0001"

    p2_strokes = [
        stroke(f"s_{i:04d}", circle_points(300 + (i % 4) * 150, 200 + (i // 4) * 120, 40), p=0.45)
        for i in range(7, 13)
    ]
    p2 = page(2, p2_strokes,
              images=[{"id": "img_0001", "asset": "assets/img_0001.png",
                       "rectMm": [700.0, 400.0, 240.0, 135.0]}])

    p3_strokes = [
        stroke(f"s_{i:04d}", line_points(100 + (i - 13) * 90, 500, 100 + (i - 13) * 90, 620, n=8))
        for i in range(13, 21)
    ]
    p3 = page(3, p3_strokes)

    annot = {
        "schemaVersion": "4.0",
        "annotationId": "a_0001",
        "kind": "solve",
        "pageIndex": 1,
        "anchor": {"bboxMm": {"x": 600.0, "y": 80.0, "w": 320.0, "h": 120.0},
                   "strokeIds": ["s_0005", "s_0006"]},
        "createdAt": FIXED_TIME,
        "model": "teach-v1",
        "contractVersion": 4,
        "confidence": 0.91,
        "edited": False,
        "payload": {
            "kind": "solve",
            "title": "解方程 x²-5x+6=0",
            "steps": [
                {"index": 1, "text": "将左边因式分解", "latex": "x^2-5x+6=(x-2)(x-3)"},
                {"index": 2, "text": "令每个因式为 0", "latex": "(x-2)=0\\ \\lor\\ (x-3)=0"},
                {"index": 3, "text": "得到两个解", "latex": "x_1=2,\\ x_2=3"},
            ],
            "knowledge": [{"name": "十字相乘法", "brief": "把二次三项式拆成两个一次因式的积"}],
            "pitfalls": [{"text": "只写一个解会扣分，一元二次方程必有两个根"}],
            "confidence": 0.91,
        },
    }

    mf = manifest("d_golden_basic", "黄金向量 · 基础三页", [p1, p2, p3],
                  subject="math", gradeLevel="junior_high",
                  courseInfo={"className": "初三(2)班", "teacherName": "李老师",
                              "schoolYear": "2026-2027"},
                  aiAnnotations=[{"file": "ai/annot_0001.json", "pageIndex": 1, "kind": "solve"}])

    files = {
        "manifest.json": mf,
        "settings.json": settings(),
        "pages/page_0001.json": p1,
        "pages/page_0002.json": p2,
        "pages/page_0003.json": p3,
        "ai/annot_0001.json": annot,
    }
    binary = {"assets/img_0001.png": _tiny_png()}
    return "v1-basic.icink", files, binary


# --------------------------------------------------------------------------
# 向量 2：六种图形
# --------------------------------------------------------------------------
def build_shapes():
    shapes = [
        {"id": "sh_0001", "shapeType": "triangle",
         "params": {"verticesMm": [[100.0, 400.0], [400.0, 400.0], [250.0, 200.0]]},
         "sourceStrokeIds": ["s_0001"], "decidedBy": "local"},
        {"id": "sh_0002", "shapeType": "rectangle",
         "params": {"originMm": [500.0, 200.0], "w": 300.0, "h": 180.0, "rotationDeg": 0.0},
         "sourceStrokeIds": ["s_0002"], "decidedBy": "local"},
        {"id": "sh_0003", "shapeType": "circle",
         "params": {"centerMm": [900.0, 300.0], "radiusMm": 80.0},
         "sourceStrokeIds": ["s_0003"], "decidedBy": "local"},
        {"id": "sh_0004", "shapeType": "line",
         "params": {"startMm": [100.0, 550.0], "endMm": [500.0, 550.0]},
         "sourceStrokeIds": ["s_0004"], "decidedBy": "local"},
        {"id": "sh_0005", "shapeType": "coordinate_system",
         "params": {"originMm": [600.0, 550.0], "xAxisEndMm": [1000.0, 550.0],
                    "yAxisEndMm": [600.0, 450.0],
                    "xRangeMm": [-100.0, 400.0], "yRangeMm": [-100.0, 100.0]},
         "sourceStrokeIds": ["s_0005", "s_0006"], "decidedBy": "local"},
        {"id": "sh_0006", "shapeType": "function_curve",
         "params": {"kindOfFunction": "quadratic", "coefficients": [1.0, -2.0, -3.0],
                    "pointsMm": [[600.0, 500.0], [700.0, 520.0], [800.0, 560.0]]},
         "sourceStrokeIds": ["s_0007"], "decidedBy": "local"},
    ]
    strokes = [
        stroke("s_0001", line_points(100, 400, 400, 400, 10)),
        stroke("s_0002", line_points(500, 200, 800, 200, 10)),
        stroke("s_0003", circle_points(900, 300, 80, 24)),
        stroke("s_0004", line_points(100, 550, 500, 550, 10)),
        stroke("s_0005", line_points(600, 550, 1000, 550, 10)),
        stroke("s_0006", line_points(600, 550, 600, 450, 6)),
        stroke("s_0007", line_points(600, 500, 800, 560, 14)),
    ]
    p1 = page(1, strokes, shapes=shapes)

    mf = manifest("d_golden_shapes", "黄金向量 · 六种标准图形", [p1],
                  subject="math", gradeLevel="junior_high")
    return "v1-shapes.icink", {
        "manifest.json": mf,
        "settings.json": settings(),
        "pages/page_0001.json": p1,
    }, {}


# --------------------------------------------------------------------------
# 向量 3：边界（空页 / 超长笔画 / 未知字段 / 中文标题）
# --------------------------------------------------------------------------
def build_edge():
    p1 = page(1, [], background={"type": "blank"})          # 完全空白页

    # 超长单笔画：5000 点
    long_points = [pt(50 + i * 0.2, 350 + 20 * math.sin(i / 50.0), 0.5, i * 4) for i in range(5000)]
    p2 = page(2, [stroke("s_0001", long_points)])

    # 未知字段（验证"保留未知字段"策略）
    p3 = page(3, [stroke("s_0002", line_points(100, 100, 300, 300, 8),
                         customPressureCurve="cubic")])
    p3["futureField"] = {"nested": [1, 2, 3], "note": "新版本加的字段，老客户端必须原样保留"}

    mf = manifest("d_golden_edge", "黄金向量 · 边界用例（中文标题、空白页、五千点、未知字段）",
                  [p1, p2, p3],
                  subject="physics", gradeLevel="senior_high",
                  unknownTopLevelField={"keep": "me"})   # 顶层未知字段
    return "v1-edge.icink", {
        "manifest.json": mf,
        "settings.json": settings(locale="zh-CN", futureSettingsKey=True),
        "pages/page_0001.json": p1,
        "pages/page_0002.json": p2,
        "pages/page_0003.json": p3,
    }, {}


# --------------------------------------------------------------------------
def _tiny_png() -> bytes:
    """1x1 透明 PNG，用来占位 assets/img_0001.png。"""
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
        "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )


def write_icink(path: Path, files: dict, binary: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            data = json.dumps(files[name], ensure_ascii=False, indent=2).encode("utf-8")
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
        for name, data in sorted(binary.items()):
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)


def main(argv):
    only_check = "--check" in argv
    OUT.mkdir(parents=True, exist_ok=True)
    EXPECTED.mkdir(parents=True, exist_ok=True)

    builders = [build_basic, build_shapes, build_edge]
    failed = 0

    for build in builders:
        name, files, binary = build()
        path = OUT / name

        if not only_check:
            write_icink(path, files, binary)
            print(f"[生成] {name}  ({path.stat().st_size:,} 字节)")

        # 立刻自校验
        src = V.Source(path)
        try:
            rep = V.validate(src)
        finally:
            src.close()

        if rep["errors"]:
            print(f"[失败] {name} 校验不通过：")
            for e in rep["errors"]:
                print("   -", e)
            failed += 1
            continue

        expected = {
            "file": name,
            "note": "本文件由 gen_golden.py 生成，勿手改。改动请改生成器。",
            **rep["digest"],
            "warnings": rep["warnings"],
        }
        exp_path = EXPECTED / f"{name.replace('.icink', '.expected.json')}"

        if only_check:
            if not exp_path.exists():
                print(f"[失败] {name} 缺少 expected 文件")
                failed += 1
                continue
            with open(exp_path, "r", encoding="utf-8-sig") as f:
                old = json.load(f)
            diffs = V.compare(old, expected)
            if diffs:
                print(f"[失败] {name} 与 expected 不一致：")
                for d in diffs:
                    print("   -", d)
                failed += 1
            else:
                print(f"[通过] {name}  digest 与 expected 一致")
        else:
            with open(exp_path, "w", encoding="utf-8") as f:
                json.dump(expected, f, ensure_ascii=False, indent=2)
            print(f"[期望] {exp_path.name}  pageCount={expected['pageCount']} "
                  f"strokes={expected['totalStrokes']} points={expected['totalPoints']}")

    print()
    if failed:
        print(f"❌ {failed} 个向量有问题")
        return 1
    print("✅ 全部向量生成/校验通过" + ("（check 模式）" if only_check else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
