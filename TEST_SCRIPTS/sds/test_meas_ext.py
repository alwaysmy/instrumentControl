"""SDS 测量扩展命令实测（手册 3.17 p.172-185 补全项）。

安全：只读为主；写操作备份原值→写→回读→恢复。不碰复位/输出。
输出：TEST_DATA/sds/meas_ext_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sds_control import SDS
from sds_control.sds import drain_errors

OUT = ROOT / "TEST_DATA" / "sds"
OUT.mkdir(parents=True, exist_ok=True)
RES = "TCPIP0::192.168.31.220::inst0::INSTR"

trace: list[dict] = []


def rec(name: str, value=None, err=None, ok=True):
    trace.append({"item": name, "ok": ok, "value": str(value)[:200], "err": err})
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}: {str(value)[:110]}" + (f" | err={err}" if err else ""), flush=True)


def try_get(name, fn):
    try:
        rec(name, fn())
    except Exception as e:
        rec(name, f"{type(e).__name__}: {str(e)[:80]}", ok=False)


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s = SDS(RES, timeout_ms=10000)
    s.connect()
    try:
        drain_errors(s)
        rec("idn", s.idn()[:60])

        print("--- 只读查询（验证命令存在性） ---", flush=True)
        try_get("THR:SOUR?", lambda: s.meas_threshold_source())
        try_get("THR:TYPE?", lambda: s.meas_threshold_type())
        try_get("THR:ABS?", lambda: s.meas_threshold_absolute())
        try_get("THR:PERC?", lambda: s.meas_threshold_percent())
        try_get("GATE?", lambda: s.meas_gate())
        try_get("GATE:GA/GB?", lambda: s.meas_gate_pos())
        try_get("RDISplay?", lambda: s.meas_result_display())
        try_get("ADV:STAT?", lambda: s.meas_statistics())
        try_get("ADV:STAT:MAXCount?", lambda: s.meas_stat_max_count())
        try_get("ADV:STAT:HIST?", lambda: s.meas_stat_histogram())
        try_get("ADV:LINenumber?", lambda: s.adv_line_number())
        try_get("ADV:STYLe?", lambda: s.adv_style())
        try_get("ASTRategy?", lambda: s.amp_strategy())
        try_get("ASTRategy:BASE/TOP?", lambda: s.amp_strategy_base_top())
        try_get("DTIMe1 全查询", lambda: s.dtime_config(1))

        print("--- 写后回读（备份→写→读→恢复） ---", flush=True)
        # 阈值类型往返
        orig_ttype = s.meas_threshold_type()
        for t in ("ABSolute", "PERCent"):
            s.meas_threshold_type(t)
            time.sleep(0.3)
            got = s.meas_threshold_type()
            rec(f"THR:TYPE 写 {t}", got, ok=got == t)
        if orig_ttype:
            s.meas_threshold_type(orig_ttype)
            rec("THR:TYPE 恢复", s.meas_threshold_type(), ok=s.meas_threshold_type() == orig_ttype)

        # 门限开关往返
        orig_gate = s.meas_gate()
        s.meas_gate(not orig_gate)
        time.sleep(0.3)
        rec("GATE 写取反", s.meas_gate(), ok=s.meas_gate() == (not orig_gate))
        s.meas_gate(orig_gate)
        rec("GATE 恢复", s.meas_gate(), ok=s.meas_gate() == orig_gate)

        # 统计开关往返
        orig_stat = s.meas_statistics()
        s.meas_statistics(not orig_stat)
        time.sleep(0.3)
        rec("ADV:STAT 写取反", s.meas_statistics(), ok=s.meas_statistics() == (not orig_stat))
        s.meas_statistics(orig_stat)
        rec("ADV:STAT 恢复", s.meas_statistics(), ok=s.meas_statistics() == orig_stat)

        # 结果样式往返
        orig_rd = s.meas_result_display()
        new_rd = "FLOating" if str(orig_rd).upper().startswith("EMB") else "EMBedded"
        s.meas_result_display(new_rd)
        time.sleep(0.3)
        got_rd = s.meas_result_display()
        rec(f"RDISplay 写 {new_rd}", got_rd, ok=str(got_rd).upper().startswith(new_rd[:3].upper()))
        if orig_rd:
            s.meas_result_display(orig_rd)
            rec("RDISplay 恢复", s.meas_result_display())

        # P 槽统计（需槽已开——用现有 P1）
        try_get("P1 STAT? ALL", lambda: s.adv_statistics(1, "ALL"))
        try_get("P1 STAT? MEAN", lambda: s.adv_statistics(1, "MEAN"))

        rec("错误队列终态", drain_errors(s) or "clean")
    finally:
        s.close()

    out = OUT / f"meas_ext_{stamp}.json"
    out.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    n_fail = sum(1 for r in trace if not r["ok"])
    print(f"\n== {len(trace) - n_fail}/{len(trace)} PASS ==\n留痕: {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
