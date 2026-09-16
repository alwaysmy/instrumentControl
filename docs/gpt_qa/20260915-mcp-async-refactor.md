# GPT 讨论：MCP 同步工具改异步方案评审（2026-09-15）

<!-- chatgpt-discuss: session=mcp-async-refactor conv=https://chatgpt.com/c/6aa95c5b-d710-83ea-9aec-92e23fc084dc updated=2026-09-15 23:02:53 rounds=3 -->
- 会话: mcp-async-refactor | 链接: https://chatgpt.com/c/6aa95c5b-d710-83ea-9aec-92e23fc084dc

## Q1 2026-09-15 22:42:50
**Q:** 我要把一台仪器控制 MCP 服务器（Python, FastMCP 1.27.0 / mcp SDK）的 50 个同步工具函数改成异步、并把超时做对。请审我的设计并指出错误。

## 现状（已实测的事实，不是推测）
1. 服务器是 stdio 传输的单进程 MCP 服务，50 个工具全是 `def f(...)-> str` 同步函数。FastMCP 对同步工具的调用路径是 `return fn(**args)`，直接跑在事件循环线程上（我读了 SDK 源码确认：只有 resources 用了 `anyio.to_thread.run_sync`，tools 没有）。
2. 所有工具内部共享一把全局锁 `_DEVICE_LOCK`（threading.Lock），在函数体内 `with _DEVICE_LOCK:` / `acquire(timeout=...)`。原因是仪器 I/O 必须串行（VISA 运行时不是线程安全的，且一个会话同一时刻只能跑一个命令）。所以工具执行天然互斥。
3. 设备 I/O 是阻塞的（pyvisa，`inst.query()`），单条命令正常几毫秒到几百毫秒；但个别设备会慢很多，实测某型号示波器的 `auto_scale` 闭环最坏情况约 90 秒（多档重试，每档内部有 6s 超时）。
4. 已知风险：某些设备/端口在某些状态下 VISA 调用会长时间不返回。实测过"配置 2 秒超时实际跑了 12.97 秒"（超时不被遵守），也观察到过 30 秒+ 才返回。
5. 目前我写的临时方案是：工具函数仍然同步，但外面套一层 `threading.Thread(daemon=True)` + `t.join(budget)`，超时就返回错误。**我知道这有问题**：`t.join()` 本身就阻塞事件循环线程，所以"超时后其他请求能快速失败"是假的——实际上整个服务器在 join 期间是停摆的。
6. 我还需要保留一个能力：把 `sys.stdout` 重定向到 stderr。因为 stdio 模式下 stdout 是 JSON-RPC 协议流，而底层设备库里有 `print()`（我已把本仓库的 print 改成 stderr，但第三方库如 pyvisa 仍可能打印；实测有过一次 stdout 污染导致客户端断开）。MCP SDK 在启动时用 `sys.stdout.buffer` 包了协议流，之后不再读 `sys.stdout` 对象，所以我重定向 `sys.stdout` 不影响协议写出。

## 我的改造方案
A. 每个工具改成 `async def`，函数体不变（内部仍是同步阻塞代码）。
B. 用一个统一装饰器/包装器：`await anyio.to_thread.run_sync(_call_sync, ..., abandon_on_cancel=True)` 把同步执行体丢到工作线程，再套 `asyncio.wait_for(...)` 或 `anyio.fail_after(timeout)` 实现超时。
C. 全局锁改为 `anyio.Lock()`（异步锁），在工作线程外、事件循环内获取，这样：
   - 抢锁不再阻塞事件循环（等待锁期间事件循环可以处理其他请求/协议心跳）；
   - 超时能在等待锁阶段就生效（拿不到锁直接返回 device_busy），不会无限排队。
D. 超时分两级：锁等待超时（默认 30s，拿不到锁报 device_busy）+ 执行超时（默认 150s，报 timeout）。
E. 工作线程里仍做 `contextlib.redirect_stdout(sys.stderr)`，因为那是线程级/全局状态，在工作线程里设也要小心。

## 请重点回答这几个问题
1. **`redirect_stdout` 在工作线程里安全吗？** `contextlib.redirect_stdout` 改的是全局 `sys.stdout`。多个工作线程并发时会互相覆盖（我依赖全局锁保证同一时刻只有一个工作线程，但锁在事件循环层，工作线程是被 `to_thread` 调度的，会不会有"线程已启动但还没拿到锁"或"锁已释放但线程还没退出 redirect 上下文"的窗口？）。有没有更好的做法（例如给每个工具调用传一个线程局部的 writer、或者干脆在进程启动时把 sys.stdout 永久指到 stderr、用 `os.dup2` 把 fd 1 重定向）？请给出你推荐的具体做法和理由。
2. **`abandon_on_cancel=True` 的正确语义**：超时后主协程放弃等待，但那个工作线程还在跑（无法杀死线程）。因为该线程持有 VISA 会话和全局锁，后续调用会怎样？我的理解是：线程最终会自己结束（VISA 超时迟早生效），但期间任何新调用都会拿不到锁（如果锁是 anyio.Lock 且被该线程持有——但锁是我在事件循环里 acquire 的，工作线程并不持有它，那**线程还在跑、锁却已释放**，是否会导致两个线程同时操作 VISA？这是个隐患，请帮我分析正确顺序）。具体：锁应该在事件循环层 acquire，然后启动工作线程执行，超时后我**不能**立即释放锁（否则并发访问 VISA），但如果不释放，后续调用全卡死。这个矛盾怎么解？
3. **超时值怎么定**：我倾向锁等待 30s / 执行 150s。考虑到 auto_scale 最坏 90s，是否应该改成"按工具分类给不同预算"（只读快查询 30s、慢操作 300s）？还是统一一个大值？请给出你的建议和理由。
4. **是否值得改**：目前全局锁保证互斥，所以"并发处理多个请求"带来的吞吐提升为零（同一时刻只有一个工具能跑）。那么改成异步的真正收益是什么？我列的是：(a) 等待锁期间事件循环不被阻塞，MCP 协议层的心跳/其他消息（如 tools/list）能被处理；(b) 超时语义能在锁等待阶段生效；(c) 不再有"整个服务器停摆 150 秒"。请评估这个收益是否值得改 50 个函数（改动面大、回归成本高），有没有更小成本的替代方案（例如只把工具入口包一层，不改函数签名）。
5. 有没有我没想到的坑？特别是：stdio 传输下单线程事件循环的语义、FastMCP 对 async 工具的并发调度限制（它有没有给工具调用加信号量/串行化？）、anyio 与 asyncio 混用、以及 `to_thread.run_sync` 的默认线程池大小（会不会因为线程池被打满而出现新的排队）。

请直接指出方案里的错误和不必要之处，不要客套。


**A:**
你的总体方向里，A、B、C 组合存在一个关键生命周期错误：执行超时后，异步调用已经返回，但同步 VISA 线程仍可能继续操作设备。此时任何由调用协程持有的 anyio.Lock 都无法安全代表设备占用状态。

我建议把设计中心从“异步锁 + 可遗弃线程”改成 单设备执行器 / actor：设备 I/O 永远由一个专用 worker 串行执行；MCP 工具只是异步提交任务和等待结果。这样可以同时解决线程安全、软超时、遗留线程和队列控制。

另外，你对 mcp==1.27.0 的源码判断是正确的。我核对了 v1.27.0 tag：FastMCP 根据 is_async 分支，async 函数 await fn(...)，同步函数直接 fn(...)，没有给同步 tool 自动套线程。
GitHub
+1
 当前最新版文档已经变成同步 tool 自动进线程池，所以这里尤其要避免拿新版文档推断 1.27.0 行为。
GitHub

先给结论

我会把你的方案改成：

MCP async wrapper
      │
      ├─ admission / busy wait timeout
      │
      ▼
DeviceExecutor
      │
      ├─ 一个设备只允许 1 个 active operation
      │
      ▼
dedicated worker thread
      │
      ▼
同步的原 50 个 tool implementation
      │
      ▼
PyVISA session

其中：

MCP request timeout
    ≠
VISA operation 被终止

150s 到期
    → MCP 返回 timeout
    → executor 继续保持 BUSY
    → VISA worker 继续跑
    → 后续设备操作返回 device_busy
    → worker 真正退出后才恢复 READY

如果你要求“150 秒以后 VISA 调用必须真的消失”，线程模型做不到，需要进程隔离，并让 VISA session 归 worker process 所有。

1. redirect_stdout 放 worker thread 里不安全

你的担心成立。

contextlib.redirect_stdout() 本质上修改：

Python
运行
sys.stdout = new_target

这是进程级全局变量，没有 thread local 语义。

即使你保证 VISA worker 只有一个，它仍然会影响：

MCP event-loop thread

SDK 内部其他线程

其他第三方线程

将来增加的后台任务

因此这种代码：

Python
运行
def worker():
    with redirect_stdout(sys.stderr):
        inst.query(...)

并不能理解成“只重定向这个 worker 的 stdout”。

推荐方案：启动时永久重定向 Python sys.stdout

你已经确认 SDK 启动时取得了原来的：

Python
运行
sys.stdout.buffer

并保存为协议 writer，之后不会动态查 sys.stdout。

那么可以在 MCP stdio transport 完成协议流绑定之后：

Python
运行
sys.stdout = sys.stderr

这样后续 Python：

Python
运行
print(...)

统一进入 stderr。

这比每次调用 redirect_stdout() 干净很多，没有并发窗口。

os.dup2(2, 1) 我反而不建议轻易做

因为它修改 OS fd 1：

Python
运行
os.dup2(2, 1)

如果 MCP transport 保存的是：

Python
运行
sys.stdout.buffer

这个对象底层最终仍然指向 fd 1。

你 dup2() 之后，协议 writer 也可能跟着写 stderr，直接把 stdio MCP 干掉。

所以：

Python
运行
sys.stdout = sys.stderr

和：

Python
运行
os.dup2(2, 1)

语义完全不同。

前者适合你的已验证架
GitHub
AnyIO
+1
GitHub
+1
GitHub
AnyIO
AnyIO

> ⚠️ **本段来自 DOM 兜底（接口读取失败），可能不完整** —— 用 tools\verify-docs.ps1 复核

## Q2 2026-09-15 22:57:34
**Q:** 上一个讨论线程卡在联网搜索里没出结果，我重开一条，问题聚焦一些。**请直接用你的知识回答，不需要联网搜索或引用来源**。

## 背景（都是实测事实）
一个仪器控制 MCP 服务器（Python 3.11 / mcp SDK 1.27.0 / FastMCP，stdio 传输，单进程）：
- 50 个工具全是同步函数；FastMCP 对同步工具直接 `fn(**args)` 跑在事件循环线程上（我读过源码，确认没有自动进线程池）。
- 工具内部共享一把 `threading.Lock` 全局串行化，因为 pyvisa/VISA 运行时不是线程安全的。
- 设备 I/O 阻塞：常规命令几十毫秒，但某个示波器的自动定标最坏约 90 秒。
- 已实测：VISA 的超时设置有时不被遵守（配 2s 实跑 12.97s）。
- 我临时加了个 `threading.Thread(daemon=True)+t.join(budget)` 看门狗。我知道它错：`join` 自己阻塞事件循环，所以"超时后其他请求能快速失败"是假的。

## 之前的讨论给了一个方向（我想确认它，并拿具体结论）
它说我的"异步锁 + abandon_on_cancel"方案有生命周期缺陷：超时后协程返回了，但同步 VISA 线程还在跑，此时锁已经不代表"设备占用"。它建议改成**单设备执行器/actor**：设备 I/O 永远由一个专用 worker 串行执行，MCP 工具只是异步提交任务并等待。MCP 层超时 ≠ VISA 操作终止；超时后 executor 保持 BUSY，后续返回 device_busy，worker 真正退出后才恢复 READY。另外它说 redirect_stdout 在工作线程里不安全（改的是进程级全局），建议在 transport 绑定后直接 `sys.stdout = sys.stderr`；并警告 `os.dup2(2,1)` 会连协议 writer 一起改掉、把 MCP 打死。

## 请直接回答这 5 点，要具体
1. **这个 actor 方向对不对？** 在我的场景（50 个工具、全局串行、stdio 单客户端）下，actor/单 worker 相比"异步锁 + to_thread"是否真的更优？还是过度设计？请明确站边。
2. **锁的正确生命周期**：如果超时后 worker 还在跑，锁应该由谁持有、什么时候释放？在"协程持有锁"和"worker 持有锁"之间，具体该怎么写才不会出现两个线程同时碰 VISA？给出关键代码骨架（不用完整实现）。
3. **超时值**：锁等待 30s + 执行 150s 合理吗？还是该按工具分类（只读快查询 vs 慢操作）？auto_scale 最坏 90s 这个事实怎么影响取值？
4. **收益是否值得**：全局锁下并发吞吐提升为 0（同一时刻只有一个工具能跑）。那改成异步的真实收益只是"锁等待期间事件循环不被阻塞"和"超时语义能在等锁阶段生效"吗？有没有更小成本的替代（例如只包一层入口、不动 50 个函数签名）？
5. **stdio 单客户端下 EventLoop 阻塞的真实后果**：客户端在等一个 150s 的调用时，MCP 协议层还需要处理什么吗（心跳？cancel？并发请求？）？如果我的客户端总是串行调用（等上一个返回再发下一个），那"阻塞事件循环"是否其实无害？

第 4、5 点特别重要——如果收益很小，我想避免为了"正确"而做一次高风险的 50 函数改造。请直接说，不要客套。


**A:**
结论：**不要做“50 个函数全面 async 化”**。你的设备天然是严格串行资源，推荐把“异步化”集中在调用边界。实现上采用一个**每设备单 worker executor，加 BUSY 状态**即可，没必要做复杂消息队列 actor。

### 1. actor 方向对不对

方向对，但需要区分两个方案：

```text
A. async lock → to_thread(sync VISA)
B. 单 worker / actor → sync VISA
```

我明确选择 **B**。

A 的典型错误生命周期是：

```python
async with async_lock:
    await wait_for(
        to_thread.run_sync(sync_func, abandon_on_cancel=True),
        150
    )
```

150 秒超时后：

```text
MCP coroutine     已经退出
async_lock        已经释放
VISA worker       可能仍在执行
```

下一个请求可以拿到 `async_lock`，然后第二个线程进入 VISA。这样就破坏了你的核心约束。

不过，你其实还有一个安全的低成本方案：

```python
await to_thread(sync_func)
```

并且让现有 `sync_func` 内部继续持有 `_DEVICE_LOCK`。

这样即使 coroutine 超时，**worker 中的 `_DEVICE_LOCK` 仍然不会释放**，所以不会发生两个线程同时访问 VISA。

因此从“能不能正确运行”看，actor 并非唯一方案。

我仍推荐单 worker，原因是它进一步提供了：

```text
1. VISA 永远只存在一个执行线程
2. 不会出现多个线程堵在 threading.Lock 上
3. MCP timeout 后可以明确保持 BUSY
4. 后续请求可以立即 device_busy
5. VISA session 实际上获得 thread confinement
6. 状态机更容易推理
```

对于你的场景，actor 可以做得非常薄。**ThreadPoolExecutor(max_workers=1) + BUSY 状态，本质上就够了。**

不建议搞完整 mailbox、command object、复杂队列。

---

## 2. 锁到底应该由谁持有

原则非常明确：

> **代表设备占用的生命周期必须绑定实际执行 VISA I/O 的 worker，不能绑定等待结果的 coroutine。**

也就是说：

```text
worker 开始操作设备
    ↓
设备 BUSY / worker 持锁
    ↓
MCP 等待
    ↓
MCP 可以超时返回
    ↓
设备仍 BUSY / 锁仍存在
    ↓
VISA 操作真正结束
    ↓
worker 释放锁
    ↓
设备 READY
```

### 你现在最容易落地的版本

你的 50 个同步函数已经自己做：

```python
def scope_xxx(...):
    with _DEVICE_LOCK:
        # VISA I/O
        ...
```

那就**继续让它们这么做**。

不要再这样包：

```python
def worker():
    with _DEVICE_LOCK:
        return original_func(...)
```

如果 `original_func()` 自己又 `with _DEVICE_LOCK`，普通 `threading.Lock` 会自锁死。

可以直接：

```python
_executor = ThreadPoolExecutor(max_workers=1)

async def call_device(fn, *args, exec_timeout=150, **kwargs):
    loop = asyncio.get_running_loop()

    fut = loop.run_in_executor(
        _executor,
        functools.partial(fn, *args, **kwargs),
    )

    try:
        return await asyncio.wait_for(
            asyncio.shield(fut),
            timeout=exec_timeout,
        )
    except asyncio.TimeoutError:
        raise DeviceTimeout(...)
```

这里 `shield()` 很重要。MCP 等待超时时，不要试图把底层 future 当成已经终止。

但这个版本还有一个问题：

```text
call A
A 超时，但线程继续运行

call B
ThreadPoolExecutor(max_workers=1)
把 B 排到队列里

A 最后结束
B 自动开始
```

如果你要的是：

> A 超时后，后续请求立即得到 `device_busy`

那么再加一个 admission 状态。

例如：

```python
class DeviceExecutor:
    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1)
        self._state_lock = asyncio.Lock()
        self._busy = False
        self._running = None

    async def call(self, fn, *args, timeout, **kwargs):
        async with self._state_lock:
            if self._busy:
                raise DeviceBusy()

            self._busy = True

            loop = asyncio.get_running_loop()
            fut = loop.run_in_executor(
                self._pool,
                functools.partial(fn, *args, **kwargs),
            )
            self._running = fut

            fut.add_done_callback(
                lambda _: loop.call_soon_threadsafe(
                    self._worker_finished
                )
            )

        try:
            return await asyncio.wait_for(
                asyncio.shield(fut),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # 注意这里绝对不能 self._busy = False
            raise DeviceTimeout(
                "MCP request timed out; device operation still running"
            )

    def _worker_finished(self):
        self._running = None
        self._busy = False
```

实际实现里 callback 可以再整理一下，核心只有一句：

> **`busy=False` 只能发生在 underlying worker future 真正完成的时候。**

不能放在：

```python
finally:
    self._busy = False
```

否则重现同一个生命周期 bug。

### 更进一步

如果能够保证：

```text
所有 VISA 操作
100% 都只能经过这个单 worker
```

理论上 `_DEVICE_LOCK` 都可以删除，因为 thread confinement 已经提供严格串行。

考虑你现在已有 50 个函数，我建议**暂时保留现有 `_DEVICE_LOCK`**。它作为第二道保险，不值得为了架构纯洁去改 50 个函数。

---

# 3. 30 秒等锁 + 150 秒执行是否合理

在推荐的 actor 模型里，我反而建议取消“等锁 30 秒”这个概念。

状态只有：

```text
READY
BUSY
```

新请求到来：

```python
if BUSY:
    return device_busy
```

通常立即返回。

因为你已经知道设备最长存在约 90 秒操作。假设 auto_scale 正在执行：

```text
t = 0 s    auto_scale 开始
t = 1 s    query 请求到达
t = 31 s   query 因 lock timeout 返回
```

这个 query 白等 30 秒，没有得到任何额外价值。

所以我建议：

```text
admission / busy timeout:    0 秒或极短
execution timeout:           按工具类别设置
```

### 不建议所有工具统一 150 秒

你的操作延迟跨度已经很明显：

```text
普通查询       数十 ms
普通配置       数十 ms ～ 秒级
较慢采集       可能数秒
AUTO_SCALE     已测最坏约 90 s
```

统一 150 秒的问题在于一个本来应该 100 ms 返回的 `*IDN?` 卡死后，服务器会等 150 秒才报告 timeout。

推荐至少分三级：

| 类型 | 软件 deadline 建议 |
|---|---:|
| 快查询、普通寄存器/SCPI query | 5～10 s |
| 一般操作、采集配置 | 20～30 s |
| 已知慢操作，如 auto_scale | 120～150 s |

你实测：

```text
VISA timeout = 2 s
实际 = 12.97 s
```

这说明应用层 deadline 有价值。

但要明确它是什么：

> **150 秒是“调用者停止等待”的 deadline，不是 VISA 操作的 hard kill deadline。**

超过 150 秒：

```text
MCP 返回 timeout
worker 继续
device BUSY
```

如果底层 VISA 真正永久卡死，那么它可能：

```text
BUSY forever
```

Python thread 没有安全的强杀机制。

如果你未来要求：

> 无论 VISA/驱动怎么挂，150 秒后设备一定恢复可用

那就必须升级到：

```text
MCP process
    ↓ IPC
VISA worker subprocess
```

150 秒后杀 worker process，重建 VISA session。

单线程方案无法提供这种 hard timeout。

---

# 4. 异步改造到底能获得什么

你的判断基本正确：

> **设备吞吐量提升为 0。**

串行 VISA：

```text
request A ──────────────┐
                       VISA
request B ──────────────┘
```

无论 asyncio、thread pool、actor，物理吞吐都不会增加。

异步化真正获得四件事。

### 第一，事件循环不再被冻结

现在：

```python
asyncio event loop
    ↓
sync tool()
    ↓
90 s blocking VISA
```

整个 asyncio runtime 停 90 秒。

改后：

```text
event loop               worker
   │                        │
   ├─ await ───────────────>│ VISA
   │
   ├─ 继续处理协议
   ├─ cancellation
   ├─ other request
   └─ shutdown
```

### 第二，等待设备的请求不会卡事件循环

如果采用 worker-side lock：

```python
def fn():
    if not _DEVICE_LOCK.acquire(timeout=30):
        ...
```

这个 30 秒发生在线程里，对 event loop 没影响。

### 第三，MCP deadline/cancel 才真正有意义

现在 event loop 卡在：

```python
fn(**args)
```

那么 asyncio 层的：

```python
wait_for()
cancel()
```

根本没有执行机会。

### 第四，超时之后可以表达真实设备状态

这是 actor 最大的架构收益：

```text
request timeout != operation terminated
```

这两个状态终于被正确分开。

---

## 但你的情况完全没必要改 50 个函数

这是我认为最重要的结论。

目标架构应该是：

```text
                FastMCP
                   │
           一个统一 async 边界
                   │
           DeviceExecutor.call()
                   │
             single worker
                   │
       原来的 50 个 sync functions
                   │
          原来的 _DEVICE_LOCK
                   │
                 VISA
```

也就是说：

> **改调度层，不改业务工具实现。**

如果你的 FastMCP 注册方式允许统一包装 handler，最好只改一个地方。

即使不能统一 hook，最多把注册形式从：

```python
mcp.tool()(foo)
```

变成类似：

```python
mcp.tool()(async_wrap(foo))
```

`foo()` 本身完全不用改。

甚至可以写注册 decorator：

```python
def device_tool(*tool_args, **tool_kwargs):
    def decorate(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await DEVICE.call(
                fn,
                *args,
                timeout=get_timeout(fn),
                **kwargs,
            )

        mcp.tool(*tool_args, **tool_kwargs)(wrapper)
        return fn

    return decorate
```

这样你的 50 个业务函数仍然是：

```python
def measure_voltage(...):
    with _DEVICE_LOCK:
        ...
```

不用重写成：

```python
async def ...
```

这比“大规模 async 化”风险低很多。

### 如果你想把修改量进一步压到最低

甚至可以先不用 BUSY actor，只做：

```python
async def wrapper(...):
    return await anyio.to_thread.run_sync(
        functools.partial(sync_fn, ...),
        abandon_on_cancel=True,
    )
```

并且**保留同步函数内部 `_DEVICE_LOCK`**。

这样至少有两个重要性质：

```text
event loop 不阻塞
超时后 threading.Lock 不会提前释放
```

这是一个完全合理的第一阶段。

它的缺陷只是多个并发请求可能产生多个线程等 `_DEVICE_LOCK`，以及 timeout 后下一请求不能立即判断 BUSY。

所以我的实施优先级会是：

```text
最小方案：
统一入口 → to_thread → 原函数内部 threading.Lock

更完善方案：
统一入口 → BUSY gate → single-worker executor → 原同步函数

不推荐：
50 个工具逐个 async 重写 + coroutine async lock
```

---

# 5. stdio 单客户端，如果客户端严格串行，EventLoop 卡住到底有多严重

这里可以说得很明确：

> **如果客户端真正严格串行，并且一个调用期间什么协议消息都不会发送，那么 event loop 阻塞 150 秒的实际危害确实很小。**

MCP stdio 并不要求服务器在一个长调用期间持续发送某种固定 heartbeat 才能保持连接。

假设实际行为始终是：

```text
client:
send request A
wait A response
    150 s 什么都不做
receive A response
send request B
```

同时：

```text
没有并发请求
没有 cancellation
没有 ping
没有需要处理的 notification
没有后台任务
不要求 shutdown 立即响应
```

那么：

```python
sync_fn()  # 阻塞 event loop 150 s
```

从这个特定工作模型看，**功能上基本可以正常工作**。

这点不值得夸大。

event loop 在这 150 秒内本来也没有必须做的事情。

### 真正损失的是这些能力

如果客户端发送：

```text
cancel A
```

服务器看不到，直到 A 返回。

如果客户端发送：

```text
request B
```

B 已经进入 stdin pipe，也只能等 A 返回以后解析。

如果客户端发 protocol ping，情况一样。

如果你希望：

```text
Ctrl+C / shutdown
connection cleanup
async timer
后台状态任务
其他 MCP operation
```

及时执行，也都会延迟。

而且最实际的一点是：

```text
客户端自己的 request timeout = 30 s

server 卡 VISA = 90 s
```

30 秒时客户端可能已经认为请求失败甚至关闭 stdio，而服务器还在事件循环线程中卡着。

因此从工程健壮性看，把 I/O 移出 event loop 仍然是正确的。

但如果你的真实系统确实满足：

```text
1 个客户端
严格 request-response 串行
不会 cancel
不会并发
长命令 90 s 客户端也愿意等
```

那么**你没有迫切理由为了“async 正统性”去改 50 个函数。**

---

## 我的最终建议

按风险收益比，我会这么做：

```text
保留：
50 个同步工具实现
现有 threading.Lock
现有 VISA 代码

修改：
FastMCP 和工具函数之间增加一个统一调用层

调用层：
1. 使用单 worker executor
2. event loop 只 await worker
3. BUSY 在 worker 真正完成时清除
4. MCP timeout 不取消底层 VISA
5. timeout 后继续报告 BUSY
6. fast / normal / slow 三档 timeout
```

其中 **30 秒 lock wait 我会删掉**。既然目标语义是 BUSY，就立即返回 BUSY。

auto_scale：

```text
软件 timeout = 120～150 s
```

普通命令：

```text
5～30 s，按类别
```

还有一个关键判断：

> 如果你暂时连 single-worker executor 都不想加，只把现有同步函数统一丢到 `to_thread`，同时继续让 `_DEVICE_LOCK` 在同步函数内部持有，这已经修掉了最危险的“协程 timeout 导致锁提前释放”问题。

所以你当前没有理由做一次高风险的“50 个函数 async 重构”。**值得改的是统一调度入口，改动规模应该很小。** memcite

## Q3 2026-09-15 23:02:53
**Q:** 收到，我接受"不改 50 个函数、只改调度层"的主结论。但我有 3 个具体点不同意或需要你确认，请逐一回应（仍然不需要联网搜索）。

## 我的反驳/疑问

### ① 你的 `sys.stdout = sys.stderr` 建议有顺序陷阱，我认为不能按你说的时机做
你说"在 transport 绑定之后 `sys.stdout = sys.stderr`"。但我的服务器代码里 `mcp.run()` 是最后一行，我没有"transport 绑定点"的钩子。我核对了 mcp 1.27.0 的 `mcp/server/stdio.py`：
```python
stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))
```
它是**在 mcp.run() 内部、stdio 上下文建立时**才读 `sys.stdout.buffer`。
所以如果我在 `mcp.run()` **之前**写 `sys.stdout = sys.stderr`，那么 `sys.stdout.buffer` 就变成了 stderr 的 buffer → **协议流会被写到 stderr** → 客户端直接收不到任何东西、服务器等于死了。
我的结论：这条只能在 transport 绑定**之后**执行。而最晚可证的时机是"第一次工具调用发生时"（那时 transport 必然已绑定）。所以我打算用**一次性懒执行**：在统一包装层里 `if not _fixed: sys.stdout = sys.stderr; _fixed = True`。
请确认：这个顺序分析对不对？懒执行是否是有意为之的正确做法？有没有更干净的钩子（不引私有 API 的前提下）？

### ② 我不同意"三档 timeout"，理由是"误报超时"比"多等"更糟
你说 fast query 用 5~10s、normal 20~30s、slow 120~150s。但在我的架构里 **MCP timeout ≠ 操作终止**（这一点你我都同意）。那么一个过短的 deadline 会产生：
- 工具其实**成功了**（比如某台设备第一次连接要 15s，或某条命令耗时 12s），但我在 10s 报了 timeout；
- 调用方以为失败 → 重试 → 拿到 device_busy → 更困惑。
而且我的 50 个工具里，慢/快我没有系统性实测数据（只有 auto_scale 实测最坏 ~90s），按名字猜档位本身就是新的错误来源。
所以我倾向：**统一一个宽裕的 deadline（150s）当"驱动彻底挂死"的安全网**，只对有实测证据的极慢工具（auto_scale）单独放宽到 300s；不做 5~10s 那一档。
请反驳或同意。如果你坚持要档位，请说明：**在"MCP timeout 不等于操作终止"的前提下，短 deadline 带来的"更早知道"到底有什么可操作价值？**（调用方除了重启 MCP 或 usb_reset 之外还能做什么？）

### ③ 我的实现骨架，请挑错
```python
class _DeviceExecutor:
    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="visa")
        self._busy = False            # 只在 event loop 线程读写（下面解释为什么不用锁）

    async def run(self, fn, budget_s):
        # 这里没有 await，所以"检查+置位"对其它协程是原子的
        if self._busy:
            return BUSY_ERROR                  # 立即返回，不等待
        self._busy = True

        def work():
            try:
                return fn()                    # fn 内部仍然是 with _DEVICE_LOCK: ...
            finally:
                self._busy = False             # 在 worker 真正结束时清除

        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(self._pool, work)
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=budget_s)
        except asyncio.TimeoutError:
            return TIMEOUT_ERROR               # 注意：不清 _busy，worker 还在跑

def device_tool(budget_s=None):
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*a, **kw):
            return await EXECUTOR.run(functools.partial(fn, *a, **kw), budget_s or DEFAULT)
        mcp.tool()(wrapper)                    # 注册 async 包装，原函数体不动
        return fn
    return deco
```
具体问题：
- ③-1 `finally: self._busy = False` 是在 worker 线程里写的，而 `if self._busy` 是在 event loop 线程里读的——**跨线程无同步**。CPython 下 bool 赋值/读取是原子的、GIL 保证可见性，所以我认为够了（而且它只是"准入闸门"，不是数据保护）。你同意吗？还是必须用 `threading.Event`？
- ③-2 `finally` 在 `fn()` 返回后立即清 BUSY，但 executor 的 future 还没标记 done。这个窗口里如果有新请求进来，会 `run_in_executor` 到同一个单线程池（此时该池已空闲），于是新任务开始跑——而旧 future 的 await 还没恢复。**这会导致 VISA 并发访问吗？** 我的判断是：不会，因为 `fn()` 已经返回、VISA I/O 已结束；future 的 done 标记只是簿记。请确认。
- ③-3 用 `functools.wraps` 让 FastMCP 仍能从我原来的函数签名生成 JSON Schema（我的工具参数是靠类型注解生成的）。`inspect.signature` 会跟随 `__wrapped__`，所以参数表不变。**但 FastMCP 也可能用 `get_type_hints()` 或 `__annotations__`**——请确认 `functools.wraps` 是否足以让 50 个工具的入参 schema 保持不变；如果有风险，替代做法是什么（例如显式 `wrapper.__signature__ = inspect.signature(fn)`）？
- ③-4 我把 `_DEVICE_LOCK` 保留了（你说的第二道保险）。但这样一来，"等待锁"永远不会发生（单 worker 内只有它自己），所以我要把 `acquire(timeout=30)` 改回普通 `with _DEVICE_LOCK:`，并把 `device_busy` 的唯一来源改成你建议的准入闸门。这样对吗？

请直接回答，同意/不同意都给出理由。仍然不要联网搜索。


**A:**
你的三点里，我的结论是：

1. ① 顺序分析正确。第一次工具调用时懒重定向是安全方案。若能确认 public lifespan 的执行时序，它更干净。
2. ② 我同意统一宽裕 deadline。现阶段做三档 timeout 缺乏实测依据，短 deadline 的收益不足以抵消假超时。
3. ③ 架构成立，但我建议把 `_busy=False` 移回 event loop，通过 `Future.add_done_callback()` 完成。这样线程模型更干净。

## ① `sys.stdout` 的顺序

你的分析正确。

已知 SDK 做的是：

```python
stdout = anyio.wrap_file(
    TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
)
```

那么执行顺序决定一切。

如果：

```python
sys.stdout = sys.stderr
mcp.run()
```

则 `stdio_server()` 进入时取得：

```python
sys.stdout.buffer == sys.stderr.buffer
```

MCP 协议输出就走 stderr，stdout 管道收不到协议数据。

而第一次工具调用意味着此前已经完成：

```text
stdio transport 创建
→ stdout buffer 被捕获
→ MCP session 已建立
→ 收到并解析 tools/call
→ 调 wrapper
```

此时执行：

```python
sys.stdout = sys.stderr
```

只改变之后通过 Python `sys.stdout` 查找的输出目标。已经创建的 MCP writer 仍握着原来的 stdout buffer。

所以你的：

```python
if not _fixed:
    sys.stdout = sys.stderr
    _fixed = True
```

放统一工具 wrapper 入口，**逻辑成立，而且时序是刻意设计出来的**。

因为检查和赋值之间没有 `await`，单 event loop 下 `_fixed` 也无需锁。

### 更干净的 public hook

如果你当前 FastMCP 版本使用公开的 `lifespan` hook，并且你已经从源码确认顺序是：

```text
进入 stdio_server()
→ 捕获原 stdout
→ 进入 server lifespan
```

那么我更倾向在 lifespan startup 中做：

```python
@asynccontextmanager
async def lifespan(server):
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout
```

它比“第一次工具调用”更早，可以覆盖 transport 建立之后、第一次工具调用之前产生的 Python stdout 输出。

但这个方案的安全性取决于 **lifespan 确实晚于 `stdio_server()` 捕获 stdout**。如果不想再依赖一个 SDK 内部执行顺序，你的 lazy wrapper 更容易证明正确。

还有一个边界需要保留：

```python
sys.stdout = sys.stderr
```

只能管 Python 层通过 `sys.stdout` 的输出。

这些仍然可能污染 fd 1：

```python
os.write(1, ...)
C printf(...)
某些 native library 的 stdout
已经保存旧 sys.stdout 对象的代码
```

而：

```python
os.dup2(2, 1)
```

确实不能用，因为 MCP writer 最终仍指向 fd 1 对应的协议通道，`dup2` 会把底层 fd 本身换掉。

所以①我同意你的方案。

---

# ② timeout：我改为同意你的统一宽裕策略

你指出的问题成立，而且这里有一个很重要的语义：

```text
MCP deadline 到期
≠
VISA operation 被终止
≠
设备恢复 READY
```

因此 5 秒、10 秒这种激进 deadline，在你的架构里价值确实有限。

例如：

```text
t=0     query 启动
t=10    MCP 返回 TIMEOUT
t=12    VISA 实际成功完成
```

结果会变成：

```text
客户端看到失败
设备实际执行成功
客户端可能重试
重试期间又看到 BUSY
```

对于有副作用的命令更麻烦，例如：

```text
AUTO
RUN
SAVE
配置写入
校准
```

调用方甚至无法根据 timeout 判断该操作有没有发生。

### 目前我建议

```python
DEFAULT_BUDGET = 150.0
AUTO_SCALE_BUDGET = 300.0
```

或者你根据实际情况给少量明确验证过的特殊操作 override。

不要根据函数名主观分 fast / normal / slow。

以后积累真实 latency telemetry，例如：

```text
tool
device model
p50
p95
p99
max
timeout count
```

再讨论收紧 deadline。

### 短 deadline 到底有什么实际价值

在这个线程模型下，主要只剩两个：

第一，限制调用方等待时间。

第二，让调用方更早决定是否采取**真正能够中断执行环境的恢复手段**。

例如：

```text
杀掉 MCP 进程
杀掉独立 VISA worker process
外部 USB reset / power cycle
```

如果调用方收到 timeout 后只会：

```text
再调用一个 MCP tool
```

那么短 timeout 几乎没有恢复价值，因为唯一的 VISA worker 仍然 BUSY。

甚至 `usb_reset` 如果本身也需要通过这个 worker/VISA session 执行，它在 worker 卡死时一样进不去。

所以我建议把这个参数在概念上叫：

```python
wait_budget_s
```

或者：

```python
response_deadline_s
```

比“VISA timeout”准确。

还可以增加一个**只记录日志、不向客户端返回错误**的 soft threshold：

```text
5 s     slow operation warning
30 s    very slow warning
150 s   caller wait deadline
```

这样能观察异常延迟，同时避免假 timeout。

因此②：**你的方案更适合当前阶段。**

---

# ③ 实现骨架

总体结构正确。我会做一个关键调整。

## ③-1 `_busy` 跨线程读写

你现在：

```python
event loop:
    if self._busy:
        ...
    self._busy = True

worker:
    self._busy = False
```

对于你明确限定的 **CPython 3.11**，单个 Python object reference 的 load/store 在 GIL 下实际不会出现 torn read/write，因此从实际运行结果看，这个 bool 大概率没问题。

但我仍然不建议这么写。

原因很简单：你已经定义了：

> `_busy` 只属于 event loop 状态。

那就贯彻到底。

`run_in_executor()` 返回的是 asyncio Future，可以直接：

```python
fut.add_done_callback(self._on_done)
```

asyncio Future 的 done callback 在其 event loop 中调度执行。

于是：

```python
def _on_done(self, fut):
    self._busy = False
```

仍运行在 event loop 线程。

这样完全消除了跨线程共享 `_busy`。

无需 `threading.Event`。

我推荐：

```python
class _DeviceExecutor:
    def __init__(self):
        self._pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="visa",
        )
        self._busy = False
        self._running = None

    def _on_done(self, fut):
        self._running = None
        self._busy = False

    async def run(self, fn, budget_s):
        # 到第一个 await 之前，同一个 event loop 内不会切换到另一协程
        if self._busy:
            return BUSY_ERROR

        self._busy = True
        loop = asyncio.get_running_loop()

        try:
            fut = loop.run_in_executor(self._pool, fn)
        except BaseException:
            self._busy = False
            raise

        self._running = fut
        fut.add_done_callback(self._on_done)

        try:
            return await asyncio.wait_for(
                asyncio.shield(fut),
                timeout=budget_s,
            )
        except TimeoutError:
            return TIMEOUT_ERROR
```

这个版本具有非常清晰的生命周期：

```text
run() admission:
    busy = True

worker:
    fn()

MCP wait:
    可以成功
    可以 timeout
    可以被 cancel

worker 真正完成:
    Future done

event loop:
    _on_done()
    busy = False
```

即使 MCP coroutine 在 150 秒已经返回 TIMEOUT：

```python
fut.add_done_callback(...)
```

仍然存在。

worker 在 180 秒结束时，callback 才会清 BUSY。

这正是你要的语义。

另外：

```python
budget_s or DEFAULT
```

我建议改成：

```python
DEFAULT if budget_s is None else budget_s
```

避免以后合法的 `0` 或其他 falsy 值被静默替换。

---

## ③-2 旧方案提前清 BUSY会不会造成 VISA 并发

你的判断正确：**不会造成 VISA 并发。**

旧代码：

```python
def work():
    try:
        return fn()
    finally:
        self._busy = False
```

其时间线可能是：

```text
worker:
fn() VISA I/O
fn() 返回
_busy = False
             ← event loop 此时接受新请求
             ← 新任务进入 executor queue
work() 返回
executor 完成旧 Future
worker 取下一个任务
新 fn() 开始
```

由于：

```python
ThreadPoolExecutor(max_workers=1)
```

同一 worker 在 `work()` 完全返回之前不可能开始第二个 work item。

所以不会出现：

```text
VISA A
VISA B
```

同时运行。

旧 Future 的 await 有没有恢复，与设备资源释放没有关系。

不过旧方案存在一个小语义窗口：

```text
_busy == False
旧 Future 尚未 done
```

这意味着新请求可以提前进入 executor queue。

安全性没问题，但已经偏离你定义的：

> BUSY 一直保持到 underlying operation 真正完成并被 executor 确认完成。

用 `add_done_callback()` 后这个窗口也消失了，所以更整洁。

---

## ③-3 `functools.wraps` 与 FastMCP schema

这里需要分两层。

在 Python 3.11 中，`functools.wraps(fn)` 会处理至少这些关键属性：

```python
__name__
__qualname__
__doc__
__module__
__annotations__
__wrapped__
```

因此普通情况：

```python
inspect.signature(wrapper)
```

默认会沿：

```python
wrapper.__wrapped__ -> fn
```

拿到原函数签名。

而且：

```python
wrapper.__annotations__
```

也会复制原函数的 annotations。

所以如果你的参数类型都是：

```python
str
int
float
bool
Optional[str]
Literal[...]
```

之类已经解析好的类型，单靠 `wraps` 通常足够。

### 真正值得注意的是 `get_type_hints()`

假设原函数位于：

```python
instrument_scope.py
```

并使用 postponed/string annotation：

```python
def foo(x: "MyEnum") -> "Result":
    ...
```

wrapper 却定义在：

```python
device_executor.py
```

`wraps` 会复制：

```python
{"x": "MyEnum", "return": "Result"}
```

但不会把原函数的：

```python
fn.__globals__
```

变成 wrapper 的 globals。

某些调用：

```python
typing.get_type_hints(wrapper)
```

可能拿 wrapper 所在模块的 namespace 去解析 `"MyEnum"`，从而失败。

所以：

> `wraps` 对 `inspect.signature()` 很可靠；对于跨模块 string / forward annotations，单独依赖它存在风险。

### 最稳的办法

在注册 FastMCP tool **之前**把 hints 用原函数上下文解析一次：

```python
sig = inspect.signature(fn)
hints = typing.get_type_hints(fn, include_extras=True)

params = [
    p.replace(annotation=hints.get(name, p.annotation))
    for name, p in sig.parameters.items()
]

wrapper.__signature__ = sig.replace(
    parameters=params,
    return_annotation=hints.get(
        "return",
        sig.return_annotation,
    ),
)

wrapper.__annotations__ = dict(hints)
```

然后：

```python
mcp.tool()(wrapper)
```

顺序必须是：

```text
wraps
→ 修正 signature / annotations
→ mcp.tool() 注册
```

这样无论 FastMCP 最终主要使用：

```python
inspect.signature()
```

还是：

```python
__annotations__
get_type_hints()
```

你给它看到的都是已经解析后的类型。

如果你的 50 个函数全部在同一个 module，且没有 string forward refs，这一步可能属于过度防御。最简单的验证方法其实是改完以后做一个自动测试：

```python
修改前 tools/list schema
修改后 tools/list schema
逐 tool JSON diff
```

要求 50 个 inputSchema 完全一致。

我会把这个测试当作重构验收条件，比猜 SDK 到底走哪条 introspection 路径可靠。

---

## ③-4 `_DEVICE_LOCK`

架构上你说得对。

当所有设备调用都变成：

```text
MCP
→ admission gate
→ ThreadPoolExecutor(max_workers=1)
→ sync fn
→ VISA
```

worker 内的 `_DEVICE_LOCK` 正常情况下永远没有竞争者。

所以：

```python
with _DEVICE_LOCK:
    ...
```

已经足够。

`device_busy` 应由 admission gate 给出：

```python
if self._busy:
    return BUSY_ERROR
```

内层 lock 的职责只剩防御：

```text
防止未来某处绕过 DeviceExecutor 直接碰 VISA
```

不过我不建议为了这个目的再去修改 50 个函数。

如果当前 50 个函数已经写着：

```python
if not _DEVICE_LOCK.acquire(timeout=30):
    ...
try:
    ...
finally:
    _DEVICE_LOCK.release()
```

**可以暂时原样保留。**

在正常 actor 路径里：

```text
30s timeout 实际等待时间 ≈ 0
```

没有运行成本。

如果它某天真的等了 30 秒，反而证明：

```text
有代码绕过 executor
或
有异常路径长期占用了 DEVICE_LOCK
```

这是有价值的异常信号。

因此我会分两阶段：

```text
本次低风险重构：
不动 50 个 sync 函数
保留现有 DEVICE_LOCK
增加统一 executor

以后代码清理：
确认所有 VISA path 都经过 executor 后
再考虑把 acquire(timeout=30) 简化
```

这样最符合你这次“避免高风险 50 函数改造”的目标。

### 最终我建议的 decorator

```python
def device_tool(budget_s=None):
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*a, **kw):
            if not _stdout_fixed:
                _fix_stdout_once()

            budget = (
                DEFAULT_BUDGET
                if budget_s is None
                else budget_s
            )

            return await EXECUTOR.run(
                functools.partial(fn, *a, **kw),
                budget,
            )

        # 可选：这里解析并固定 signature / annotations
        _preserve_tool_signature(wrapper, fn)

        mcp.tool()(wrapper)

        # 原业务代码里的符号仍指向同步函数
        return fn

    return deco
```

这里 `return fn` 我认为也是合理设计：Python 代码直接调用 `foo()` 时仍得到原同步实现，只有 MCP registry 持有 async wrapper。这样对现有代码侵入最小。

最终判断：你的设计已经足够接近我会实际提交的版本。**我会改的核心只有 `_busy` 清理由 worker 写改成 Future done callback 在 event loop 写；timeout 策略采用你提出的宽裕统一值；stdout 优先考虑 public lifespan，无法证明其时序时就用第一次 tool call 的一次性懒重定向。**


---

## 复核更正（2026-09-16，本仓真机/离线实验）

本节由后续复核追加，只记录**被实验推翻或补强**的结论，不改上文原话（保留评审过程）。

### ① `ThreadPoolExecutor(max_workers=1)` 的 atexit 会让"重启 MCP"这条恢复路径失效

上文多处（本文 `ThreadPoolExecutor(max_workers=1) + BUSY 状态，本质上就够了`、
以及第 912 行"调用方除了重启 MCP 或 usb_reset 之外还能做什么"）把 **重启 MCP** 当作
卡死后的最终恢复手段。实测发现这与 TPE 的性质冲突：

- `concurrent.futures.ThreadPoolExecutor` 的 worker 是**非 daemon** 线程，且
  `concurrent.futures.thread` 注册了 `atexit` 钩子会 **join** 它们；
- 本设计要顶住的正是"驱动挂起、worker 卡在 native 调用里"——那种情形下进程
  **退不出来**：离线实验（提交一个 `sleep(600)` 任务后让解释器退出）实测
  **12s 内不退出**（`taskkill /F` 才能收场）；同场景换成 daemon 线程**2s 秒退**。

**处置**：执行器改为 **daemon worker 线程 + `queue.Queue`**（语义逐条保留：单线程封闭、
BUSY 闸门立即 `device_busy`、超时只放弃等待不取消 worker、结果/异常原样回填、
`_busy` 仍只在事件循环线程写）。回归：`TEST_SCRIPTS/common/verify_executor_exit.py`
（11 项：含"挂起任务在跑时子进程仍能退出"、BUSY 闸门不下发、超时后仍 BUSY、
worker 结束后自动空闲、异常路径清 BUSY、预算解析），另加端到端 `mho_status` 真机调用。

### ② `scan_cidr` 的识别阶段漏用了共享 ResourceManager（库路径与 MCP 路径不一致）

`identify_lan` 的文档写明"多线程各自 `ResourceManager()` 并发 open 会随机抛
`VI_ERROR_INV_OBJECT`，且该异常会从 `rm.close()` 里抛出、冲垮整轮扫描"，
`instr_discover` 已改成共享单例——但**库路径的 `scan_cidr` 仍是每台候选自建 RM**
（`pool.submit(identify_lan, a, timeout_ms)`），`find_device`/`resolve` 回退会踩到。
**处置**：`scan_cidr` 改走 `identify_lan_all`（共享 RM），并把预筛到的**开放端口**
传下去，识别只试对应协议。

### ③ 扫描范围：`local_cidrs` 的 /24 假设与"宽网段直接扫"的代价

- 原实现按 `/24` 硬编码（真实网卡是 `/16`）→ 同广播域但不在该 /24 的仪器被静默漏掉
  （详见 `TEST_SCRIPTS/common/verify_discovery_local.py` 头部）；
- 改成真实掩码后，直接扫 `/16` 要 ~166s/4 端口，而仪器通常在**同 /24** 里。
  **处置**：`local_scan_segments()` 给出**由窄到宽**的顺序（近邻 /24 → 真实网段），
  实测本机 `find_device` 从"扫不全/166s"变为 **8.3s 命中**。
