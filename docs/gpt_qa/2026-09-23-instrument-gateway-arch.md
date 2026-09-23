# GPT 讨论：仪器控制 MCP 网关化架构（2026-09-23）

<!-- chatgpt-discuss: session=instrument-gateway-arch conv=https://chatgpt.com/c/6ab37be8-9a44-83e9-a274-4e487364b947 updated=2026-09-23 15:16:34 rounds=1 -->
- 会话: instrument-gateway-arch | 链接: https://chatgpt.com/c/6ab37be8-9a44-83e9-a274-4e487364b947

## Q1 2026-09-23 15:16:34
**Q:** 背景：我在维护一个仪器控制项目（Python，控制 RIGOL/Keysight 等真实台式仪器）。现状分两层：

【库层】已经是干净的：每个设备一个独立 Python 包（sds_control 示波器、sdg_control 信号源、dg832_control 信号源、keysight_3446x 与 3458a 万用表、dh1766_control 电源、dho_control/mho_control 示波器、rigol_scope），共用 common/ 发现层与地址解析层（不写死 IP）。这些库可以直接 import 使用，已用于脚本。

【MCP 层】一个 server.py（约 3400 行，FastMCP），用 @device_tool() 装饰器把 57 个函数注册成 MCP 工具，模型侧名字是 mcp__instrument__<name>，前缀为 dg_ / sds_ / sdg_ / dmm_ / dho_ / mho_ / psu_ / ks3458a_ / instr_。每个工具的描述里内联了大量排障知识与实测结论（设备行为、强制流程、安全门语义）。安全护栏都在 server.py 里：复位类命令黑名单（confirm 也不放行）、输出/关机类需显式 confirm、写后回读验证、错误队列排空、审计落盘。

【消费方】DSH、Codex、Claude、opencode、zcode 等多个客户端，都走 MCP stdio。

【实测数据】这 57 个工具的定义（名称+描述+JSON Schema）在每次请求里占约 13.7k token，占该 harness 静态上下文注入总量（约 4 万 token）的 44%；而多数会话根本不碰仪器。

【我的猜想】想改成"按需暴露"，倾向不再堆一堆 MCP 工具。

三个候选方向：
方案A（网关）：只注册一个或极少数"申请入口"工具，例如 instrument(action, params)，真正能力由服务端自己实现 API，模型按需查询能力目录后再调用。
方案B（代码执行）：不做 MCP 工具堆，改为把库 + 一个稳定 CLI 暴露给 agent，让 agent 自己写 Python 脚本调用。工具定义几乎为零，且天然支持循环、扫频、批量采集这类组合操作。
方案C（混合）：保留少量高频工具（discover/status/query 等），其余走网关或脚本。

请帮我分析：

1. 这三种模式各自的取舍？特别是对"模型写脚本组合调用"这类场景，哪个更合适、为什么？

2. 单一网关工具的代价是什么（schema 变弱、模型必须先查能力目录、参数错误更难被发现）？业界有没有成熟的 progressive disclosure / 工具懒加载实践可以参考？

3. 安全护栏怎么在网关模式或脚本模式下保持？如果走脚本模式，模型可以绕过 MCP 层直接对仪器发任意 SCPI 命令，这个风险边界该怎么设计（例如护栏下沉到库层）？

4. 多客户端兼容性：有的客户端支持用配置过滤工具（glob 排除），有的不支持。这对方案选择有什么影响？

5. 如果要迁移，有没有推荐的分阶段路径（既降低风险，又不破坏现有可用性）？

请给出明确的推荐方案与理由，不要罗列所有可能性而不下结论。


**A:**
结论先给：

**推荐采用 C，但具体形态应是“轻量 MCP Broker + 按需能力发现 + 受控 Code Mode”，不建议长期保留一批高频设备工具。**

默认模型侧只看到约 4 到 5 个稳定工具：

```text
instr_discover()       # 当前有哪些仪器
instr_search(query)    # 搜能力
instr_describe(ids)    # 取完整 schema、语义、安全说明、示例
instr_call(op, args)   # 单次调用
instr_run(code/plan)   # 组合、循环、扫频、批量采集
```

现有 57 个 `dg_* / sds_* / ...` 工具继续保留为 **legacy profile**，用于兼容旧客户端和迁移期。最终业务能力仍然有 57 个甚至未来 200 个，只是不再全部进入模型静态上下文。

其中最关键的一点是：

> **`instr_run` 里的模型代码只能调用受控 instrument API，不能得到任意 Python、socket、pyvisa、subprocess、文件系统和网络能力。**

这实际上结合了 A 的低上下文成本和 B 的组合能力，同时避开纯 A 的弱 schema 与纯 B 最大的安全问题。

---

## 1. A / B / C 怎么选

### A：单一 Gateway

适合解决您当前最显性的 13.7k token 问题，但如果设计成：

```python
instrument(action: str, params: dict)
```

我不建议。

它会把原来的：

```text
57 个强类型 schema
```

压缩成：

```text
1 个几乎无类型的 dict
```

模型对参数名、单位、枚举、互斥参数、设备差异的错误只能等服务器运行时发现。

正确的 Gateway 应该采用：

```text
search → describe → validate → execute
```

`describe("sdg.set_frequency")` 动态返回：

```json
{
  "operation": "sdg.set_frequency",
  "schema": {...},
  "examples": [...],
  "safety": {...},
  "notes": [...]
}
```

执行时服务端仍然拿这个 schema 做严格验证。因此损失的是**静态模型可见 schema**，服务器端类型检查完全可以保留。

这正是目前 progressive disclosure 的主流方向。Anthropic 的 Tool Search 已明确支持 deferred loading，官方建议在工具超过 10 个或定义超过 10k token 时使用；其文档还指出，工具数量达到约 30 到 50 个以后，模型的工具选择准确率会明显受影响。您的 57 个工具和 13.7k token 正好落入这个区间。citeturn372374search0

### B：让 agent 自己写 Python

对于：

```text
for f in frequencies:
    gen.set_frequency(f)
    wait_settle()
    v = dmm.measure()
    results.append((f, v))
```

这种工作，**代码明显比逐次 MCP tool call 更合适**。

原因有四个：

1. 循环、条件、数据处理天然就是程序控制流。
2. 不需要每一次调用都经过一次 LLM inference。
3. 中间的 1000 个采样结果可以留在执行环境里，只把汇总结果送回模型。
4. 可以封装 cleanup、超时、锁、异常处理。

Anthropic 目前也专门提供了 Programmatic Tool Calling，其理由就是循环、条件和数据转换更适合由代码完成。Cloudflare 的 Code Mode 也采用同一模式，模型编写代码协调工具，再只把必要结果送回上下文。citeturn372374search2turn521784search3

所以从**执行模型**看，我赞成 B。

但我不赞成：

```text
agent shell
   ↓
python xxx.py
   ↓
import sds_control / pyvisa / socket
   ↓
真实仪器
```

这让 MCP 中的全部安全控制失去意义。

### C：我推荐的版本

应该是：

```text
                    ┌─ instr_call()
Agent → compact MCP ┤
                    └─ instr_run(code)
                              │
                       restricted runtime
                              │
                    guarded instrument API
                              │
                     policy / audit / lock
                              │
                    existing device libraries
                              │
                         VISA / LAN
```

这样脚本能力和安全边界可以同时保留。

Cloudflare 现在甚至已经正式提供这种 MCP 结构：一个 MCP server 可以只暴露 `code`，或者使用 `search + execute`；其 Cloudflare API MCP 用两个工具覆盖 2500 多个 API endpoint。citeturn521784search4turn521784search8

所以这已经不属于很实验性的架构猜想，progressive discovery + programmatic composition 已经形成明确实践。

---

# 2. 单一 Gateway 真正的问题

您列的三个代价都成立，但严重程度不同。

### 2.1 最大的问题是 schema discoverability

例如现在模型直接看到：

```python
sdg_set_frequency(
    channel: int,
    frequency_hz: float,
    ...
)
```

Gateway 后可能只看到：

```python
instr_call(
    operation: str,
    arguments: object
)
```

所以 `operation` 拼错、单位搞错、参数缺失不会被 MCP JSON Schema 提前拦住。

解决方案是把 schema 变成**按需数据**：

```text
instr_search("set signal generator frequency")
        ↓
sdg.set_frequency
sdg.configure_channel

instr_describe(["sdg.set_frequency"])
        ↓
完整 schema + 示例 + 陷阱 + 安全属性
```

然后模型调用：

```text
instr_call(
    op="sdg.set_frequency",
    args={"channel": 1, "frequency_hz": 10000}
)
```

服务端再次依据 registry 中同一个 schema 校验。

因此我建议建立一个真正的 **Operation Registry**，成为唯一事实源：

```python
Operation(
    id="sdg.set_frequency",
    summary=...,
    schema=...,
    examples=...,
    risk=...,
    implementation=...,
    notes=...,
)
```

然后：

```text
legacy MCP 57 tools
compact MCP
CLI
Code Mode SDK
documentation
```

全部从 registry 派生。

这样不会出现现在 `server.py` 描述、CLI、库 API、安全语义逐渐分叉的问题。

### 2.2 多一次 search 的 latency

确实存在。

但您的场景里：

```text
13.7k 静态 token × 每一轮
```

和：

```text
涉及仪器时多一次 10 到 100 ms 级本地目录查询
```

通常没有可比性。

而且一个会话里发现过：

```text
sdg.set_frequency
dmm.measure_dc_voltage
```

以后可以缓存，不需要反复搜索。

Anthropic 的 Tool Search 默认就是一次找 3 到 5 个相关工具，并自动载入其完整定义。citeturn372374search0

### 2.3 搜索召回错误

这个风险真实存在。

您的命名其实非常适合搜索：

```text
dg_
sds_
sdg_
dmm_
dho_
mho_
psu_
ks3458a_
instr_
```

建议 registry 保留结构化字段：

```text
device_family
operation
aliases
keywords
SCPI concepts
risk
```

例如：

```text
id: sdg.set_frequency
aliases:
  - set frequency
  - frequency
  - freq
  - configure generator frequency
keywords:
  - signal generator
  - SDG
  - source
  - Hz
```

57 项这个规模甚至不需要 embeddings，BM25 / keyword / prefix ranking 已经够用。

---

# 3. 安全护栏放哪里

这里我建议修正一个概念：

> **不要简单地“把 MCP 护栏下沉到设备库”。应当抽出一个 agent 不可绕过的 policy broker。**

分层可以是：

```text
drivers/
    sds_control
    sdg_control
    keysight_3446x
    ...

instrument_runtime/
    registry
    policy
    sessions
    locking
    verification
    audit

frontends/
    mcp_compact
    mcp_legacy
    cli
    code_runtime
```

现有那些干净的设备库可以继续做低层 driver。

所有 **agent-controlled execution path** 必须经过 `instrument_runtime`。

这样不会把：

```text
需要用户确认
Agent 安全语义
审计格式
禁止复位
```

这种上层策略污染到纯设备驱动里。

---

## 一个非常重要的安全问题

如果 agent 可以：

```python
import socket
socket.create_connection(("192.168.x.x", 5025))
send("*RST")
```

或者：

```python
import pyvisa
```

那么您在 Python library 里加多少安全检查都没有用。

**安全边界取决于 agent 是否拥有绕过 broker 的物理能力。**

所以纯方案 B 最大的问题其实不是软件架构，而是 capability containment。

理想部署是：

```text
agent/code sandbox
       │
       │ only IPC
       ▼
instrument broker
       │
       ├─ VISA
       ├─ USBTMC
       └─ TCP/5025
```

并使 agent runtime 本身：

```text
无 instrument VLAN 网络访问
无 USBTMC/VISA 设备访问
无任意 socket
无 subprocess
无任意 import
```

最强的方案甚至是：

```text
Agent PC              Instrument broker
无仪器网段权限   →     唯一能访问仪器 VLAN
```

如果都运行在 Windows 本机，也至少需要进程级 ACL、防火墙或其他 OS 隔离。

单靠：

```python
不要调用 socket
```

没有安全意义。

---

# 4. `instr_run()` 怎么设计

我建议不要让它执行：

```text
任意 Python
```

模型可以写“脚本”，但脚本环境是 capability sandbox。

例如它看到：

```python
scope = instrument.device("scope1")
gen = instrument.device("gen1")

for f in logspace(10, 100000, 100):
    gen.set_frequency(f)
    sleep(0.05)
    v = scope.measure_vpp(1)
    emit(f, v)
```

但环境没有：

```python
open
os
socket
subprocess
ctypes
pyvisa
importlib
eval
exec
```

每次：

```python
gen.set_frequency()
```

仍然经过：

```text
schema validation
policy
instrument lock
write
readback verification
error queue
audit
```

这和 Cloudflare Code Mode 的思想很接近，他们也是让模型生成代码，但工具调用穿过 sandbox 边界，并且 approval policy 与代码执行本身分离。citeturn521784search1turn521784search11

Python 自己做安全 sandbox 很难。我不会建议用：

```python
exec(code, {"__builtins__": ...})
```

作为安全边界。

更可靠的实现包括：

```text
隔离子进程 + OS 权限限制 + broker IPC
WASM
无 host capability 的 JS/QuickJS runtime
专用 DSL
```

从实现成本考虑，我会优先：

```text
受限子进程 + broker RPC
```

同时限制：

```text
最大执行时间
最大循环次数
最大调用次数
最大结果大小
允许访问的 device set
```

---

# 5. 您现有安全规则怎么迁移

我建议 Operation Registry 至少给每个 operation 这些属性：

```python
risk = READ_ONLY | CONFIG | OUTPUT | DESTRUCTIVE
requires_arm = bool
blocked = bool
verify = VERIFY_READBACK | VERIFY_ERROR_QUEUE | ...
idempotent = bool
timeout = ...
```

例如：

```text
scope.measure_vpp
    READ_ONLY

sdg.set_frequency
    CONFIG

sdg.output_on
    OUTPUT
    requires_arm = true

psu.output_on
    OUTPUT
    requires_arm = true

reset / factory reset
    blocked = true
```

现有：

* reset 黑名单
* 输出/关机确认
* write 后 readback
* error queue drain
* audit

全部移动到这个执行层。

MCP 自身已有 `readOnlyHint / destructiveHint / idempotentHint / openWorldHint` 等 tool annotations，但规范明确说明这些只是 hint，不应承担安全保证。citeturn970085search1turn970085search3

因此 annotation 可以继续输出给客户端做 UX，但真正的 gate 必须在 broker。

---

## `confirm=True` 也值得再审一下

如果当前是：

```python
psu_output_on(confirm=True)
```

而 `confirm` 是模型自己能填的参数，它不能构成强用户授权。

模型完全可以自行生成：

```json
{"confirm": true}
```

更稳妥的机制是 **arming capability**：

```text
用户/客户端
   ↓
显式授权：
device=psu1
actions=[output_on]
max_voltage=5V
expires=10min
   ↓
broker 发 arm_id
```

随后模型只能在这个授权范围内执行。

例如：

```text
arm_id = abc123

允许：
psu1 output_on
psu1 voltage <= 5V

拒绝：
psu2 output_on
psu1 12V
*RST
过期后的任何输出动作
```

而且 **arm_id 必须来自 agent 无法自行创建的授权渠道**。

这比一个 boolean `confirm` 强很多。

如果依赖 MCP UI approval，需要考虑客户端兼容性，所以我会把它当增强层，不作为唯一安全机制。

---

# 6. 为什么特别推荐 Code Mode 给扫频和批量采集

例如 1000 点扫频。

传统 tool calling：

```text
LLM
↓ set_frequency
LLM
↓ measure
LLM
↓ set_frequency
LLM
↓ measure
...
```

会产生大量 inference round trip 和 context accumulation。

Code Mode：

```python
for f in points:
    set_frequency(f)
    rows.append(measure())
return summarize(rows)
```

模型只做一次规划。

对仪器还有额外好处：可以把整个 run 放到一个显式 execution scope：

```python
with instrument.run(devices=["sdg1", "dmm1"]) as run:
    ...
```

broker 可以统一做：

```text
设备锁
session reuse
deadline
取消
异常 cleanup
audit run_id
结果文件
```

如果中途超时，可以执行定义好的：

```text
finally:
    safe_cleanup()
```

这比 agent 每次重新决定“下一条工具调用是什么”可靠得多。

---

# 7. 多客户端兼容性直接决定了不要依赖客户端过滤

您的这个判断很关键。

如果架构依赖：

```text
Claude 支持工具过滤
Codex 支持
客户端 X 不支持
```

最后还是必须保留 57 个静态工具给最弱客户端。

所以：

> **client-side filtering 只能作为优化，不能作为解决 13.7k token 的架构基础。**

MCP 协议本身支持工具列表发生变化。当前 2026-07-28 规范下，`tools/list_changed` 通过客户端主动订阅获得；各客户端是否利用动态列表仍属于 client behavior。citeturn970085search2

这意味着我也不建议您做：

```text
开始只有 3 个工具
↓
用户说“示波器”
↓
服务端动态注册 12 个 scope tools
↓
通知客户端 refresh
```

理论上漂亮，跨 DSH、Codex、Claude、opencode、zcode 时很容易出现兼容性差异。

**静态的 4 到 5 个 gateway tools 是跨客户端最稳的最低公分母。**

而且 MCP 最新协议自身也越来越倾向显式状态句柄。2026-07-28 版移除了协议层 session，并建议应用需要状态时自己发显式 handle。citeturn970085search0

所以例如：

```text
run_id
lease_id
arm_id
```

都应该显式传递，不依赖“这个 stdio 会话里服务器应该还记得”。

---

# 8. 我建议的具体 API

我会把最终默认 MCP surface 控制在下面 5 个。

### `instr_discover`

返回：

```text
logical_id
vendor/model
address
capability groups
status
```

不要返回所有完整 operation schema。

### `instr_search`

输入：

```json
{
  "query": "sweep signal generator frequency and measure AC voltage",
  "devices": ["gen1", "dmm1"],
  "limit": 8
}
```

返回：

```text
sdg.set_frequency
sdg.output
dmm.measure_ac_voltage
...
```

附一两行摘要。

### `instr_describe`

一次可以描述多个：

```text
schema
units
examples
behavior notes
known quirks
safety classification
```

您现在内联在 57 个 descriptions 里的排障知识，绝大部分应该搬到这里。

这一步本身就能大幅缩减 token。

### `instr_call`

用于：

```text
读一次电压
设置一次频率
读 IDN
```

保持低延迟。

### `instr_run`

用于：

```text
sweep
loop
batch acquisition
adaptive test
multi-device coordination
```

内部走相同 registry 和 policy。

这 5 个工具的稳定 schema 很容易压到约 1k 到 2k token 量级，和当前 13.7k 相比已经是数量级改善。

---

# 9. 不建议做的三件事

第一，不建议把默认接口做成纯：

```python
instrument(action, params)
```

没有 search/describe，模型使用体验会明显退化。

第二，不建议默认让 agent：

```text
shell → python → import 设备库
```

只要 agent 还能接触 VISA 或仪器网络，MCP 安全层就已经失去边界。

第三，不建议为了“按需暴露”大量依赖 MCP 动态 add/remove tool。协议能表达，客户端生态差异会成为长期兼容负担。

---

# 10. 迁移路径

我会分五阶段，而且第一阶段完全不改变外部行为。

### Phase 1：先做 Operation Registry

把当前：

```text
57 个 decorator
description
schema
implementation
safety
```

抽成单一 registry。

旧的：

```python
@device_tool()
def sdg_set_frequency(...):
```

改成自动从 registry 生成。

**此时 57 个 MCP 名字完全不变。**

这是最重要的一步，因为以后 compact MCP 和 legacy MCP 才不会形成两套实现。

### Phase 2：把安全执行路径抽成 Broker

形成：

```text
Operation Registry
      ↓
Policy / Validator
      ↓
Executor
      ↓
Device libraries
```

用现有 57 个工具跑完整 regression。

此阶段应验证：

```text
blacklist
confirm/arm
readback
error queue
audit
locking
timeouts
```

都不依赖 MCP wrapper。

### Phase 3：增加 compact profile

新增：

```text
instrument-mcp --profile compact
```

暴露那 4 到 5 个工具。

同时：

```text
instrument-mcp --profile legacy
```

继续暴露现在的 57 个名字。

不要让客户端名称决定服务器行为，显式 profile 更可测试。

### Phase 4：加入受限 `instr_run`

先只支持：

```text
纯控制流
数值运算
instrument proxy
```

逐步增加能力。

尤其先做：

```text
sweep
repeat
measure
collect
aggregate
```

这是收益最大的区域。

### Phase 5：compact 成为默认

通过真实会话比较：

```text
静态 token
总输入 token
tool-selection failure
invalid argument rate
执行 round trip
任务完成率
安全拒绝次数
平均仪器调用数量
```

稳定后将 compact 作为默认，legacy 保留一个较长兼容周期。

---

# 最终架构判断

我会定成：

```text
                 ┌───────────────────┐
                 │  MCP compact      │
                 │ discover/search   │
Agents ─────────▶│ describe/call/run │
                 └─────────┬─────────┘
                           │
Human scripts/CLI ─────────┤
                           ▼
                   Operation Registry
                           │
                    Policy Broker
                   ┌───────┼────────┐
                   │       │        │
                validate  audit   locking
                   │       │        │
                   └───────┼────────┘
                           ▼
                  existing libraries
                           ▼
                    real instruments
```

迁移期旁边保留：

```text
legacy MCP 57 tools
        │
        └────→ same Operation Registry
```

**所以我的选择是 C，但偏向“Gateway + Code Mode”，而非“保留十几个常用原生工具 + 其他另走一条路”。**

原因可以压缩成四条：

1. **57 工具、13.7k token 已经足以值得 progressive disclosure。**
2. **扫频、批采、条件控制天然适合模型写代码。**
3. **任意 Python 直连仪器会破坏您已经建立的安全边界。**
4. **固定的小 MCP surface 对 DSH、Codex、Claude、opencode、zcode 的兼容性明显优于依赖各客户端自己的懒加载能力。**

还有一个我认为值得趁这次迁移一起修正的点：**把“安全确认”从模型可填写的 `confirm=True` 升级成 broker 侧的 bounded arm/capability，并把设备、动作、参数上限和有效期绑定进去。** 对真实电源、信号源输出这类操作，这会让整个架构的安全语义清楚很多。
