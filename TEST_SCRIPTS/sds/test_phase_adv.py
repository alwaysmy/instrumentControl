"""SDS824X HD 双通道相位测量（ADVanced PHA）实机验证。

验证目标（手册 CN11G §3.17 / 表 5-1）：
  PHA = 通道A与通道B第一个上升沿中值点间的相位差（度），需两通道完整周期。
  正确序列：Pn ON + SOURce1=A + SOURce2=B + TYPE PHA + VALue?
同时复核用户已尝试失败的 4 种命令的真实失败模式。

安全：只动测量槽配置；结束恢复（槽 OFF + MODE 恢复）；不碰复位/输出。
输出：TEST_DATA/sds/phase_adv_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.visa_client import VisaClient
from sds_control import SDS

RES = "TCPIP0::192.168.31.220::inst0::INSTR"
OUT_DIR = ROOT / "TEST_DATA" / "sds"
OUT_DIR.mkdir(parents=True, exist_ok=True)

log: dict = {"steps": []}


def step(name: str, **kw) -> None:
    log["steps"].append({"name": name, **kw})
    print(f"[{name}] " + " ".join(f"{k}={v}" for k, v in kw.items()))


def drain(s: SDS) -> list[str]:
    errs = []
    for _ in range(30):
        e = s.query(":SYST:ERR?").strip()
        if e.startswith("+0") or "No error" in e:
            break
        errs.append(e)
    return errs


def wcheck(s: SDS, cmd: str) -> str:
    """写→查错，返回错误串（空=干净）"""
    s.write(cmd)
    time.sleep(0.2)
    e = s.query(":SYST:ERR?").strip()
    return "" if (e.startswith("+0") or "No error" in e) else e


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log["timestamp"] = stamp
    scope = SDS(RES, timeout_ms=8000)
    scope.connect()
    slot_used = None
    orig_mode = None
    try:
        # ---- Phase A: 只读基线 ----
        step("idn", value=scope.idn())
        orig_mode = scope.query(":MEASure:MODE?").strip()
        step("meas_mode_orig", value=orig_mode)
        slots = {}
        for n in range(1, 13):
            try:
                st = scope.query(f":MEASure:ADVanced:P{n}?").strip()
            except Exception as ex:
                st = f"QUERY_FAIL:{type(ex).__name__}"
            slots[f"P{n}"] = st
        step("pslots", **slots)
        free = next((n for n in range(1, 13) if slots[f"P{n}"] == "OFF"), None)
        step("free_slot", value=free)
        step("trig_status", value=scope.trigger_status())
        step("trig_source", value=scope.edge_source())
        try:
            step("trig_level", value=scope.edge_level())
        except Exception as ex:
            step("trig_level", error=type(ex).__name__)
        for ch in (1, 2):
            try:
                disp = scope.query(f"C{ch}:TRA?").strip()
                scale = scope.query(f"C{ch}:VDIV?")
                step(f"ch{ch}", display=disp, scale=scale)
            except Exception as ex:
                step(f"ch{ch}", error=type(ex).__name__)
        try:
            step("timebase", value=scope.timebase_scale())
        except Exception as ex:
            step("timebase", error=type(ex).__name__)

        if free is None:
            step("abort", reason="无空闲 P 槽（P1..P12 全 ON），拒绝覆盖用户配置")
            return 2

        # ---- Phase B: C1/C2 信号确认（SIMPLE，可靠路径）----
        sig = {}
        for ch, item in (("C1", "FREQ"), ("C1", "PKPK"), ("C2", "FREQ"), ("C2", "PKPK")):
            try:
                sig[f"{ch}_{item}"] = scope.measure_simple(item, ch, timeout_s=8.0)
            except Exception as ex:
                sig[f"{ch}_{item}"] = f"FAIL:{type(ex).__name__}"
        step("signals_simple", **{k: str(v) for k, v in sig.items()})

        # ---- Phase C: PHA 配置 + 读值 ----
        slot_used = free
        n = free
        errs = drain(scope)
        step("drain_before", removed=len(errs), leftovers=errs[:5])
        for cmd in (
            ":MEASure:MODE ADVanced",
            f":MEASure:ADVanced:P{n}:SOURce1 C2",
            f":MEASure:ADVanced:P{n}:SOURce2 C1",
            f":MEASure:ADVanced:P{n}:TYPE PHA",
            f":MEASure:ADVanced:P{n} ON",
        ):
            e = wcheck(scope, cmd)
            step("write", cmd=cmd, err=e or "clean")
        # 回读比对
        rb = {}
        for q in ("SOURce1", "SOURce2", "TYPE", ""):
            cmd = f":MEASure:ADVanced:P{n}:{q}?" if q else f":MEASure:ADVanced:P{n}?"
            try:
                rb[q or "STATE"] = scope.query(cmd).strip()
            except Exception as ex:
                rb[q or "STATE"] = f"FAIL:{type(ex).__name__}"
        step("readback", **rb)
        # 等待测量稳定后读值（最多轮询 ~12s）
        val = None
        raw_last = ""
        t0 = time.monotonic()
        while time.monotonic() - t0 < 12:
            time.sleep(1.0)
            raw_last = scope.query(f":MEASure:ADVanced:P{n}:VALue?").strip()
            try:
                v = float(raw_last)
                if abs(v) < 9.0e36:
                    val = v
                    break
            except ValueError:
                pass
        step("phase_C2C1", value=val, raw=raw_last)

        # ---- Phase D: 交换 A/B 验证符号约定 ----
        e1 = wcheck(scope, f":MEASure:ADVanced:P{n}:SOURce1 C1")
        e2 = wcheck(scope, f":MEASure:ADVanced:P{n}:SOURce2 C2")
        step("swap_sources", err1=e1 or "clean", err2=e2 or "clean")
        val2 = None
        raw2 = ""
        t0 = time.monotonic()
        while time.monotonic() - t0 < 12:
            time.sleep(1.0)
            raw2 = scope.query(f":MEASure:ADVanced:P{n}:VALue?").strip()
            try:
                v = float(raw2)
                if abs(v) < 9.0e36:
                    val2 = v
                    break
            except ValueError:
                pass
        step("phase_C1C2", value=val2, raw=raw2)
        if val is not None and val2 is not None:
            step("sign_check", sum_deg=round(val + val2, 3),
                 note="若互为相反数(+360归一)，则 PHA=B相对A的相位")
    finally:
        # ---- Phase F: 恢复 ----
        try:
            if slot_used is not None:
                e = wcheck(scope, f":MEASure:ADVanced:P{slot_used} OFF")
                step("restore_slot_off", err=e or "clean")
            if orig_mode:
                e = wcheck(scope, f":MEASure:MODE {orig_mode}")
                step("restore_mode", err=e or "clean")
            e = wcheck(scope, ":MEASure:SIMPle:CLEar")
            step("restore_simple_clear", err=e or "clean")
            leftovers = drain(scope)
            step("restore_drain", leftovers=leftovers[:5])
        finally:
            scope.close()

    # ---- Phase E: 失败命令复核（短超时独立连接，不污染主会话队列）----
    from common.visa_client import VisaClient as VC

    c2 = VC(RES, timeout_ms=3000, open_timeout_ms=3000)
    try:
        def probe(cmd: str, is_query: bool):
            try:
                r = c2.query(cmd) if is_query else (c2.write(cmd), "WRITE_OK")
                left = []
                for _ in range(5):
                    e = c2.query(":SYST:ERR?").strip()
                    if e.startswith("+0") or "No error" in e:
                        break
                    left.append(e)
                return {"resp": str(r)[:80], "queue": left}
            except Exception as ex:
                return {"resp": f"{type(ex).__name__}: {str(ex)[:60]}", "queue": []}

        step("fail_MEAS_PHAS", **probe("MEAS:PHAS? C1,C2", True))
        step("fail_MEAS_MEAS1_TYPE", **probe("MEAS:MEAS1:TYPE?", True))
        step("fail_MEAD_write", **probe("MEAD C1,PHASE,C2", False))
        step("fail_PAVA", **probe("PAVA? PHAS", True))
        step("fail_MEAS_FREQ_C1", **probe("MEAS:FREQ? C1", True))
    finally:
        c2.close()

    out = OUT_DIR / f"phase_adv_{stamp}.json"
    out.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n留痕: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
