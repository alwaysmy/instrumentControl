"""SDG->SDS 生成+测量闭环矩阵：多波形/频率/幅度，每轮自动定标+测量+断言。

安全约定：幅度<=5Vpp；结束关闭输出并清测量项。
输出：控制台 + TEST_DATA/common/waveform_matrix_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402
from sdg_control import SDG  # noqa: E402
from sds_control import SDS  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"

CASES = [
    ("SINE", 1000, 2.0, 0),
    ("SINE", 100, 2.0, 0),
    ("SINE", 10000, 2.0, 0),
    ("SINE", 100000, 2.0, 0),
    ("SQUARE", 1000, 2.0, 0),
    ("RAMP", 1000, 2.0, 0),
    ("PULSE", 1000, 2.0, 0),
    ("NOISE", 1000, 2.0, 0),
    ("SINE", 1000, 0.5, 0),
    ("SINE", 1000, 5.0, 0),
    ("SINE", 1000, 2.0, 1.0),
]


def main() -> int:
    results = []
    # 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
    gen = SDG(resolve("sdg"))
    scope = SDS(resolve("sds"))
    gen.connect()
    scope.connect()

    def drain():
        n = 0
        while True:
            e = scope.query(":SYST:ERR?").strip()
            if e.startswith("+0") or "No error" in e:
                break
            n += 1
        return n

    try:
        for wave, freq, amp, ofst in CASES:
            tag = "%s@%gHz/%gVpp" % (wave, freq, amp)
            rec = {"case": tag}
            print("== %s ==" % tag)
            try:
                gen.set_basic_wave(
                    2, WVTP=wave, FRQ="%gHZ" % freq, AMP="%gV" % amp, OFST="%gV" % ofst
                )
                time.sleep(0.3)
                gen.set_output(2, True, gen.output_state(2).get("LOAD", "HZ"))
                time.sleep(1.0)

                scale = scope.auto_scale(4)
                rec["scale"] = scale.get("actions")

                meas_vpp = scope.measure_simple("PKPK", "C4")
                meas_freq = scope.measure_simple("FREQ", "C4")
                rec["vpp"] = meas_vpp
                rec["freq"] = meas_freq

                ok_v = abs(meas_vpp - amp) / max(amp, 1e-9) < 0.25
                ok_f = (
                    abs(meas_freq - freq) / freq < 0.05
                    if wave not in ("NOISE",)
                    else True
                )
                rec["ok_v"], rec["ok_f"] = ok_v, ok_f
                verdict = "PASS" if (ok_v and ok_f) else "FAIL"
            except Exception as e:
                rec["error"] = "%s: %s" % (type(e).__name__, e)
                verdict = "ERROR"
            rec["verdict"] = verdict
            results.append(rec)
            print("   -> %s | vpp=%s freq=%s" % (verdict, rec.get("vpp"), rec.get("freq")))
    finally:
        print("-- 恢复 --")
        try:
            gen.set_output(2, False, gen.output_state(2).get("LOAD", "HZ"))
            print("   CH2 输出关闭:", gen.output_state(2).get("state"))
        except Exception as e:
            print("   恢复失败:", e)
        try:
            scope.clear_adv_measurements()
        except Exception:
            pass
        gen.close()
        scope.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / ("waveform_matrix_" + stamp + ".json")
    f.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pass = sum(1 for r in results if r["verdict"] == "PASS")
    print("\n== 结果: %d/%d PASS ==" % (n_pass, len(results)))
    print("留痕已保存: %s" % f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
