"""猜测命令批量核验：只读查询 + 无害写回读，每步查错误队列。

覆盖：SDS ACQ:TYPE? / SDG ARWV? + BSWV 写回读 / 34465A NPLC + MEAS 族。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from keysight_3446x import DMM  # noqa: E402
from sdg_control import SDG  # noqa: E402
from sds_control import SDS  # noqa: E402

results = []


def check(tag, fn):
    try:
        v = fn()
        results.append({"item": tag, "ok": True, "value": str(v)[:80]})
        print(f"  [OK]   {tag}: {str(v)[:70]}")
    except Exception as e:
        results.append({"item": tag, "ok": False, "error": f"{type(e).__name__}: {e}"})
        print(f"  [FAIL] {tag}: {type(e).__name__}")


def main() -> int:
    print("== SDS824X HD ==")
    with SDS("TCPIP0::192.168.31.220::inst0::INSTR") as s:
        check("ACQ:TYPE?", lambda: s.query("ACQ:TYPE?"))
        s.query(":SYST:ERR?")
        check("C1:TRA? (通道显示)", lambda: s.query("C1:TRA?"))

    print("== SDG2122X ==")
    with SDG("TCPIP0::192.168.31.206::inst0::INSTR") as g:
        check("C1:ARWV?", lambda: g.query("C1:ARWV?"))
        g.query(":SYST:ERR?")

        def bswv_write_readback():
            before = g.basic_wave(1).get("PHSE")
            g.set_basic_wave(1, PHSE="0")     # 写同值，无副作用
            time.sleep(0.3)
            err = g.query(":SYST:ERR?").strip()
            after = g.basic_wave(1).get("PHSE")
            return f"before={before} after={after} err={err}"

        check("BSWV PHSE 写+回读", bswv_write_readback)

    print("== Keysight 34465A ==")
    with DMM("TCPIP0::192.168.31.123::inst0::INSTR") as d:
        d.configure("volt_dc", range_v=0.1)
        check("NPLC 查询", lambda: d.get_nplc())
        check("NPLC=1 写+回读", lambda: (d.set_nplc(1), time.sleep(0.2), d.get_nplc())[2])
        for fn in ("volt_ac", "curr_dc", "curr_ac", "res", "fres", "cap", "freq"):
            check(f"MEAS {fn}", lambda fn=fn: d.measure(fn))
        d.configure("volt_dc", range_v=0.1)  # 恢复
        e = d.query(":SYST:ERR?").strip()
        results.append({"item": "34465A 最终错误队列", "ok": e.startswith("+0"), "value": e})
        print(f"  [{'OK]' if e.startswith('+0') else 'FAIL]'} 最终错误队列: {e}")

    n_fail = sum(1 for r in results if not r["ok"])
    print(f"\n== 结果: {len(results) - n_fail}/{len(results)} OK ==")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
