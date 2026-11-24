#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simulate_stream.py —— 本地假 AI 网关（不需要任何模型、不花钱）

两个用途：

  1) 看流是什么样的（理解 SSE）
       python simulate_stream.py --demo
     终端里会一个字一个字吐出来，最后打出结构化的卡片 JSON。

  2) 给两个端开发界面用（关键！）
       python simulate_stream.py --serve --port 8787
     Windows 端 / 鸿蒙端把 endpoint 指向 http://127.0.0.1:8787/v1/teach/ai，
     就能在"没有真模型"的情况下把界面全部做完。
     联调那天只需要把 URL 换掉——这是省时间的最大一招。

还可以人为制造故障，测降级：
       python simulate_stream.py --serve --port 8787 --fault timeout
       python simulate_stream.py --serve --port 8787 --fault bad_shape
       python simulate_stream.py --serve --port 8787 --fault blocked
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE.parent.parent / "schemas" / "ai-capability.schema.json"


# --------------------------------------------------------------------------
# 三种能力的固定返回值（跟 04-AI能力协议 的示例完全一致）
# --------------------------------------------------------------------------
SOLVE_CARD = {
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
    "anchor": {"pageIndex": 1, "bboxMm": {"x": 600.0, "y": 80.0, "w": 320.0, "h": 120.0}},
}

SHAPE_RESULT = {
    "kind": "shape",
    "shapeType": "triangle",
    "params": {"verticesMm": [[120.0, 120.0], [520.0, 120.0], [120.0, 360.0]],
               "isRightAngle": True},
    "autoLabels": [{"type": "right_angle", "at": [120.0, 120.0]}],
    "confidence": 0.93,
    "decidedBy": "local",
}

HANDOUT = {
    "kind": "handout",
    "title": "一元二次方程 第2课时",
    "sections": [
        {
            "heading": "一、因式分解法",
            "points": ["二次项系数为 1 时，找两数积为常数项、和为一次项系数",
                       "分解后令每个因式为 0"],
            "formulas": ["x^2+(a+b)x+ab=(x+a)(x+b)"],
            "figures": [{"pageIndex": 1, "shapeId": "sh_0001"}],
        },
        {
            "heading": "二、易错点",
            "points": ["漏解：只写一个根", "忘记检验判别式"],
            "formulas": [],
            "figures": [],
        },
    ],
    "mindmap": {
        "text": "一元二次方程",
        "children": [
            {"text": "解法", "children": [{"text": "因式分解法"}, {"text": "求根公式"}]},
            {"text": "判别式", "children": [{"text": "Δ>0 两解"}, {"text": "Δ=0 一解"}]},
        ],
    },
}

CAPS = {
    "lasso_solve": SOLVE_CARD,
    "sketch_to_shape": SHAPE_RESULT,
    "board_to_handout": HANDOUT,
}

# 逐字流式播放这些"思考过程"（只是为了让界面看起来在动）
NARRATION = {
    "lasso_solve": "正在识别圈选内容…识别到一元二次方程，正在规划解题步骤…",
    "sketch_to_shape": "正在分析笔迹几何特征…拟合残差，判断闭合性…",
    "board_to_handout": "正在逐页提取知识点…合并同类…生成讲义结构…",
}


def schema_validator():
    """有 jsonschema 就用它校验固定返回值，确保假网关本身是合规的。"""
    try:
        import jsonschema
    except ImportError:
        return None
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    return jsonschema.Draft202012Validator(schema)


# --------------------------------------------------------------------------
# SSE 生成
# --------------------------------------------------------------------------
def sse(event: str, data: dict) -> bytes:
    """SSE 帧：event: xxx\\ndata: {json}\\n\\n"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def stream_events(capability: str, delay: float = 0.04):
    """按协议顺序产出 (event, data) 二元组。"""
    cap = capability if capability in CAPS else "lasso_solve"
    card = CAPS[cap]

    yield "task.started", {"requestId": "sim-" + uuid.uuid4().hex[:8],
                           "model": "simulate-stream-v1",
                           "ts": int(time.time() * 1000)}

    narration = NARRATION[cap]
    chunk = ""
    for i, ch in enumerate(narration):
        chunk += ch
        if len(chunk) >= 4 or i == len(narration) - 1:
            yield "task.chunk", {"text": chunk}
            chunk = ""

    yield "task.card", card
    yield "task.usage", {"tokensIn": 1432, "tokensOut": 587, "costCny": 0.0031}
    yield "task.done", {"status": "ok", "latencyMs": int(delay * 1000 * 40)}


def fault_events(fault: str):
    """故障注入，用来测客户端的降级路径。"""
    if fault == "timeout":
        yield "task.started", {"requestId": "sim-fault", "model": "simulate-stream-v1",
                               "ts": int(time.time() * 1000)}
        yield "task.chunk", {"text": "正在识别圈选内容…"}
        yield "task.error", {"code": "E_MODEL_TIMEOUT", "message": "模型超时", "retryable": True}
        return
    if fault == "bad_shape":
        yield "task.started", {"requestId": "sim-fault", "model": "simulate-stream-v1",
                               "ts": int(time.time() * 1000)}
        yield "task.chunk", {"text": "正在识别…"}
        # 故意发一个不合 schema 的卡片（steps 10 条）
        bad = dict(SOLVE_CARD)
        bad["steps"] = [{"index": i + 1, "text": f"第{i+1}步"} for i in range(10)]
        yield "task.card", bad
        yield "task.done", {"status": "ok", "latencyMs": 800}
        return
    if fault == "blocked":
        yield "task.started", {"requestId": "sim-fault", "model": "simulate-stream-v1",
                               "ts": int(time.time() * 1000)}
        yield "task.error", {"code": "E_CONTENT_BLOCKED", "message": "内容无法处理", "retryable": False}
        return
    yield from stream_events("lasso_solve")


# --------------------------------------------------------------------------
# HTTP 服务模式
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    fault = "none"
    delay = 0.04

    def log_message(self, fmt, *args):  # 静音默认日志
        pass

    def _not_found(self):
        self.send_response(404)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'{"error":"NOT_FOUND"}')

    def do_GET(self):
        if self.path.startswith("/health"):
            body = json.dumps({"ok": True, "capabilities": list(CAPS),
                               "fault": self.fault}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._not_found()

    def do_POST(self):
        if not self.path.startswith("/v1/teach/ai"):
            self._not_found()
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8-sig") or "{}")
        except Exception:
            req = {}

        cap = req.get("capability", "lasso_solve")
        ver = self.headers.get("X-Contract-Version", "4")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Request-Id", req.get("requestId", "sim"))
        self.send_header("X-Accel-Buffering", "no")   # 告诉反代别缓冲
        self.end_headers()
        self.close_connection = True                  # 发完即关，SSE 的标准结束方式

        try:
            if str(ver) != "4":
                for ev, data in fault_events("version"):
                    self.wfile.write(sse(ev, data))
                    self.wfile.flush()
                self.wfile.write(sse("task.error", {"code": "E_VERSION_UNSUPPORTED",
                                                    "message": "契约版本不匹配",
                                                    "retryable": False}))
                self.wfile.flush()
                return

            events = fault_events(self.fault) if self.fault != "none" else stream_events(cap, self.delay)
            for ev, data in events:
                self.wfile.write(sse(ev, data))
                self.wfile.flush()
                time.sleep(self.delay)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端提前断开，正常


def serve(port: int, fault: str, delay: float):
    Handler.fault = fault
    Handler.delay = delay
    print(f"假 AI 网关已启动： http://127.0.0.1:{port}/v1/teach/ai")
    print(f"  健康检查： http://127.0.0.1:{port}/health")
    print(f"  故障注入： {fault}（none 表示正常）")
    print(f"  能力：     {', '.join(CAPS)}")
    print("  Ctrl+C 结束\n")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()


# --------------------------------------------------------------------------
def demo(capability: str, delay: float):
    v = schema_validator()
    print(f"=== 模拟 {capability} 的 SSE 流（delay={delay}s）===\n")
    n = 0
    for ev, data in stream_events(capability, delay):
        payload = json.dumps(data, ensure_ascii=False)
        if len(payload) > 160:
            payload = payload[:160] + f" …（共 {len(payload)} 字符）"
        print(f"  event: {ev:<14} data: {payload}")
        n += 1
        time.sleep(delay)

    print(f"\n=== 共 {n} 个事件 ===")
    if v is not None:
        card = CAPS.get(capability, SOLVE_CARD)
        errs = sorted(v.iter_errors(card), key=lambda e: list(e.path))
        if errs:
            print("❌ 固定返回值不符合 schemas/ai-capability.schema.json：")
            for e in errs:
                print("   -", "/".join(str(x) for x in e.path) or "(根)", "→", e.message)
            return 1
        print("✅ 固定返回值通过 ai-capability.schema.json 校验")
    return 0


def main(argv):
    args = sys.argv[1:]
    cap = "lasso_solve"
    if "--cap" in args:
        cap = args[args.index("--cap") + 1]

    delay = 0.04
    if "--delay" in args:
        delay = float(args[args.index("--delay") + 1])

    if "--serve" in args:
        port = 8787
        if "--port" in args:
            port = int(args[args.index("--port") + 1])
        fault = "none"
        if "--fault" in args:
            fault = args[args.index("--fault") + 1]
        serve(port, fault, delay)
        return 0

    if "--demo" in args or len(args) == 0:
        return demo(cap, delay)

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
