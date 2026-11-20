# AI 教学能力网关（真网关 v1.0）

> **这是艾尼这一岗的核心交付物。**
> 两个开发组不关心后面接哪个模型——他们只认这份协议和这个地址。
> 换模型只改一个 config 文件，两组一行代码都不用动。**这就是"AI 能力编排"的实际含义。**

---

## 三种运行模式

| 模式 | 命令 | 用途 |
|---|---|---|
| **离线** | `python server.py --offline` | 没有 API key 时开发界面用；返回预置卡片，事件流是真的 |
| **真上游** | `python server.py --config config.json` | 接 DeepSeek / Qwen / 智谱 / MoonShot / 本地 ollama |
| **自测** | `python server.py --selftest` | 内置假上游，端到端验证 10 项，不需要任何 key |

---

## 接真模型：3 步

### 第 1 步：复制配置

```powershell
cd F:\DSH\projects\AI教学助手-架构交付\gateway
copy config.example.json config.json
```

### 第 2 步：填 key（二选一）

**方式 A：写进 config.json**
```json
"api_key": "sk-你的key"
```

**方式 B：走环境变量（推荐，不会误传文件）**
```powershell
$env:DEEPSEEK_API_KEY = "sk-你的key"
```

### 第 3 步：起服务

```powershell
$py = "C:\Users\ZhuanZ（无密码）\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py server.py --config config.json --port 8788
```

看到这行就成功了：
```
网关启动 http://127.0.0.1:8788/v1/teach/ai
```

---

## 两个端怎么连

### Windows 端（同一台机器）

```
endpoint = http://127.0.0.1:8788/v1/teach/ai
```

### 鸿蒙平板（同一个 WiFi）

先查本机局域网 IP：

```powershell
ipconfig | Select-String "IPv4"
```

然后平板填：

```
endpoint = http://192.168.x.x:8788/v1/teach/ai
```

**如果连不上，99% 是防火墙**。放行：

```powershell
New-NetFirewallRule -DisplayName "InkTeach AI Gateway" -Direction Inbound -LocalPort 8788 -Protocol TCP -Action Allow
```

（这条需要管理员。没有管理员就用 `--port 80` 试试，但 80 也可能被占。）

### 必带请求头

```
Content-Type: application/json
X-Contract-Version: 1
```

不带 `X-Contract-Version: 1` 也能用；带了其他值会被拒（防止老客户端硬连）。

---

## 一次完整调用长什么样

```bash
curl -N -X POST http://127.0.0.1:8788/v1/teach/ai \
  -H "Content-Type: application/json" \
  -H "X-Contract-Version: 1" \
  -d '{"requestId":"t1","capability":"lasso_solve","subject":"math","context":{"gradeLevel":"junior_high"},"input":{"text":"x^2-5x+6=0"}}'
```

返回（严格按这个顺序）：

```
event: task.started
data: {"requestId":"t1","model":"deepseek-chat","ts":...}

event: task.chunk
data: {"text":"正在识别"}

event: task.chunk
data: {"text":"圈选内容"}

event: task.card
data: {"kind":"solve","title":"...","steps":[...]}

event: task.usage
data: {"tokensIn":812,"tokensOut":204,"costCny":0.0012}

event: task.done
data: {"status":"ok","latencyMs":3210}
```

---

## 网关替你挡掉的事（这些是它的价值）

| 问题 | 网关怎么处理 |
|---|---|
| 模型输出带 ` ```json ` 围栏 | 自动剥离 |
| 模型输出后面继续啰嗦 | 取平衡括号，截断多余部分 |
| 模型漏字段 | `coerce_card` 补齐 + 限制条数 |
| 模型超出条数限制（比如 8 步） | 截断到 5 步 |
| 输出里有 `<script>` | 递归清洗所有字符串字段 |
| 学生手写「忽略以上指令」 | 模式匹配拦截，直接回 `E_CONTENT_BLOCKED`，**不发给模型** |
| 上游 429 / 超时 / 断连 | 重试 1 次 → 还不行就降级到预置卡片（演示不白屏） |
| 同一块区域反复圈 | 5 分钟内走缓存，0 token |
| 模型返回的 JSON 不合 schema | 把 schema 报错回灌给模型，让它自己修一次 |

---

## 演示保命策略（**必须提前做**）

演示前一小时，跑这两个：

```powershell
# 终端 1：网关（接真模型）
& $py server.py --config config.json --port 8788

# 终端 2：测一遍
& $py "..\contracts\tools\sse_client.py" http://127.0.0.1:8788/v1/teach/ai lasso_solve --strict
```

如果现场网络挂了：

1. **不要慌**，网关有自动降级——上游不通会自动返回预置卡片，界面照常有东西
2. 如果连网关都挂了，现场切 `--offline` 重启（3 秒）
3. 兜底视频永远在手边

---

## 自测（改完代码必跑）

```powershell
& $py server.py --selftest
```

应该是 **10/10 通过**。这个数字掉了说明你改坏了某条链路：

1. 事件顺序
2. 有 card
3. card 通过 schema
4. chunk 有内容
5. 注入被拦截
6. 图形能力出卡
7. 讲义能力出卡
8. handout 通过 schema
9. 输出不含 `<script>`
10. 版本不匹配报对应错误

---

## 换模型（比赛现场可以秀这个）

改 `config.json` 三行即可，两个端不用动：

```json
"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
"model": "qwen-plus",
"api_key_env": "DASHSCOPE_API_KEY"
```

`config.example.json` 里已经给了四家现成配置。

**答辩时可以说**：「我们的 AI 能力与模型解耦，换模型只改配置，双端零改动。」这是架构分。

---

## 成本

按 DeepSeek 价格粗算（以实际账单为准）：

| 能力 | 输入 | 输出 | 单次 |
|---|---|---|---|
| lasso_solve | ~800 token | ~250 token | ≈ ¥0.002 |
| sketch_to_shape | ~400 token | ~120 token | ≈ ¥0.001 |
| board_to_handout | ~6000 token | ~1500 token | ≈ ¥0.015 |

**一节课**（圈 20 次 + 生成 1 份讲义）≈ **¥0.06**。

这个数字要能随口说出来。
