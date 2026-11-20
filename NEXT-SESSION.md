# 新会话接力卡（开新会话时把这段贴进去）

> 生成于 2026-11-19 21:35，因为上一个会话上下文已达 **~572k tokens**，明显变慢。
> 用法：开新会话 → 把本文件路径发给助手 → 接着干。

---

## 一句话状态

《AI 教学助手》架构交付包已完成并全部跑通，等老大看完 `00-先看这份` 后开始实际操作（访谈老师、填场景卡、跟两组对契约）。

---

## 已完成（不用重做）

`F:\DSH\projects\AI教学助手-架构交付\` —— 33 个文件 / 281 KB

- 00–07 八份文档（00 是白话入口）
- `schemas/` 5 份 JSON Schema
- `contracts/ai-testset.jsonl` 33 条测试集
- `contracts/golden-vectors/` 3 组黄金向量 + expected
- `contracts/tools/` 5 个 Python 工具
- `prompts/` 3 份模板
- `templates/` 3 份表单

**验证状态**：`selftest.py` 12/12 通过、`gen_golden.py --check` 全绿、假网关 11 事件合规、SSE 客户端协议校验通过。

---

## 下一步（按优先级）

1. **老大读 `00-先看这份-你的岗位到底是什么.md`**，确认方向对不对
2. **约 2 位老师访谈**（问题清单在 `03-四大场景需求卡.md` 末尾）
3. 用访谈结果替换场景卡里的 `[待验证]`
4. 把 `06-工具与环境清单.md` 里"给两组的第二天任务"发给 Windows 组和鸿蒙组

---

## 常用命令（复制即用）

```powershell
$py   = "C:\Users\ZhuanZ（无密码）\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$root = "F:\DSH\projects\AI教学助手-架构交付"
$env:PYTHONIOENCODING = "utf-8"

& $py "$root\contracts\tools\selftest.py"                                    # 自检
& $py "$root\contracts\tools\validate.py" "$root\contracts\golden-vectors\v1-basic.icink"  # 校验
& $py "$root\contracts\tools\simulate_stream.py" --serve --port 8787         # 假网关
& $py "$root\contracts\tools\simulate_stream.py" --demo                      # 看流
```

---

## 已知的坑（别再踩）

- PowerShell `>` 重定向写 UTF-16 → 用 `--out` 参数
- `.ps1` 被执行策略拦 → 写 `.py`
- 坐标超 3 位小数 → 跨端比对必挂（校验器会警告）
- SSE 不关连接 → 客户端卡到超时（假网关已修）

---

## 环境事实

- Python：`C:\Users\ZhuanZ（无密码）\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（已装 jsonschema 4.26）
- `DSH_HOME` = `C:\Users\ZhuanZ（无密码）\.dsh`（1.6 GB，在 C 盘）
- 本机 PowerShell 5.1，`.ps1` 默认禁
