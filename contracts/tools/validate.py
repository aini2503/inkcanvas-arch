#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py —— .icink 存档校验器 / 摘要器 / 跨端比对器

用法：
  # 1) 完整校验（schema + 交叉一致性）
  python validate.py lesson.icink

  # 2) 只输出摘要 JSON（给两端比对用，纯 JSON 到 stdout）
  python validate.py lesson.icink --digest > win.digest.json

  # 3) 比对两端的摘要（这是"接口警察"的执法动作）
  python validate.py win.digest.json harmony.digest.json --compare

  # 4) 校验目录（解压后的工作目录也行）
  python validate.py path/to/extracted_dir/

退出码：
  0 = 全部通过
  1 = 有问题（错误明细见输出）
  2 = 用法错误 / 文件不存在

约定：
  - 文本一律 UTF-8（容忍 BOM）
  - 坐标单位毫米，序列化为 3 位小数
  - 未知字段不报错（向前兼容），但会在报告的 info 里列出来
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    print("[致命] 缺少 jsonschema。安装：python -m pip install jsonschema", file=sys.stderr)
    sys.exit(2)

# Windows 控制台默认 GBK，强制 UTF-8 输出，避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent          # 项目根
SCHEMA_DIR = ROOT / "schemas"

MANIFEST_SCHEMA = "icink.manifest.schema.json"
PAGE_SCHEMA = "icink.page.schema.json"
SETTINGS_SCHEMA = "icink.settings.schema.json"
ANNOT_SCHEMA = "icink.annotation.schema.json"

REQUIRED_FILES = ["manifest.json", "settings.json"]
CONTRACT_VERSION = 1


# --------------------------------------------------------------------------
# 读文件：支持 .icink(zip) 和目录
# --------------------------------------------------------------------------
class Source:
    """统一的文件读取抽象，zip 和目录共用。"""

    def __init__(self, target: Path):
        self.target = target
        self.is_zip = target.is_file()
        self._zf = zipfile.ZipFile(target) if self.is_zip else None
        self._names = set(self._zf.namelist()) if self._zf else set()

    def names(self):
        if self.is_zip:
            return sorted(self._names)
        return sorted(
            str(p.relative_to(self.target)).replace("\\", "/")
            for p in self.target.rglob("*") if p.is_file()
        )

    def exists(self, name: str) -> bool:
        if self.is_zip:
            return name in self._names
        return (self.target / name).is_file()

    def read_bytes(self, name: str) -> bytes:
        if self.is_zip:
            return self._zf.read(name)
        return (self.target / name).read_bytes()

    def read_json(self, name: str):
        raw = self.read_bytes(name)
        # 容忍 BOM（PowerShell 的 Out-File -Encoding utf8 会加）
        text = raw.decode("utf-8-sig")
        if text.lstrip()[:1] == "":
            raise ValueError(f"{name} 含 UTF-16/其它非 UTF-8 编码")
        return json.loads(text)

    def close(self):
        if self._zf:
            self._zf.close()


# --------------------------------------------------------------------------
# JSON 数字规范化：把浮点转成 3 位小数（跨端比对必须做这一步）
# --------------------------------------------------------------------------
def q3(v):
    """量化到 3 位小数，返回 float。非数字原样返回。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    if isinstance(v, int):
        return v
    return float(Decimal(str(v)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def norm_points(points):
    """[[x,y,p,t], ...] → 量化后重新打包，保证两端算出来的字符串一致。"""
    out = []
    for pt in points:
        if isinstance(pt, (list, tuple)) and len(pt) >= 4:
            out.append([q3(pt[0]), q3(pt[1]), q3(pt[2]), int(pt[3])])
        else:
            out.append(pt)
    return out


def page_content_hash(page) -> str:
    """
    页面内容指纹：把笔画（含每个点的坐标/笔压/时间）规范化后做 sha256。

    为什么需要它：
      只比"笔画数/点数"抓不到"点被搬了 3 毫米"这种错误，
      而这类错误正是两端不一致的典型表现。
      有了这个哈希，任何一点位置差异都会被立刻抓到。
    """
    import hashlib

    canon = {
        "pageIndex": page.get("pageIndex"),
        "sizeMm": {k: q3(v) for k, v in (page.get("sizeMm") or {}).items()
                   if isinstance(v, (int, float))},
        "strokes": [
            {
                "id": st.get("id"),
                "tool": st.get("tool"),
                "color": st.get("color"),
                "widthMm": q3(st.get("widthMm", 0)),
                "renderedAs": st.get("renderedAs"),
                "points": norm_points(st.get("points") or []),
            }
            for st in (page.get("strokes") or [])
            if isinstance(st, dict)
        ],
        "shapes": [
            {
                "id": sh.get("id"),
                "shapeType": sh.get("shapeType"),
                "params": sh.get("params"),
                "decidedBy": sh.get("decidedBy"),
            }
            for sh in (page.get("shapes") or [])
            if isinstance(sh, dict)
        ],
        "images": [
            {"id": im.get("id"), "asset": im.get("asset"),
             "rectMm": [q3(v) for v in (im.get("rectMm") or [])]}
            for im in (page.get("images") or [])
            if isinstance(im, dict)
        ],
        "textBoxes": [
            {"id": tb.get("id"), "text": tb.get("text")}
            for tb in (page.get("textBoxes") or [])
            if isinstance(tb, dict)
        ],
    }
    blob = json.dumps(canon, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def load_schema(name: str):
    with open(SCHEMA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def schema_errors(instance, schema, where: str):
    validator = Draft202012Validator(schema)
    errs = []
    for e in sorted(validator.iter_errors(instance), key=lambda x: list(x.path)):
        loc = "/".join(str(x) for x in e.path) or "(根)"
        errs.append(f"{where}: {loc} → {e.message}")
    return errs


def collect_unknown_keys(obj, allowed, where, out_info):
    if not isinstance(obj, dict):
        return
    extra = sorted(set(obj) - set(allowed))
    if extra:
        out_info.append(f"{where}: 未知字段（将被原样保留）{extra}")


def validate(src: Source):
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    # ---- 1. 必需文件 ----
    for f in REQUIRED_FILES:
        if not src.exists(f):
            errors.append(f"缺少必需文件：{f}")
    if errors:
        return _report(errors, warnings, info, None)

    # ---- 2. manifest ----
    try:
        manifest = src.read_json("manifest.json")
    except Exception as e:
        errors.append(f"manifest.json 解析失败：{e}")
        return _report(errors, warnings, info, None)

    mschema = load_schema(MANIFEST_SCHEMA)
    errors += schema_errors(manifest, mschema, "manifest.json")
    collect_unknown_keys(
        manifest,
        mschema.get("properties", {}).keys(),
        "manifest.json", info,
    )

    if isinstance(manifest, dict):
        pv = (manifest.get("producer") or {}).get("contractVersion")
        if pv != CONTRACT_VERSION:
            errors.append(
                f"manifest.producer.contractVersion = {pv!r}，本客户端只接受 {CONTRACT_VERSION}"
            )

    # ---- 3. settings ----
    try:
        settings = src.read_json("settings.json")
        sschema = load_schema(SETTINGS_SCHEMA)
        errors += schema_errors(settings, sschema, "settings.json")
        collect_unknown_keys(settings, sschema.get("properties", {}).keys(), "settings.json", info)
    except Exception as e:
        errors.append(f"settings.json 解析失败：{e}")

    # ---- 4. 版本策略 ----
    sv = manifest.get("schemaVersion", "") if isinstance(manifest, dict) else ""
    major = None
    try:
        major = int(str(sv).split(".")[0])
    except Exception:
        pass
    if major is not None and major > CONTRACT_VERSION:
        errors.append(
            f"schemaVersion {sv} 高于客户端支持的 {CONTRACT_VERSION}"
            f" —— 必须拒绝打开并提示升级（不许尝试读）"
        )

    # ---- 5. 逐页 ----
    pages_meta = manifest.get("pages", []) if isinstance(manifest, dict) else []
    pschema = load_schema(PAGE_SCHEMA)

    seen_stroke_ids: dict[str, str] = {}
    total_points = 0
    total_strokes = 0
    page_stats = []

    # pages 索引连续性
    idxs = [p.get("index") for p in pages_meta if isinstance(p, dict)]
    if idxs and idxs != list(range(1, len(idxs) + 1)):
        errors.append(f"manifest.pages 的 index 必须从 1 连续递增，实际为 {idxs}")

    if isinstance(manifest, dict) and manifest.get("pageCount") != len(pages_meta):
        errors.append(
            f"manifest.pageCount({manifest.get('pageCount')}) ≠ pages 数组长度({len(pages_meta)})"
        )

    for pm in pages_meta:
        if not isinstance(pm, dict):
            errors.append(f"manifest.pages 中存在非对象项：{pm!r}")
            continue
        rel = pm.get("file", "")
        if not src.exists(rel):
            errors.append(f"manifest 声明的页文件不存在：{rel}")
            continue
        try:
            page = src.read_json(rel)
        except Exception as e:
            errors.append(f"{rel} 解析失败：{e}")
            continue

        errors += schema_errors(page, pschema, rel)
        collect_unknown_keys(page, pschema.get("properties", {}).keys(), rel, info)

        if page.get("pageIndex") != pm.get("index"):
            errors.append(f"{rel}: pageIndex({page.get('pageIndex')}) 与 manifest.index({pm.get('index')}) 不一致")

        # 页尺寸一致性（警告级）
        dsz = manifest.get("defaultPageSizeMm") or {}
        psz = page.get("sizeMm") or {}
        if dsz and psz and (abs(q3(dsz.get("w", 0)) - q3(psz.get("w", 0))) > 0.01
                            or abs(q3(dsz.get("h", 0)) - q3(psz.get("h", 0))) > 0.01):
            warnings.append(f"{rel}: 页尺寸 {psz} 与 defaultPageSizeMm {dsz} 不同（合法，但确认是否有意为之）")

        n_strokes = 0
        n_points = 0
        for st in page.get("strokes", []) or []:
            sid = st.get("id")
            if sid in seen_stroke_ids:
                errors.append(f"笔画 id 重复：{sid}（{seen_stroke_ids[sid]} 与 {rel}）")
            elif sid:
                seen_stroke_ids[sid] = rel
            pts = st.get("points") or []
            n_strokes += 1
            n_points += len(pts)

            # 时间戳严格递增
            ts = [p[3] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 4]
            if any(b <= a for a, b in zip(ts, ts[1:])):
                warnings.append(f"{rel}/{sid}: 时间戳非严格递增（回放会受影响）")

            # 坐标 3 位小数的规范化提示
            for p in pts:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    for v in p[:2]:
                        if isinstance(v, float) and len(repr(v).split(".")[-1].rstrip("0")) > 3:
                            warnings.append(
                                f"{rel}/{sid}: 坐标精度超过 3 位小数（跨端比对会不一致）"
                            )
                            break
                    break

        total_strokes += n_strokes
        total_points += n_points
        page_stats.append({
            "index": page.get("pageIndex"),
            "strokes": n_strokes,
            "points": n_points,
            "shapes": len(page.get("shapes", []) or []),
            "images": len(page.get("images", []) or []),
            "textBoxes": len(page.get("textBoxes", []) or []),
            "contentHash": page_content_hash(page),
        })

        # renderedAs 指向的 shape 必须存在
        shape_ids = {s.get("id") for s in (page.get("shapes") or []) if isinstance(s, dict)}
        for st in page.get("strokes", []) or []:
            ra = st.get("renderedAs")
            if ra and ra not in shape_ids:
                errors.append(f"{rel}: stroke {st.get('id')} 的 renderedAs={ra} 不存在于 shapes")

    # ---- 6. AI 批注 ----
    aschema = load_schema(ANNOT_SCHEMA)
    annots_meta = manifest.get("aiAnnotations", []) if isinstance(manifest, dict) else []
    annot_kinds = []
    for am in annots_meta:
        if not isinstance(am, dict):
            continue
        rel = am.get("file", "")
        if not src.exists(rel):
            errors.append(f"manifest 声明的批注文件不存在：{rel}")
            continue
        try:
            annot = src.read_json(rel)
        except Exception as e:
            errors.append(f"{rel} 解析失败：{e}")
            continue
        errors += schema_errors(annot, aschema, rel)
        annot_kinds.append(annot.get("kind"))
        if annot.get("pageIndex") != am.get("pageIndex"):
            errors.append(f"{rel}: pageIndex 与 manifest 索引不一致")
        # anchor.strokeIds 必须都存在于笔画集合
        for sid in (annot.get("anchor") or {}).get("strokeIds", []) or []:
            if sid not in seen_stroke_ids:
                errors.append(f"{rel}: anchor.strokeIds 引用了不存在的笔画 {sid}")

    # ---- 7. checksums（可选） ----
    if src.exists("checksums.sha256"):
        import hashlib
        try:
            lines = src.read_bytes("checksums.sha256").decode("utf-8-sig").strip().splitlines()
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                want, name = parts[0].strip(), parts[1].strip().lstrip("*")
                if not src.exists(name):
                    errors.append(f"checksums.sha256 声明的文件不存在：{name}")
                    continue
                got = hashlib.sha256(src.read_bytes(name)).hexdigest()
                if got != want:
                    errors.append(f"校验和不匹配：{name}（文件可能被截断或篡改）")
        except Exception as e:
            warnings.append(f"checksums.sha256 读取失败：{e}")

    digest = {
        "source": str(src.target),
        "schemaVersion": sv,
        "docId": manifest.get("docId") if isinstance(manifest, dict) else None,
        "title": manifest.get("title") if isinstance(manifest, dict) else None,
        "platform": manifest.get("platform") if isinstance(manifest, dict) else None,
        "pageCount": len(pages_meta),
        "totalStrokes": total_strokes,
        "totalPoints": total_points,
        "pages": page_stats,
        "annotations": annot_kinds,
        "annotationCount": len(annot_kinds),
    }
    return _report(errors, warnings, info, digest)


def _report(errors, warnings, info, digest):
    return {"errors": errors, "warnings": warnings, "info": info, "digest": digest}


# --------------------------------------------------------------------------
# 跨端比对
# --------------------------------------------------------------------------
COMPARE_KEYS = ["pageCount", "totalStrokes", "totalPoints", "annotationCount"]


def compare(d1: dict, d2: dict):
    diffs = []
    for k in COMPARE_KEYS:
        a, b = d1.get(k), d2.get(k)
        if a != b:
            diffs.append(f"{k}: {a!r} ≠ {b!r}")

    if d1.get("schemaVersion") != d2.get("schemaVersion"):
        diffs.append(f"schemaVersion: {d1.get('schemaVersion')!r} ≠ {d2.get('schemaVersion')!r}")

    if sorted(d1.get("annotations") or []) != sorted(d2.get("annotations") or []):
        diffs.append(f"annotations 种类不同：{d1.get('annotations')} vs {d2.get('annotations')}")

    p1 = {p.get("index"): p for p in d1.get("pages") or []}
    p2 = {p.get("index"): p for p in d2.get("pages") or []}
    for idx in sorted(set(p1) | set(p2)):
        a, b = p1.get(idx), p2.get(idx)
        if a is None or b is None:
            diffs.append(f"第 {idx} 页只存在于一侧")
            continue
        for k in ("strokes", "points", "shapes"):
            if a.get(k) != b.get(k):
                diffs.append(f"第 {idx} 页 {k}: {a.get(k)} ≠ {b.get(k)}")
        ha, hb = a.get("contentHash"), b.get("contentHash")
        if ha and hb and ha != hb:
            diffs.append(
                f"第 {idx} 页 内容指纹不同（坐标/笔压/时间有差异）：{ha} ≠ {hb}"
            )
    return diffs


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    raw = argv[1:]
    # 取 --out 的值（不参与位置参数解析）
    out_path = None
    if "--out" in raw:
        i = raw.index("--out")
        if i + 1 < len(raw):
            out_path = raw[i + 1]
        raw = raw[:i] + raw[i + 2:]

    args = [a for a in raw if not a.startswith("--")]
    flags = {a for a in raw if a.startswith("--")}

    if not args:
        print(__doc__)
        return 2

    if "--compare" in flags:
        if len(args) != 2:
            print("用法：validate.py a.digest.json b.digest.json --compare", file=sys.stderr)
            return 2
        def _load_digest(p):
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except UnicodeDecodeError:
                # PowerShell 的 > 重定向会写成 UTF-16LE，这是最常见的坑
                with open(p, "r", encoding="utf-16") as f:
                    return json.load(f)

        d1 = _load_digest(args[0])
        d2 = _load_digest(args[1])
        diffs = compare(d1, d2)
        if diffs:
            print(f"❌ 两端不一致，共 {len(diffs)} 处：")
            for d in diffs:
                print("  -", d)
            return 1
        print("✅ 两端完全一致（pageCount / totalStrokes / totalPoints / annotations / 分页统计）")
        return 0

    target = Path(args[0])
    if not target.exists():
        print(f"[错误] 不存在：{target}", file=sys.stderr)
        return 2

    src = Source(target)
    try:
        rep = validate(src)
    finally:
        src.close()

    if "--digest" in flags:
        text = json.dumps(rep["digest"], ensure_ascii=False, indent=2)
        if out_path:
            Path(out_path).write_text(text, encoding="utf-8")   # 永远 UTF-8 无 BOM
            print(f"已写入 {out_path}")
        else:
            print(text)
        return 0 if not rep["errors"] else 1

    if "--json" in flags:
        text = json.dumps(rep, ensure_ascii=False, indent=2)
        if out_path:
            Path(out_path).write_text(text, encoding="utf-8")
            print(f"已写入 {out_path}")
        else:
            print(text)
        return 0 if not rep["errors"] else 1

    # 人类可读模式
    d = rep["digest"]
    print(f"文件：{target}")
    if d:
        print(f"  标题      {d['title']}")
        print(f"  平台      {d['platform']}   格式 v{d['schemaVersion']}")
        print(f"  页数      {d['pageCount']}")
        print(f"  笔画/点   {d['totalStrokes']} / {d['totalPoints']}")
        print(f"  批注      {d['annotationCount']} 条 {d['annotations'] or ''}")
        print("  分页：")
        for p in d["pages"]:
            print(f"    第{p['index']}页  笔画{p['strokes']:>4}  点{p['points']:>6}"
                  f"  图形{p['shapes']:>2}  图{p['images']:>2}  文本框{p['textBoxes']:>2}")

    if rep["errors"]:
        print(f"\n❌ 发现 {len(rep['errors'])} 个错误：")
        for e in rep["errors"]:
            print("  -", e)
    if rep["warnings"]:
        print(f"\n⚠️  {len(rep['warnings'])} 个警告：")
        for w in rep["warnings"][:20]:
            print("  -", w)
        if len(rep["warnings"]) > 20:
            print(f"  ...（其余 {len(rep['warnings']) - 20} 条略）")
    if rep["info"]:
        print(f"\nℹ️  {len(rep['info'])} 条提示（未知字段已保留）：")
        for i in rep["info"][:10]:
            print("  -", i)

    print("\n✅ 校验通过" if not rep["errors"] else "\n❌ 校验未通过")
    return 0 if not rep["errors"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
