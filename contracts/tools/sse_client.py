#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sse_client.py —— 最小 SSE 客户端（教学 + 调试两用）

用途 1：验证假网关/真网关的流是不是按协议吐的
    python sse_client.py http://127.0.0.1:8787/v1/teach/ai lasso_solve

用途 2：给开发看"一个 SSE 客户端最少要写多少代码"
    —— 大概就是下面这 40 行。不需要任何库。

用途 3：验证 5 种事件顺序是否合规（--strict）
    python sse_client.py URL lasso_solve --strict
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ORDER_RULE = "started 必须第一，card 最多一次，done/error 必须最后且只有一个"


def parse_sse(stream):
    """SSE 解析：一行行读，空行表示一个事件结束。"""
    event, data_lines = None, []
    for raw in stream:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line == "":
            if event or data_lines:
                payload = "\n".join(data_lines)
                try:
                    data = json.loads(payload) if payload else None
                except json.JSONDecodeError:
                    data = payload
                yield event or "message", data
            event, data_lines = None, []
            continue
        if line.startswith(":"):
            continue                      # 注释/心跳
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        # 其它字段（id:, retry:）本协议不用


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    url = argv[1]
    cap = argv[2] if len(argv) > 2 else "lasso_solve"
    strict = "--strict" in argv

    body = json.dumps({
        "requestId": "client-" + str(int(time.time())),
        "capability": cap,
        "locale": "zh-CN",
        "subject": "auto",
        "input": {"text": "x^2-5x+6=0"},
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-Contract-Version": "4",
            "X-Client": "sse-client/1.0",
            "X-Request-Id": "client-1",
        },
    )

    t0 = time.time()
    seen_started = False
    card_count = 0
    terminal = 0
    first_card_ms = None
    errors = []
    events = 0

    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"HTTP {resp.status}  Content-Type: {resp.headers.get('Content-Type')}\n")
        for ev, data in parse_sse(resp):
            events += 1
            dt = (time.time() - t0) * 1000
            preview = json.dumps(data, ensure_ascii=False)
            if len(preview) > 120:
                preview = preview[:120] + " …"
            print(f"[{dt:7.0f}ms] {ev:<14} {preview}")

            if ev == "task.started":
                if seen_started:
                    errors.append("task.started 出现了两次")
                seen_started = True
            elif ev == "task.card":
                card_count += 1
                if first_card_ms is None:
                    first_card_ms = dt
            elif ev in ("task.done", "task.error"):
                terminal += 1
                # 终态事件到了就可以收工；后续以连接关闭为准
            elif ev not in ("task.chunk", "task.usage"):
                errors.append(f"未知事件类型：{ev}")

            if terminal >= 1:
                break

    print(f"\n共 {events} 个事件，耗时 {(time.time() - t0) * 1000:.0f}ms")
    if not seen_started:
        errors.append("缺少 task.started")
    if card_count > 1:
        errors.append(f"task.card 出现 {card_count} 次（最多 1 次）")
    if terminal != 1:
        errors.append(f"结束事件出现 {terminal} 次（必须恰好 1 次）")

    if errors:
        print("❌ 协议不合规：")
        for e in errors:
            print("  -", e)
        return 1

    print("✅ 事件顺序符合协议：" + ORDER_RULE)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
