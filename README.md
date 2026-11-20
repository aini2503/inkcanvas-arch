# AI 教学助手 · 需求与架构组交付包

> 这是给 **艾尼萨尔** 的整套工作材料。
> 覆盖：需求定义 → AI 能力编排 → 跨端数据契约，三块全在这。
>
> 生成时间：2026-11-19　可运行环境：本机 Python 3.12（已装 jsonschema 4.26）

---

## 先看这个（按顺序）

| 顺序 | 文件 | 你用它的场景 |
|---|---|---|
| 0️⃣ | [2天冲刺-艾尼作战手册.md](<2天冲刺-艾尼作战手册.md>) | **冲刺期先看这份。** 48 小时排期、砍功能清单、5 分钟演示剧本 |
| 1️⃣ | [00-先看这份-你的岗位到底是什么.md](<00-先看这份-你的岗位到底是什么.md>) | **现在就看。** 白话讲清你这岗在干嘛、要交什么、哪里会翻车 |
| 2️⃣ | [01-岗位拆解与每周动作.md](<01-岗位拆解与每周动作.md>) | 想知道"这周具体做啥"、开会怎么开 |
| 3️⃣ | [02-能力地图与补齐路径.md](<02-能力地图与补齐路径.md>) | 想知道缺什么、三周怎么补 |
| 4️⃣ | [03-四大场景需求卡.md](<03-四大场景需求卡.md>) | 访谈老师前后、写需求文档 |
| 🆕 | [各组Agent提示词包.md](<各组Agent提示词包.md>) | **发给 6 个组员**，每人粘自己那段进 Agent |

## 两块硬核技术（你的招牌）

| 文件 | 内容 |
|---|---|
| [04-AI能力协议.md](<04-AI能力协议.md>) | 三个 AI 能力的接口契约、SSE 五种事件、8 个错误码、**提示词注入防护**、成本预算 |
| [05-数据契约.md](<05-数据契约.md>) | `.icink` 格式规范、毫米坐标系、笔迹四元组、版本策略、黄金测试向量 |

## 落地执行

| 文件 | 内容 |
|---|---|
| [06-工具与环境清单.md](<06-工具与环境清单.md>) | 本机已有什么、装什么、日常命令速查、给两组的"第一天任务" |
| [07-排期与对接计划.md](<07-排期与对接计划.md>) | 八周甘特、周一/周五会议议程、答辩技术段落模板、风险表 |

---

## 能跑的东西（全部实测通过）

```powershell
# 设这两个变量（每次开新窗口都要设）
$py   = "C:\Users\ZhuanZ（无密码）\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$root = "F:\DSH\projects\AI教学助手-架构交付"
$env:PYTHONIOENCODING = "utf-8"
```

| 命令 | 作用 | 实测结果 |
|---|---|---|
| `& $py "$root\contracts\tools\gen_golden.py"` | 生成 3 组黄金测试向量 + 期望摘要 | ✅ 3/3 通过 |
| `& $py "$root\contracts\tools\validate.py" "$root\contracts\golden-vectors\v1-basic.icink"` | 校验一个 `.icink` | ✅ 3 页 / 20 笔画 / 352 点 |
| `& $py "$root\contracts\tools\selftest.py"` | 校验器自检（证明它能抓错） | ✅ **12/12** |
| `& $py "$root\contracts\tools\simulate_stream.py" --demo` | 看 SSE 流长什么样 | ✅ 11 个事件，顺序合规 |
| `& $py "$root\contracts\tools\simulate_stream.py" --serve --port 8787` | **起假 AI 网关**（开发界面必备） | ✅ 已实测 |
| `& $py "$root\contracts\tools\sse_client.py" http://127.0.0.1:8787/v1/teach/ai lasso_solve --strict` | 验证网关协议合规 | ✅ 通过 |
| `& $py "$root\contracts\tools\simulate_stream.py" --serve --port 8787 --fault timeout` | 人为造故障，测降级 | ✅ 返回 `E_MODEL_TIMEOUT` |

---

## 目录一览

```
AI教学助手-架构交付\
├── 00 ~ 07 ................. 八份文档（00 是入口）
├── schemas\ ................ 5 份 JSON Schema（机器校验，给开发）
├── contracts\
│   ├── ai-testset.jsonl .... 33 条 AI 测试集（含 4 条安全必过）
│   ├── golden-vectors\ ..... 3 个 .icink 样本 + 期望摘要
│   └── tools\ .............. 5 个 Python 工具
├── prompts\ ................ 3 份 prompt 模板（可直接用）
└── templates\ .............. 场景卡 / 互通检查表 / 变更单
```

---

## 三句话总结这套东西的用法

1. **拿去改，别当成成品。** 场景卡里的 `[待验证]` 都要用访谈结果替换；`[ ]` 空的地方都要填。
2. **先冻契约，再做增强。** W3 冻结 `.icink`，W4 冻结 AI 协议——之后只加可选字段，不改含义。
3. **每周五跑一次 `selftest.py` + 互通检查表。** 这是这个岗位唯一真正"可验证"的动作。

---

## 已知的坑（都踩过了，写在文档里）

- PowerShell 的 `>` 重定向写 UTF-16 → 用 `--out` 参数
- `.ps1` 被执行策略拦 → 写 `.py` 或 `-ExecutionPolicy Bypass`
- 坐标精度超 3 位小数 → 跨端比对必挂（校验器会警告）
- SSE 不关闭连接 → 客户端会卡到超时（假网关已修）
- 只比"笔画数"抓不到"点被搬了 3 毫米" → 加了 `contentHash` 逐页指纹
