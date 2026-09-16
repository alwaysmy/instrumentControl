"""设备执行器（`mcp_instruments.server._DeviceExecutor`）的**设计回归**：离线、不碰仪器。

来源：2026-09-16 对远端引入的"单 worker 异步执行器"做设计复核时发现的问题——
它用 `concurrent.futures.ThreadPoolExecutor`，而 TPE 的 worker 是**非 daemon** 线程且
`concurrent.futures.thread` 注册了 `atexit` 钩子会 **join** 它们。这套设计要顶住的
恰恰是"驱动挂起、worker 卡在 native 调用里"——那种情形下整个进程**退不出来**
（实测：提交 sleep(600) 后进程 12s 内不退出），"重启 MCP 服务可恢复"的恢复路径失效。
修法是 daemon worker + queue（语义不变），本文件把这几条语义都钉住：

    python TEST_SCRIPTS/common/verify_executor_exit.py

断言：
    §1 **挂起任务不阻塞进程退出**（子进程实测；旧 TPE 版会挂住）
    §2 BUSY 闸门：并发第二个调用立即 device_busy，且**不下发**（fn 没被执行）
    §3 预算超时 → 返回 timeout 且**保持 BUSY**（worker 还在跑）；worker 跑完后自动空闲
    §4 结果与异常原样回填（含自定义异常类型）
    §5 预算解析：默认 / 数值 / 可调用 / 预热未完成时 +90s
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:60s} {str(detail)[:100]}", flush=True)
    if not ok:
        fails.append(name)


print("§1 挂起任务不阻塞进程退出（daemon worker）", flush=True)
CHILD = r'''
import asyncio, sys, time
sys.path.insert(0, r"{root}")
sys.path.insert(0, r"{root}\mcp_instruments")
import server as S

def hang():                      # 同步可调用：在 worker 线程里真的卡住
    time.sleep(600)              # 模拟卡在 native VISA 调用里
    return "never"

async def main():
    ex = S._executor()
    task = asyncio.ensure_future(ex.run(hang, budget_s=600, label="hang"))
    await asyncio.sleep(0.5)
    print("submitted-and-returning", flush=True)
    task.cancel()

asyncio.run(main())
'''.format(root=str(ROOT))
t0 = time.time()
try:
    r = subprocess.run([sys.executable, "-c", CHILD], capture_output=True, text=True,
                       timeout=20, cwd=str(ROOT))
    dt = time.time() - t0
    ok = r.returncode == 0 and dt < 15
    detail = f"退出码 {r.returncode}，耗时 {dt:.1f}s（旧 TPE 实现会卡到超时）"
    if not ok:
        detail += f" | stderr: {(r.stderr or '')[-160:]}"
    check("挂起任务在跑时，子进程仍能正常退出", ok, detail)
except subprocess.TimeoutExpired:
    check("挂起任务在跑时，子进程仍能正常退出", False,
          "20s 未退出——worker 线程把进程拖住了")

import server as S  # noqa: E402   （本进程内继续测语义）


def run_async(coro):
    return asyncio.run(coro)


def took(v):
    """执行器返回：错误路径是 `_err()` 的 JSON 串，正常路径是 fn() 的原始结果。"""
    if isinstance(v, str) and v.lstrip().startswith("{"):
        try:
            return json.loads(v)
        except ValueError:
            pass
    return v


print("\n§2 BUSY 闸门：不排队、不白等、不下发", flush=True)
ex = S._DeviceExecutor(default_budget_s=5.0)
calls: list[str] = []


async def busy_case():
    def slow():                       # 注意：执行器跑的是**同步**可调用（worker 线程里 fn()）
        calls.append("slow-start")
        time.sleep(1.0)
        calls.append("slow-end")
        return "slow-done"

    def second():
        calls.append("second-start")
        return "second-done"

    t1 = asyncio.ensure_future(ex.run(slow, budget_s=10, label="slow"))
    await asyncio.sleep(0.2)                      # 让 slow 真正进入 worker
    t2 = asyncio.ensure_future(ex.run(second, budget_s=10, label="second"))
    r2 = took(await t2)
    r1 = took(await t1)
    return r1, r2


r1, r2 = run_async(busy_case())
check("BUSY 时第二个调用立即返回 device_busy", r2.get("error_type") == "device_busy",
      f"{r2.get('error_type')} — {str(r2.get('error'))[:60]}")
check("被打回的调用**没有**被执行（fn 未被调用）", "second-start" not in calls, str(calls))
check("占用中的调用正常完成（返回 fn 的原始结果）", r1 == "slow-done", str(r1)[:60])

print("\n§3 预算超时：放弃等待但保持 BUSY，worker 完成后自动空闲", flush=True)
ex3 = S._DeviceExecutor(default_budget_s=0.5)
state: list[str] = []


async def timeout_case():
    def slow():
        state.append("start")
        time.sleep(1.2)
        state.append("end")
        return "done-late"

    r = took(await ex3.run(slow, budget_s=0.4, label="slow"))
    # 超时返回后立刻再调一次：应当 BUSY（worker 还在跑）
    during = took(await ex3.run(lambda: "x", budget_s=1, label="probe"))
    await asyncio.sleep(1.4)                      # 等 worker 真正跑完
    after = took(await ex3.run(lambda: "after-ok", budget_s=2, label="after"))
    return r, during, after


r, during, after = run_async(timeout_case())
check("超时返回 error_type=timeout", r.get("error_type") == "timeout", str(r)[:70])
check("超时后设备仍 BUSY（worker 未结束）", during.get("error_type") == "device_busy",
      str(during)[:60])
check("worker 真正结束后自动空闲，后续调用正常", after == "after-ok", str(after)[:60])


print("\n§4 结果与异常原样回填", flush=True)
ex4 = S._DeviceExecutor(default_budget_s=5.0)


class MyErr(Exception):
    pass


async def exc_case():
    def boom():
        raise MyErr("自定义异常")
    r = await ex4.run(boom, budget_s=5, label="boom")
    return r


try:
    run_async(exc_case())
    check("异常会传播到调用方（而不是被吞掉）", False, "没有抛异常")
except MyErr as e:
    check("异常会传播到调用方（而不是被吞掉）", str(e) == "自定义异常", str(e))
# 异常之后 BUSY 必须已清
ok_after = took(run_async(ex4.run(lambda: "ok", budget_s=2, label="after-err")))
check("异常路径也清 BUSY（后续调用可用）", ok_after == "ok", str(ok_after)[:50])

print("\n§5 预算解析（_budget_for）", flush=True)
ex5 = S._DeviceExecutor(default_budget_s=150.0)
warmed = S._PREWARM_DONE.is_set()
S._PREWARM_DONE.set()
check("默认预算", ex5._budget_for(None, (), {}) == 150.0)
check("数值预算", ex5._budget_for(300.0, (), {}) == 300.0)
check("可调用预算（按入参）",
      ex5._budget_for(lambda a, k: k["timeout_ms"] / 1000 + 30, (), {"timeout_ms": 5000}) == 35.0)
S._PREWARM_DONE.clear()
check("预热未完成时 +90s（防误杀首调用）", ex5._budget_for(150.0, (), {}) == 240.0)
if warmed:
    S._PREWARM_DONE.set()

print(f"\n== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL'} ==")
for f in fails:
    print(f"  - {f}")
sys.exit(1 if fails else 0)
