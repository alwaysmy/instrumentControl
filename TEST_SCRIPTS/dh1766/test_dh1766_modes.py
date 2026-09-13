"""DH1766 输出模式（TRAC/SERI/PARA）互斥性探测 + 恢复。

背景：手册 §3.8 面板 MODE 菜单为 NORM/SERIES/PARALL/TRACE 四选一，
SCPI §4.2.4-4.2.6 为三个独立 ON|OFF 开关——需实测固件是否互斥。

安全：继电器联动拓扑变化，模式切换前必须输出全关；结束恢复原模式+原输出。
输出：TEST_DATA/dh1766/dh1766_modes_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from common.resolver import resolve  # noqa: E402
from dh1766_control import DH1766, VisaClient  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dh1766"
# 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
RES = resolve("psu")

trace: list[dict] = []


def rec(step: str, **kw) -> None:
    trace.append({"step": step, **kw})
    print(f"[{step}] " + " ".join(f"{k}={v}" for k, v in kw.items()))


def modes(ps: DH1766) -> dict:
    return {
        "TRAC": ps.track_mode(),
        "SERI": ps.series_mode(),
        "PARA": ps.parallel_mode(),
    }


def drain(ps: DH1766) -> list[str]:
    errs = []
    for _ in range(20):
        e = ps.system_error() or ""
        if not e or e.startswith("0,"):
            break
        errs.append(e)
    return errs


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with VisaClient(RES, timeout_ms=5000) as client:
        ps = DH1766(client)
        rec("idn", value=ps.idn())
        base_modes = modes(ps)
        base_out = ps.get_output_state()
        rec("baseline_modes", **{k: str(v) for k, v in base_modes.items()})
        rec("baseline_outputs", value=base_out)
        rec("baseline_vset", value=ps.apply_voltage())

        try:
            # ---- 输出全关 ----
            ps.set_output_all([False, False, False], ps.output_mode())
            time.sleep(0.5)
            rec("outputs_off", value=ps.get_output_state())
            drain(ps)

            # ---- SERI ON 后读三路 ----
            ps.series_mode(True)
            time.sleep(0.6)
            rec("after_SERI_ON", **{k: str(v) for k, v in modes(ps).items()},
                err=drain(ps) or "clean")

            # ---- PARA ON 后读三路 ----
            ps.parallel_mode(True)
            time.sleep(0.6)
            rec("after_PARA_ON", **{k: str(v) for k, v in modes(ps).items()},
                err=drain(ps) or "clean")

            # ---- TRAC ON 后读三路 ----
            ps.track_mode(True)
            time.sleep(0.6)
            rec("after_TRAC_ON", **{k: str(v) for k, v in modes(ps).items()},
                err=drain(ps) or "clean")

            # ---- 全 OFF 后读三路 ----
            ps.track_mode(False)
            ps.series_mode(False)
            ps.parallel_mode(False)
            time.sleep(0.6)
            rec("after_ALL_OFF", **{k: str(v) for k, v in modes(ps).items()},
                err=drain(ps) or "clean")
            rec("output_mode_NORM", value=ps.output_mode())

            # ---- 新 API：set_output_mode 往返 ----
            for m in ("SERI", "PARA", "TRAC"):
                ps.set_output_mode(m)
                time.sleep(0.6)
                got = ps.output_mode()
                rec(f"set_output_mode_{m}", value=got,
                    ok=got == m, err=drain(ps) or "clean")
            try:
                ps.set_output_mode("BOGUS")
                rec("set_output_mode_BOGUS", ok=False, err="未抛错")
            except ValueError as e:
                rec("set_output_mode_BOGUS", ok=True, err=str(e)[:60])
            ps.set_output_mode("NORM")
            time.sleep(0.6)
            rec("set_output_mode_NORM", value=ps.output_mode(),
                err=drain(ps) or "clean")

            # ---- 带载切换必须被拒（无条件强制）----
            ps.set_output_all([True, True, False], ps.output_mode())
            time.sleep(0.5)
            try:
                ps.set_output_mode("SERI")
                rec("loaded_switch_blocked", ok=False, err="未抛错")
            except RuntimeError as e:
                rec("loaded_switch_blocked", ok=True, err=str(e)[:60])
            finally:
                ps.set_output_all([False, False, False], ps.output_mode())
                time.sleep(0.5)
        finally:
            # ---- 恢复原模式 ----
            for name, setter in (("TRAC", ps.track_mode), ("SERI", ps.series_mode),
                                 ("PARA", ps.parallel_mode)):
                if base_modes.get(name):
                    setter(True)
                    time.sleep(0.6)
            rec("restore_modes", **{k: str(v) for k, v in modes(ps).items()})
            # ---- 恢复原输出 ----
            ps.set_output_all(base_out, ps.output_mode())
            time.sleep(2.5)
            rec("restore_outputs", outputs=ps.get_output_state(),
                voltage_v=ps.measure_voltage_all())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"dh1766_modes_{stamp}.json"
    out.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"留痕: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
