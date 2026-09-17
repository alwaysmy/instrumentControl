"""VISA **并发假设**的真机实验（MHO984D over LAN/VXI-11 + DG832 over USB-TMC）。

背景：仓库里有两处设计建立在"VISA 并发怎么用才安全"的假设上，但一直只有零散现场经验
（`identify_lan` 注释："多线程各自 ResourceManager() 并发 open 会随机抛
VI_ERROR_INV_OBJECT，且异常会从 rm.close() 里抛出、冲垮整轮扫描"），没有系统验证。
两台仪器都在（MHO 走 LAN、DG832 走 USB-TMC）时把假设逐条测掉：

    H1 共享单个 ResourceManager + 多线程并发访问**不同**设备 → 安全（identify_lan_all 的做法）
    H1b 共享 RM + 多线程并发 open **同一**资源 → 会话分配有上限吗（VI_ERROR_ALLOC？）
    H2 每线程各自 RM 并发（对端现场说会抛 VI_ERROR_INV_OBJECT；本机复现与否都是结论）
    H3 同一设备**两个会话**并发（LAN/VXI-11）→ 响应会不会串台
    H4 同一设备**两个会话**并发（USB-TMC）→ 单管道共享 IN/OUT，**响应可能串台**
    H5 对照：同一设备两会话但**串行化**（一把锁）→ 应当零串台（证明"单 worker"设计是对的）

**期望值自校准**：串台判定需要"两条查询的响应互不相同"，故先单线程读一遍候选查询，
挑出一对不同的（避免把"记错现场值"误判成串台——首轮实验就踩过这个坑）。
全程**只读**查询，不动任何输出、保护与设定。
留痕：TEST_DATA/common/visa_concurrency_<ts>.json

    python TEST_SCRIPTS/common/verify_visa_concurrency.py
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pyvisa  # noqa: E402
from common.resolver import resolve  # noqa: E402

AP = argparse.ArgumentParser(description="VISA 并发假设实验")
AP.add_argument("--same-res-storm", action="store_true",
                help="额外跑'同一资源多线程并发 open'（T1b/T2b）——实测会污染仪器响应流"
                     "（MHO 通道被打成持续错位，需面板重置 LAN），默认跳过")
AP.add_argument("--lan-two-session", action="store_true",
                help="额外跑 LAN 两会话实验（T3）——**会**把设备的 VXI-11 链路搞成粘滞错位"
                     "（2026-09-17 实测代价），仅在你愿意事后重置该仪器 LAN 时开启")
ARGS = AP.parse_args()

MHO_RES = resolve("mho")
DG_RES = resolve("dg")
N = 150
N_SESSION = 200
results: dict = {"ts": datetime.now().isoformat(timespec="seconds"),
                 "mho": MHO_RES, "dg": DG_RES, "n_per_thread": N, "tests": {}}
fails: list[str] = []

MHO_CANDIDATES = ("*IDN?", ":CHANnel1:OFFSet?", ":CHANnel3:OFFSet?", ":CHANnel3:SCALe?",
                  ":TIMebase:MAIN:SCALe?", ":ACQuire:MDEPth?")
DG_CANDIDATES = ("*IDN?", ":SOUR1:FREQ?", ":SOUR2:FREQ?", ":OUTP1?", ":OUTP2?")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:62s} {str(detail)[:96]}", flush=True)
    if not ok:
        fails.append(name)


def info(name: str, detail: str = "") -> None:
    print(f"  [INFO] {name:62s} {str(detail)[:96]}", flush=True)


def open_session(res: str, rm=None):
    own = rm is None
    rm = rm or pyvisa.ResourceManager()
    inst = rm.open_resource(res, open_timeout=3000)
    inst.timeout = 2000
    if "SOCKET" in res.upper():
        inst.read_termination = "\n"
        inst.write_termination = "\n"
    return inst, (rm if own else None)


def loop(inst, queries, n, out: dict, barrier=None):
    lat: list[float] = []
    errors: list[str] = []
    seen: list[str] = []
    if barrier is not None:
        barrier.wait()
    for i in range(n):
        q = queries[i % len(queries)]
        t0 = time.perf_counter()
        try:
            r = inst.query(q).strip()
            lat.append((time.perf_counter() - t0) * 1000)
            if len(seen) < 4:
                seen.append(r)
        except Exception as e:                      # noqa: BLE001
            errors.append(f"{type(e).__name__}: {str(e)[:70]}")
    out["n"] = n
    out["errors"] = len(errors)
    out["error_kinds"] = sorted({e.split(":")[0] for e in errors})
    out["error_sample"] = errors[:2]
    out["latency_ms"] = ({"mean": round(statistics.mean(lat), 2)} if lat else None)
    out["responses_seen"] = seen


def pick_distinct_queries(res, candidates):
    """单线程读候选查询，返回响应**互不相同**的两条（用于串台检测）。"""
    inst, own = open_session(res)
    vals: list[tuple[str, str]] = []
    try:
        for q in candidates:
            try:
                vals.append((q, inst.query(q).strip()))
            except Exception:                       # noqa: BLE001
                continue
    finally:
        inst.close()
        if own:
            own.close()
    distinct = [v for v in vals if v[1] not in ("", "0")]
    for i in range(len(distinct)):
        for j in range(i + 1, len(distinct)):
            if distinct[i][1] != distinct[j][1]:
                return distinct[i], distinct[j], vals
    return None, None, vals


def two_session_probe(res, label, serialize: bool):
    """同一设备两会话并发（可选串行化）→ 统计错误与**串台**（收到对方查询的答案）。"""
    qa, qb, _all = pick_distinct_queries(res, MHO_CANDIDATES if res == MHO_RES else DG_CANDIDATES)
    if qa is None:
        return {"skipped": "找不到两条响应不同的查询（现场值恰好相同）"}
    (QA, VA), (QB, VB) = qa, qb
    out: dict = {"qa": QA, "va": VA, "qb": QB, "vb": VB, "serialized": serialize,
                 "a": {}, "b": {}, "cross_talk": []}
    lock = threading.Lock() if serialize else None

    def probe(inst, q, mine, other, slot, barrier):
        barrier.wait()
        for _ in range(N_SESSION):
            try:
                if lock is not None:
                    with lock:
                        r = inst.query(q).strip()
                else:
                    r = inst.query(q).strip()
                if mine not in r:
                    slot["mismatch"] = slot.get("mismatch", 0) + 1
                    if other in r and len(out["cross_talk"]) < 6:
                        out["cross_talk"].append({"asked": q, "got": r, "belongs_to": other})
            except Exception as e:                  # noqa: BLE001
                slot["errors"] = slot.get("errors", 0) + 1
                slot.setdefault("error_sample", []).append(f"{type(e).__name__}: {str(e)[:40]}")

    try:
        i_a, _ = open_session(res)
        i_b, _ = open_session(res)
    except Exception as e:                          # noqa: BLE001
        out["open_two_sessions"] = f"{type(e).__name__}: {str(e)[:70]}"
        return out
    out["open_two_sessions"] = True
    try:
        bar = threading.Barrier(2)
        ta = threading.Thread(target=probe, args=(i_a, QA, VA, VB, out["a"], bar))
        tb = threading.Thread(target=probe, args=(i_b, QB, VB, VA, out["b"], bar))
        [t.start() for t in (ta, tb)]
        [t.join() for t in (ta, tb)]
    finally:
        for i in (i_a, i_b):
            try:
                i.close()
            except Exception:
                pass
    out["a_total_mismatch"] = out["a"].get("mismatch", 0)
    out["b_total_mismatch"] = out["b"].get("mismatch", 0)
    out["a_errors"] = out["a"].get("errors", 0)
    out["b_errors"] = out["b"].get("errors", 0)
    return out


print(f"MHO  = {MHO_RES}\nDG832= {DG_RES}\n", flush=True)

# ---------------------------------------------------------------- T0 基线
print("§T0 基线：单线程各 100 次", flush=True)
t0: dict = {}
for label, res, qs in (("mho", MHO_RES, ["*IDN?", ":CHANnel3:OFFSet?", ":TIMebase:MAIN:SCALe?"]),
                       ("dg", DG_RES, ["*IDN?", ":SOUR1:FREQ?", ":SOUR2:FREQ?"])):
    inst, own = open_session(res)
    try:
        out: dict = {}
        loop(inst, qs, 100, out)
        t0[label] = out
        print(f"  {label}: {100 - out['errors']}/100 成功，延迟 {out['latency_ms']}")
    finally:
        inst.close()
        if own:
            own.close()
results["tests"]["T0_baseline"] = t0
check("两台设备单线程基线均无错误", all(v["errors"] == 0 for v in t0.values()),
      f"MHO {t0['mho']['errors']} 错 / DG {t0['dg']['errors']} 错")

# ---------------------------------------------------------------- T1 共享 RM 并发（不同设备）
print("\n§T1 共享**单个** RM + 两线程并发访问不同设备（= identify_lan_all 的做法）", flush=True)
shared_rm = pyvisa.ResourceManager()
res_t1: dict = {}
mho_i = dg_i = None
try:
    mho_i, _ = open_session(MHO_RES, rm=shared_rm)
    dg_i, _ = open_session(DG_RES, rm=shared_rm)
    bar = threading.Barrier(2)
    outs = {"mho": {}, "dg": {}}
    th = [threading.Thread(target=loop, args=(mho_i, ["*IDN?", ":CHANnel3:OFFSet?"], N, outs["mho"], bar)),
          threading.Thread(target=loop, args=(dg_i, ["*IDN?", ":SOUR2:FREQ?"], N, outs["dg"], bar))]
    t_start = time.perf_counter()
    [t.start() for t in th]
    [t.join() for t in th]
    res_t1 = {"mho": outs["mho"], "dg": outs["dg"], "wall_s": round(time.perf_counter() - t_start, 2)}
finally:
    for i in (mho_i, dg_i):
        try:
            i and i.close()
        except Exception:
            pass
    shared_rm.close()
results["tests"]["T1_shared_rm_two_devices"] = res_t1
check("H1 成立：共享 RM 下两设备并发 300 次查询零错误",
      res_t1["mho"]["errors"] == 0 and res_t1["dg"]["errors"] == 0,
      f"MHO {res_t1['mho']['errors']} / DG {res_t1['dg']['errors']}，墙钟 {res_t1['wall_s']}s")

# ---------------------------------------------------------------- T1b 共享 RM 并发 open 同一资源
print("\n§T1b 共享 RM + N 线程并发 open **同一**资源（N=1 表示未开 --same-res-storm）", flush=True)

res_t1b: dict = {"ok": 0, "errors": [], "kinds": []}
rm_b = pyvisa.ResourceManager()
N_STORM = 20 if ARGS.same_res_storm else 1
bar2 = threading.Barrier(N_STORM)


def open_close(out):
    bar2.wait()
    try:
        inst, _ = open_session(MHO_RES, rm=rm_b)   # 统一入口：socket 会配换行终止符
        inst.query("*IDN?")
        inst.close()
        out["ok"] += 1
    except Exception as e:                          # noqa: BLE001
        out["errors"].append(f"{type(e).__name__}: {str(e)[:60]}")
        out["kinds"].append(type(e).__name__)


ths = [threading.Thread(target=open_close, args=(res_t1b,)) for _ in range(N_STORM)]
[t.start() for t in ths]
[t.join() for t in ths]
rm_b.close()
res_t1b["kinds"] = sorted(set(res_t1b["kinds"]))
results["tests"]["T1b_shared_rm_parallel_open"] = res_t1b
info("H1b 结果：并发会话分配上限", f"{res_t1b['ok']}/{N_STORM} 成功；错误类型 {res_t1b['kinds']}；"
     f"样例 {res_t1b['errors'][:1]}")

# ---------------------------------------------------------------- T2b 每线程各自 RM（同资源并发）
print("\n§T2b 每线程**各自** RM + N 线程并发 open 同一资源（N=1 表示未开 --same-res-storm）", flush=True)
res_t2b: dict = {"ok": 0, "errors": [], "kinds": [], "close_errors": []}
N_OWN = 8 if ARGS.same_res_storm else 1
bar3 = threading.Barrier(N_OWN)


def own_rm_round(out):
    rm = None
    bar3.wait()
    try:
        rm = pyvisa.ResourceManager()
        inst, _ = open_session(MHO_RES, rm=rm)     # 同上：socket 需换行终止符
        inst.query("*IDN?")
        inst.close()
        out["ok"] += 1
    except Exception as e:                          # noqa: BLE001
        out["errors"].append(f"{type(e).__name__}: {str(e)[:60]}")
        out["kinds"].append(type(e).__name__)
    finally:
        if rm is not None:
            try:
                rm.close()
            except Exception as e:                  # noqa: BLE001
                out["close_errors"].append(f"{type(e).__name__}: {str(e)[:60]}")


th2b = [threading.Thread(target=own_rm_round, args=(res_t2b,)) for _ in range(N_OWN)]
[t.start() for t in th2b]
[t.join() for t in th2b]
res_t2b["kinds"] = sorted(set(res_t2b["kinds"]))
results["tests"]["T2b_rm_per_thread_same_res"] = res_t2b
info("H2 结果：各自 RM + N 线程同资源", f"{res_t2b['ok']}/{N_OWN} 成功；错误类型 {res_t2b['kinds']}；"
     f"rm.close() 异常 {len(res_t2b['close_errors'])}；样例 {res_t2b['errors'][:1]}")

# ---------------------------------------------------------------- T3/T4/T5 同一设备两会话
print("\n§T3 同一设备两会话并发 — MHO（LAN 或 raw）", flush=True)
if ARGS.lan_two_session:
    res_t3 = two_session_probe(MHO_RES, "mho", serialize=False)
    results["tests"]["T3_two_sessions_lan"] = res_t3
    check("H3：MHO 两会话**串台计为 0 才算安全**（实测通常不为 0）",
          res_t3.get("a_total_mismatch") == 0 and res_t3.get("b_total_mismatch") == 0,
          f"串台 a/b={res_t3.get('a_total_mismatch')}/{res_t3.get('b_total_mismatch')}，"
          f"错误 a/b={res_t3.get('a_errors')}/{res_t3.get('b_errors')}")
else:
    results["tests"]["T3_two_sessions_lan"] = {
        "skipped": "默认跳过：实测会把设备的会话响应流搞成错位（VXI-11 需设备侧重置才恢复）"}
    info("T3 默认跳过（保护仪器）", "要跑请加 --lan-two-session；结论见 docs/visa_concurrency_20260917.md")

print("\n§T4 同一设备两会话并发 — DG832（USB-TMC：单管道）", flush=True)
res_t4 = two_session_probe(DG_RES, "dg", serialize=False)
results["tests"]["T4_two_sessions_usb"] = res_t4
info("H4 结果：USB 两会话", f"串台 a/b={res_t4.get('a_total_mismatch')}/{res_t4.get('b_total_mismatch')}，"
     f"错误 a/b={res_t4.get('a_errors')}/{res_t4.get('b_errors')}，"
     f"样例 {res_t4.get('cross_talk', [])[:1]}")
check("H4 判定：USB 两会话会串台/大量丢响应（这正是单进程单 worker 存在的理由）",
      (res_t4.get("a_total_mismatch", 0) + res_t4.get("b_total_mismatch", 0) > 0)
      or (res_t4.get("a_errors", 0) + res_t4.get("b_errors", 0) > 0),
      f"串台合计 {res_t4.get('a_total_mismatch', 0) + res_t4.get('b_total_mismatch', 0)}，"
      f"错误合计 {res_t4.get('a_errors', 0) + res_t4.get('b_errors', 0)}")

print("\n§T5 对照：同一设备两会话但**串行化**（一把锁）— DG832/USB", flush=True)
res_t5 = two_session_probe(DG_RES, "dg", serialize=True)
results["tests"]["T5_two_sessions_usb_serialized"] = res_t5
check("H5 成立：串行化后 USB 两会话零串台、零错误（= 单 worker 设计的价值）",
      res_t5.get("a_total_mismatch") == 0 and res_t5.get("b_total_mismatch") == 0
      and res_t5.get("a_errors") == 0 and res_t5.get("b_errors") == 0,
      f"串台 a/b={res_t5.get('a_total_mismatch')}/{res_t5.get('b_total_mismatch')}，"
      f"错误 a/b={res_t5.get('a_errors')}/{res_t5.get('b_errors')}")

# ---------------------------------------------------------------- 收尾：把仪器留在对齐状态
print("\n§收尾 对齐核查（实验不应把仪器留在错位状态）", flush=True)
align: dict = {}
for label, res in (("mho", MHO_RES), ("dg", DG_RES)):
    try:
        i, own = open_session(res)
        try:
            got = i.query("*IDN?").strip()
            want = "MHO" if label == "mho" else "DG8"
            align[label] = {"idn": got[:60], "aligned": want in got}
            info(f"{label} 对齐核查", f"*IDN? -> {got[:48]} {'✓' if want in got else '✗ 未对齐'}")
        finally:
            i.close()
            if own:
                own.close()
    except Exception as e:                          # noqa: BLE001
        align[label] = {"error": f"{type(e).__name__}: {str(e)[:70]}"}
        info(f"{label} 对齐核查失败", f"{type(e).__name__}: {str(e)[:60]}")
results["alignment_after"] = align
check("实验后两台仪器仍对齐（未留在错位状态）",
      all(v.get("aligned") for v in align.values()),
      json.dumps(align, ensure_ascii=False)[:110])

out_path = ROOT / "TEST_DATA" / "common" / f"visa_concurrency_{datetime.now():%Y%m%d_%H%M%S}.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n留痕: {out_path}")
print(f"== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL'} ==")
for f in fails:
    print(f"  - {f}")
sys.exit(1 if fails else 0)
