#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_golden_demo.py —— 生成数理化生 Golden Demo 样板（.icink）

用途：
  1. 给王梓楠当"标准演示存档库"的起点，真机打开看渲染对不对
  2. 给双端当渲染验证样本（比几何图形更"教学"）
  3. 演示时挑最上镜的一页直接讲

用法：
  python gen_golden_demo.py

产出到 contracts/golden-demo/：
  demo-math-functions.icink   二次函数图像 + 坐标系 + 顶点标注
  demo-physics-incline.icink  斜面受力分析（重力/支持力/摩擦力）
  demo-physics-circuit.icink  串联电路（电池/电阻/开关）
  demo-chemistry.icink        实验装置（烧杯/试管/酒精灯）

所有坐标单位毫米，页面 1200 x 700 mm。
"""

from __future__ import annotations

import json
import math
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_golden import (  # noqa: E402
    FIXED_TIME, ZIP_DATE, manifest, page, pt, settings, stroke,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "golden-demo"

PW, PH = 1200.0, 700.0


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def poly(pts, t_step=10, p=0.55, **_ignored):
    """[(x,y), ...] → 笔迹点序列（额外的样式参数由 P.add 处理）"""
    out, t = [], 0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 4))
        for k in range(n):
            f = k / (n - 1) if n > 1 else 0
            out.append(pt(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, p, t))
            t += t_step
    return out


def seg(x0, y0, x1, y1, **kw):
    return poly([(x0, y0), (x1, y1)], **kw)


def arrow(x0, y0, x1, y1, head=10.0):
    """一条带箭头的线（返回两组点：主干 + 箭头两撇）"""
    body = seg(x0, y0, x1, y1, p=0.6)
    ang = math.atan2(y1 - y0, x1 - x0)
    a1, a2 = ang + math.radians(155), ang - math.radians(155)
    h1 = (x1 + head * math.cos(a1), y1 + head * math.sin(a1))
    h2 = (x1 + head * math.cos(a2), y1 + head * math.sin(a2))
    return body, seg(x1, y1, h1[0], h1[1], p=0.6), seg(x1, y1, h2[0], h2[1], p=0.6)


def rect_pts(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


def arc_pts(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / (n - 1)),
             cy + r * math.sin(a0 + (a1 - a0) * i / (n - 1))) for i in range(n)]


def tb(tid, x, y, text, size=6.0):
    return {"id": tid, "rectMm": [float(x), float(y), 240.0, 26.0],
            "text": text, "fontSizeMm": size}


class Page:
    """收集笔画，自动编号"""

    def __init__(self, index=1):
        self.index = index
        self.strokes = []
        self.shapes = []
        self.images = []
        self.text = []
        self._s = 0
        self._sh = 0
        self._t = 0

    def add(self, points, color="#1A1A1A", width=0.6, tool="pen", alpha=None, **_ignored):
        # 规范化：允许传 [(x,y)] 或 [[x,y,p,t]]，统一成 4 元组、3 位小数
        norm, t = [], 0
        for q in points:
            if len(q) >= 4:
                norm.append([round(float(q[0]), 3), round(float(q[1]), 3),
                             round(float(q[2]), 3), int(q[3])])
                t = int(q[3]) + 10
            else:
                norm.append([round(float(q[0]), 3), round(float(q[1]), 3), 0.55, t])
                t += 10
        self._s += 1
        extra = {}
        if alpha is not None:
            extra["alpha"] = alpha
        st = stroke(f"s_{self._s:04d}", norm, color=color, width=width, tool=tool, **extra)
        self.strokes.append(st)
        return st["id"]

    def textbox(self, x, y, text, size=6.0):
        self._t += 1
        self.text.append(tb(f"t_{self._t:04d}", x, y, text, size))

    def shape(self, shape_type, params, source_ids, decided="local", labels=None):
        self._sh += 1
        d = {"id": f"sh_{self._sh:04d}", "shapeType": shape_type, "params": params,
             "sourceStrokeIds": source_ids, "decidedBy": decided}
        if labels:
            d["autoLabels"] = labels
        self.shapes.append(d)
        return d["id"]

    def build(self):
        return page(self.index, self.strokes, self.shapes, self.images, self.text,
                    background={"type": "grid", "param": {"spacingMm": 10.0}})


# --------------------------------------------------------------------------
# 1. 数学 · 二次函数图像
# --------------------------------------------------------------------------
def build_math():
    P = Page()
    OX, OY = 200.0, 520.0          # 原点屏幕位置
    SX = 170.0                     # 每 1 个 x 单位 = 170mm
    SY = 55.0                      # 每 1 个 y 单位 = 55mm
    to_screen = lambda x, y: (OX + x * SX, OY - y * SY)

    # 坐标系
    ax = P.add(seg(OX - 40, OY, OX + 950, OY, p=0.6))          # x 轴
    ay = P.add(seg(OX, OY + 60, OX, OY - 430, p=0.6))          # y 轴
    P.add(seg(OX + 950, OY, OX + 975, OY - 8, p=0.6))
    P.add(seg(OX + 950, OY, OX + 975, OY + 8, p=0.6))
    P.add(seg(OX, OY - 430, OX - 8, OY - 400, p=0.6))
    P.add(seg(OX, OY - 430, OX + 8, OY - 400, p=0.6))
    P.textbox(OX + 985, OY - 20, "x", 7.0)
    P.textbox(OX + 12, OY - 445, "y", 7.0)

    # 刻度
    for k in range(-1, 6):
        x, y = to_screen(k, 0)
        if k != 0 and 150 < x < 1150:
            P.add(seg(x, y - 6, x, y + 6, p=0.5, width=0.4))
            P.textbox(x - 6, y + 10, str(k), 4.5)
    for k in range(-2, 7):
        x, y = to_screen(0, k)
        if k != 0 and 80 < y < 660:
            P.add(seg(x - 6, y, x + 6, y, p=0.5, width=0.4))
            P.textbox(x - 22, y - 8, str(k), 4.5)

    # 抛物线 y = x^2 - 4x + 3
    curve = [to_screen(-0.6 + 6.0 * i / 89, (-0.6 + 6.0 * i / 89) ** 2 - 4 * (-0.6 + 6.0 * i / 89) + 3)
             for i in range(90)]
    cs = P.add(poly(curve, p=0.65), color="#1565C0", width=0.8)
    P.shape("function_curve",
            {"kindOfFunction": "quadratic", "coefficients": [1.0, -4.0, 3.0],
             "pointsMm": [[round(a, 1), round(b, 1)] for a, b in curve[::10]]},
            [cs], labels=[{"type": "vertex", "at": [round(v, 1) for v in to_screen(2, -1)]}])

    # 顶点 + 两根
    vx, vy = to_screen(2, -1)
    P.add(arc_pts(vx, vy, 6, 0, 2 * math.pi, 12), color="#D32F2F", width=0.7)
    P.textbox(vx + 12, vy + 6, "顶点(2,-1)", 5.0)
    for root in (1, 3):
        rx, ry = to_screen(root, 0)
        P.add(arc_pts(rx, ry, 5, 0, 2 * math.pi, 12), color="#D32F2F", width=0.7)
        P.textbox(rx - 8, ry + 26, f"x={root}", 5.0)

    # 对称轴（虚线感）
    for k in range(6):
        y0 = OY - 400 + k * 66
        P.add(seg(vx, y0, vx, y0 + 34, p=0.4, width=0.35, color="#9E9E9E"))

    P.textbox(260, 90, "y = x² - 4x + 3", 8.0)
    P.textbox(260, 130, "开口向上，对称轴 x = 2", 5.5)

    return "demo-math-functions.icink", "黄金演示 · 二次函数图像", "math", [P.build()]


# --------------------------------------------------------------------------
# 2. 物理 · 斜面受力
# --------------------------------------------------------------------------
def build_incline():
    P = Page()
    X0, Y0 = 220.0, 600.0          # 斜面左下角
    SL = 520.0                     # 斜面长度
    ANG = math.radians(30)
    X1, Y1 = X0 + SL * math.cos(ANG), Y0 - SL * math.sin(ANG)

    # 地面 + 斜面
    P.add(seg(X0 - 60, Y0, X1 + 120, Y0, p=0.6))
    face = P.add(seg(X0, Y0, X1, Y1, p=0.6, width=0.8))
    back = P.add(seg(X1, Y1, X1, Y0, p=0.5, width=0.5, color="#BDBDBD"))
    P.shape("triangle",
            {"verticesMm": [[X0, Y0], [X1, Y0], [round(X1, 1), round(Y1, 1)]],
             "isRightAngle": False},
            [face, back])
    # 倾角标注
    P.add(arc_pts(X0, Y0, 70, -ANG, 0, 14), color="#D32F2F", width=0.6)
    P.textbox(X0 + 78, Y0 - 32, "θ=30°", 6.0)

    # 物块（斜面上的小方块）
    cx, cy = X0 + 0.55 * SL * math.cos(ANG), Y0 - 0.55 * SL * math.sin(ANG)
    ux, uy = math.cos(ANG), -math.sin(ANG)       # 沿斜面向上
    nx, ny = -math.sin(ANG), -math.cos(ANG)      # 垂直斜面向外
    bw, bh = 54.0, 34.0
    p0 = (cx - ux * bw / 2 - nx * bh, cy - uy * bw / 2 - ny * bh)
    p1 = (cx + ux * bw / 2 - nx * bh, cy + uy * bw / 2 - ny * bh)
    p2 = (cx + ux * bw / 2, cy + uy * bw / 2)
    p3 = (cx - ux * bw / 2, cy - uy * bw / 2)
    block = P.add(poly([p0, p1, p2, p3, p0], p=0.6), color="#1A1A1A", width=0.8)
    P.shape("rectangle",
            {"originMm": [round(min(p[0] for p in (p0, p1, p2, p3)), 1),
                          round(min(p[1] for p in (p0, p1, p2, p3)), 1)],
             "w": round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 1),
             "h": round(bh, 1), "rotationDeg": round(math.degrees(ANG) % 360, 1)},
            [block], labels=[{"type": "right_angle", "at": [round(p2[0], 1), round(p2[1], 1)]}])
    P.textbox(cx - 18, cy - 14, "m", 6.5)

    # 三个力
    F = 150.0
    g_end = (cx, cy + F)
    n_end = (cx + nx * F, cy + ny * F)
    f_end = (cx - ux * F * 0.8, cy - uy * F * 0.8)
    for (ex, ey), col, lab in (
        (g_end, "#D32F2F", "G = mg"),
        (n_end, "#2E7D32", "N"),
        (f_end, "#F57C00", "f"),
    ):
        P.add(seg(cx, cy, ex, ey, p=0.6, width=0.8, color=col))
        P.add(seg(ex, ey, ex - 8 * math.cos(math.atan2(ey - cy, ex - cx) + math.radians(170)),
                  ey - 8 * math.sin(math.atan2(ey - cy, ex - cx) + math.radians(170)),
                  p=0.6, color=col))
        P.add(seg(ex, ey, ex - 8 * math.cos(math.atan2(ey - cy, ex - cx) - math.radians(170)),
                  ey - 8 * math.sin(math.atan2(ey - cy, ex - cx) - math.radians(170)),
                  p=0.6, color=col))
        P.textbox(ex + (8 if "G" in lab else -30), ey + 4, lab, 5.5)

    # 分解虚线
    for k in range(5):
        t = k / 5
        P.add(seg(cx + (g_end[0] - cx) * t, cy + (g_end[1] - cy) * t,
                  cx + (n_end[0] - cx) * t, cy + (n_end[1] - cy) * t,
                  p=0.35, width=0.3, color="#BDBDBD"))

    P.textbox(120, 90, "斜面受力分析", 8.0)
    P.textbox(120, 128, "重力沿斜面分量：mg sin θ    法向分量：mg cos θ", 5.0)
    return "demo-physics-incline.icink", "黄金演示 · 斜面受力分析", "physics", [P.build()]


# --------------------------------------------------------------------------
# 3. 物理 · 串联电路
# --------------------------------------------------------------------------
def build_circuit():
    P = Page()
    L, T, R, B = 320.0, 220.0, 900.0, 520.0

    # 外框
    P.add(poly([(L, T), (R, T)], p=0.6))
    P.add(poly([(R, T), (R, B)], p=0.6))
    P.add(poly([(L, B), (R, B)], p=0.6))
    # 左边留电池缺口
    P.add(poly([(L, B), (L, 430)], p=0.6))
    P.add(poly([(L, 310), (L, T)], p=0.6))

    # 电池（两对长短线）
    for i, (y, w) in enumerate([(350, 46), (378, 24)]):
        P.add(seg(L - w / 2, y, L + w / 2, y, p=0.6, width=0.9))
    P.textbox(L - 90, 340, "E", 6.0)

    # 电阻（矩形）
    P.add(poly(rect_pts(560, T - 26, 120, 52), p=0.6, width=0.8))
    P.textbox(596, T + 34, "R₁", 5.5)

    # 开关（断开 + 触点）
    P.add(seg(700, T, 760, T, p=0.6))
    P.add(seg(760, T, 812, T - 34, p=0.6))
    P.add(arc_pts(760, T, 4, 0, 2 * math.pi, 8), p=0.6)
    P.add(arc_pts(815, T, 4, 0, 2 * math.pi, 8), p=0.6)
    P.textbox(762, T - 60, "S", 5.5)

    # 电流方向箭头
    for (x, y, dx, dy) in ((470, T, 1, 0), (R, 340, 0, 1), (700, B, -1, 0), (L, 470, 0, -1)):
        P.add(seg(x, y, x + dx * 40, y + dy * 40, p=0.5, width=0.5, color="#1565C0"))
        ang = math.atan2(dy, dx)
        P.add(seg(x + dx * 40, y + dy * 40,
                  x + dx * 40 - 9 * math.cos(ang - 0.5), y + dy * 40 - 9 * math.sin(ang - 0.5),
                  p=0.5, color="#1565C0"))
        P.add(seg(x + dx * 40, y + dy * 40,
                  x + dx * 40 - 9 * math.cos(ang + 0.5), y + dy * 40 - 9 * math.sin(ang + 0.5),
                  p=0.5, color="#1565C0"))
    P.textbox(560, B + 40, "电流方向", 5.0)

    P.textbox(120, 90, "串联电路", 8.0)
    P.textbox(120, 128, "I = E / (R₁ + r)    U₁ = I · R₁", 5.0)
    return "demo-physics-circuit.icink", "黄金演示 · 串联电路", "physics", [P.build()]


# --------------------------------------------------------------------------
# 4. 化学 · 实验装置
# --------------------------------------------------------------------------
def build_chemistry():
    P = Page()
    # 烧杯
    bx, by, bw, bh = 300.0, 300.0, 220.0, 260.0
    P.add(poly([(bx, by), (bx, by + bh), (bx + bw, by + bh), (bx + bw, by), (bx + bw - 14, by)],
               p=0.6, width=0.8))
    # 液面
    P.add(seg(bx + 6, by + bh - 120, bx + bw - 6, by + bh - 120, p=0.55, width=0.6, color="#1565C0"))
    # 液体填充（浅蓝荧光）
    for k in range(7):
        y = by + bh - 110 + k * 16
        P.add(seg(bx + 8, y, bx + bw - 8, y, p=0.25, width=3.2, tool="highlighter",
                  color="#4FC3F7", alpha=0.28))
    P.textbox(bx + 60, by - 30, "烧杯", 5.5)

    # 试管（倾斜）
    tx, ty = 700.0, 250.0
    ang = math.radians(68)
    tl = 240.0
    ex, ey = tx + tl * math.cos(ang), ty + tl * math.sin(ang)
    P.add(seg(tx, ty, ex, ey, p=0.6, width=0.6))
    P.add(seg(tx + 26, ty - 10, ex + 26, ey - 10, p=0.6, width=0.6))
    P.add(arc_pts((tx + ex) / 2 + 13, (ty + ey) / 2 - 5, 13,
                  math.atan2(ey - ty, ex - tx) - math.pi / 2,
                  math.atan2(ey - ty, ex - tx) + math.pi / 2, 14))
    # 管内液体
    for k in range(3):
        f = 0.55 + k * 0.12
        P.add(seg(tx + (ex - tx) * f + 4, ty + (ey - ty) * f,
                  tx + (ex - tx) * f + 22, ty + (ey - ty) * f - 4,
                  p=0.3, width=3.0, tool="highlighter", color="#66BB6A", alpha=0.3))
    P.textbox(tx - 60, ty - 50, "试管", 5.5)

    # 酒精灯
    fx, fy = 880.0, 620.0
    P.add(poly(rect_pts(fx, fy - 90, 90, 90), p=0.6, width=0.7))
    P.add(poly([(fx + 30, fy - 90), (fx + 45, fy - 150), (fx + 60, fy - 90)], p=0.6))
    # 火焰
    for k in range(3):
        a = fx + 45 + (k - 1) * 8
        P.add(poly([(a, fy - 150), (a + 6, fy - 190 - k * 6), (a + 12, fy - 150)], p=0.5,
                   color="#FB8C00"))
    P.textbox(fx + 20, fy + 8, "酒精灯", 5.5)

    # 导管
    P.add(poly([(tx + 6, ty - 4), (tx + 6, ty - 60), (bx + bw + 40, ty - 60)], p=0.55, width=0.6))

    P.textbox(120, 90, "实验室制取气体装置", 8.0)
    P.textbox(120, 128, "加热 → 收集 → 验满", 5.0)
    return "demo-chemistry.icink", "黄金演示 · 实验装置", "chemistry", [P.build()]


# --------------------------------------------------------------------------
def write_icink(path: Path, files: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            data = json.dumps(files[name], ensure_ascii=False, indent=2).encode("utf-8")
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)


def main():
    import validate as V

    OUT.mkdir(parents=True, exist_ok=True)
    builders = [
        (build_math, "d_demo_math"),
        (build_incline, "d_demo_incline"),
        (build_circuit, "d_demo_circuit"),
        (build_chemistry, "d_demo_chem"),
    ]
    ok = 0
    for build, docid in builders:
        fname, title, subject, pages = build()
        mf = manifest(docid, title, pages, subject=subject, gradeLevel="senior_high")
        files = {"manifest.json": mf, "settings.json": settings()}
        for i, pg in enumerate(pages, 1):
            files[f"pages/page_{i:04d}.json"] = pg

        path = OUT / fname
        write_icink(path, files)

        src = V.Source(path)
        try:
            rep = V.validate(src)
        finally:
            src.close()

        d = rep["digest"]
        if rep["errors"]:
            print(f"❌ {fname}")
            for e in rep["errors"][:3]:
                print("   -", e)
        else:
            print(f"✅ {fname:<30} {d['totalStrokes']:>3} 笔画 / {d['totalPoints']:>5} 点 / "
                  f"图形 {d['pages'][0]['shapes']} 个  ({path.stat().st_size:,} 字节)")
            ok += 1

    print(f"\n{ok}/{len(builders)} 生成成功 → {OUT}")
    return 0 if ok == len(builders) else 1


if __name__ == "__main__":
    sys.exit(main())
