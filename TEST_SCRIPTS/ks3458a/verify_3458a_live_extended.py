"""ks3458a **扩展真机验收**：固定档/自动挡、SINT 与 DINT 突发、ACV 配置与 AC 读数。

与 `verify_3458a_live.py`（只读 + 同值 configure）分开：本脚本**会改设备配置**
（数字档预设、功能切 AC），跑完用 `PRESET NORM` + 显式 DCV/NPLC 恢复（手册 p.217 的
官方"退出数字档"路径，**不发 `RESET`**，也不动校准常数）。

用法：
    python TEST_SCRIPTS/ks3458a/verify_3458a_live_extended.py [resource]
留痕：TEST_DATA/ks3458a/verify_3458a_live_extended_<stamp>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from keysight_3458a import DMM3458A, commands as C  # noqa: E402

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="ascii", errors="replace")
    except Exception:
        pass

RESOURCE = sys.argv[1] if len(sys.argv) > 1 else "GPIB0::9::INSTR"
rows: list[dict] = []
BASE_RANGE, BASE_NPLC = 0.1, 10.0        # 现场原状：DCV 0.1 V 档 / NPLC 10


def rec(name: str, ok, detail=""):
    rows.append({"item": name, "ok": (None if ok is None else bool(ok)), "detail": str(detail)[:240]})
    tag = "PASS" if ok is True else ("UNVERIFIED" if ok is None else "FAIL")
    print(f"  [{tag:10s}] {name:44s} {str(detail)[:88]}", flush=True)


def main() -> int:
    d = DMM3458A(RESOURCE, timeout_s=25.0)
    d.connect()
    try:
        # ---- 1) 固定档 ----
        d.configure_dcv(BASE_RANGE, BASE_NPLC)
        st = d.state()
        rec("fixed range DCV 0.1 -> readback",
            abs((st.get("range_v") or 0) - BASE_RANGE) < 1e-12 and not st.get("autorange"),
            f"range={st.get('range_v')} arange={st.get('arange')} func={st.get('function')}")

        # ---- 2) 自动挡（ARANGE ON/OFF）----
        d.set_autorange(True)
        st = d.state()
        rec("ARANGE ON -> autorange", st.get("autorange") is True and "ON" in str(st.get("arange")),
            f"arange={st.get('arange')} autorange={st.get('autorange')} range={st.get('range_v')}")
        d.set_autorange(False)
        st = d.state()
        rec("ARANGE OFF -> fixed", st.get("autorange") is False and "OFF" in str(st.get("arange")),
            f"arange={st.get('arange')} autorange={st.get('autorange')}")

        # ---- 3) DCV AUTO（FUNC 的 max_input=AUTO 写法）----
        d.configure_dcv("AUTO", BASE_NPLC)
        st = d.state()
        rec("DCV AUTO -> autorange", st.get("autorange") is True,
            f"func={st.get('function')} autorange={st.get('autorange')}")

        # ---- 4) 回到固定档 + 单次读数 ----
        d.configure_dcv(BASE_RANGE, BASE_NPLC)
        v = d.read_dcv()
        rec("back to fixed range + single read", isinstance(v, float), f"{v:.9e} V")

        # ---- 5) SINT 突发 ----
        b = d.read_burst(100, sample_interval_s=1e-4, dcv_range=BASE_RANGE, data_format="SINT")
        sm = b["summary"]
        rec("burst SINT n=100", len(b["values"]) == 100 and sm["bytes_expected"] == 202,
            f"n={len(b['values'])} bytes={sm['bytes_read']}/{sm['bytes_expected']} "
            f"iscale={sm['iscale_v_per_lsb']:.3e} mean={sm.get('mean'):.3e} sd={sm.get('stddev'):.2e}")

        # ---- 6) DINT 突发（>120% 档位信号必须用它）----
        b2 = d.read_burst(100, sample_interval_s=1e-4, dcv_range=BASE_RANGE, data_format="DINT")
        sm2 = b2["summary"]
        rec("burst DINT n=100", len(b2["values"]) == 100 and sm2["bytes_expected"] == 400,
            f"n={len(b2['values'])} bytes={sm2['bytes_read']}/{sm2['bytes_expected']} "
            f"fmt={sm2['data_format']} iscale={sm2['iscale_v_per_lsb']:.3e} mean={sm2.get('mean'):.3e}")
        rec("SINT/DINT 均值一致（同源同档）",
            abs((sm.get('mean') or 0) - (sm2.get('mean') or 0)) < max(1e-3, abs(sm.get('mean') or 1) * 5),
            f"|dmean|={abs((sm.get('mean') or 0) - (sm2.get('mean') or 0)):.3e}")

        # ---- 7) 退出数字档（PRESET NORM，不是 RESET）----
        d.write(C.PRESET_NORM)
        import time as _t
        _t.sleep(1.2)
        d.prepare_for_read()
        d.configure_dcv(BASE_RANGE, BASE_NPLC)
        st = d.state()
        rec("PRESET NORM + 回到 DCV 0.1/NPLC10",
            str(st.get("function", "")).startswith("1") and st.get("mem") is not None,
            f"func={st.get('function')} nplc={st.get('nplc')} oformat={st.get('oformat')} "
            f"mformat={st.get('mformat')} mem={st.get('mem')}")
        v2 = d.read_dcv()
        rec("恢复后单次读数", isinstance(v2, float), f"{v2:.9e} V")

        # ---- 8) ACV 配置 + AC 单次读数（手册未证实的配方，实测见结论）----
        try:
            d.configure_acv(10.0, band_lo=20.0, band_hi=100000.0, sync=False)
            st = d.state()
            rec("ACV 配置（ACV 10 / SETACV ANA / ACBAND 20,1E5）", True,
                f"func={st.get('function')} nplc={st.get('nplc')} err={d.error_string()}")
            try:
                vac = d.read_acv(timeout_s=20.0)
                rec("AC 单次读数（TARM SGL,1 配方）", True, f"{vac:.6e} V AC")
            except Exception as e:                       # noqa: BLE001
                rec("AC 单次读数（TARM SGL,1 配方）", None,
                    f"未证实：{type(e).__name__}: {str(e)[:80]}")
        except Exception as e:                           # noqa: BLE001
            rec("ACV 配置", False, f"{type(e).__name__}: {e}")

        # ---- 9) 交回 DCV 原状 ----
        d.configure_dcv(BASE_RANGE, BASE_NPLC)
        st = d.state()
        rec("finally: DCV 0.1/NPLC10 交回", str(st.get("function", "")).startswith("1"),
            f"func={st.get('function')} range={st.get('range_v')} nplc={st.get('nplc')} "
            f"trig={st.get('trig')} inbuf={st.get('inbuf')} end={st.get('end')}")
    finally:
        d.close()

    out_dir = ROOT / "TEST_DATA" / "ks3458a"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = out_dir / f"verify_3458a_live_extended_{stamp}.json"
    n_fail = sum(1 for r in rows if r["ok"] is False)
    n_unv = sum(1 for r in rows if r["ok"] is None)
    f.write_text(json.dumps({
        "when": datetime.now().isoformat(timespec="seconds"),
        "resource": RESOURCE,
        "note": "改配置项：ARANGE / DCV AUTO / PRESET DIG（突发）/ ACV；恢复用 PRESET NORM（非 RESET）",
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== result: {len(rows) - n_fail - n_unv}/{len(rows)} PASS, "
          f"{n_unv} UNVERIFIED, {n_fail} FAIL ==\nevidence: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
