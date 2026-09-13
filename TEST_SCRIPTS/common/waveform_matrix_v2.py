"""SDG->SDS 扩展闭环矩阵 v2：更多波形/频率/幅度/偏置，每轮留痕触发状态。"""
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

# (波形, 频率Hz, 幅度Vpp, 偏置V, 期望FREQ是否有效)
CASES = [
    ("SINE", 10, 2.0, 0, True),
    ("SINE", 100, 2.0, 0, True),
    ("SINE", 1000, 2.0, 0, True),
    ("SINE", 10000, 2.0, 0, True),
    ("SINE", 100000, 2.0, 0, True),
    ("SINE", 1000000, 1.0, 0, True),
    ("SQUARE", 1000, 2.0, 0, True),
    ("SQUARE", 10000, 2.0, 0, True),
    ("RAMP", 1000, 2.0, 0, True),
    ("PULSE", 1000, 2.0, 0, True),
    ("PULSE", 100, 2.0, 0, True),
    ("NOISE", 1000, 2.0, 0, False),
    ("DC", 1000, 0, 1.0, False),
    ("SINE", 1000, 0.2, 0, True),
    ("SINE", 1000, 5.0, 0, True),
    ("SINE", 1000, 2.0, 1.0, True),
    ("SINE", 1000, 2.0, -1.0, True),
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
        trig0 = scope.diagnose_trigger()
        print("初始触发状态:", trig0)
        for wave, freq, amp, ofst, freq_valid in CASES:
            tag = "%s@%gHz/%gVpp/off%g" % (wave, freq, amp, ofst)
            rec = {"case": tag}
            print("== %s ==" % tag)
            try:
                amp_arg = ("%gV" % amp) if amp else "0V"
                gen.set_basic_wave(
                    2, WVTP=wave, FRQ="%gHZ" % freq, AMP=amp_arg, OFST="%gV" % ofst
                )
                time.sleep(0.3)
                gen.set_output(2, True, gen.output_state(2).get("LOAD", "HZ"))
                time.sleep(1.0)

                scale = scope.auto_scale(4)
                rec["scale"] = scale.get("actions")
                rec["trig"] = scope.diagnose_trigger()

                meas_vpp = scope.measure_simple("PKPK", "C4")
                rec["vpp"] = meas_vpp
                rec["ok_v"] = (
                    abs(meas_vpp - (amp * 2 if wave == "DC" else amp))
                    / max(amp, 0.2) < 0.3
                    if amp else abs(meas_vpp) < 0.05
                )
                if freq_valid:
                    meas_freq = scope.measure_simple("FREQ", "C4")
                    rec["freq"] = meas_freq
                    rec["ok_f"] = abs(meas_freq - freq) / freq < 0.05
                else:
                    rec["ok_f"] = True
                verdict = "PASS" if (rec["ok_v"] and rec["ok_f"]) else "FAIL"
            except Exception as e:
                rec["error"] = "%s: %s" % (type(e).__name__, str(e)[:150])
                verdict = "ERROR"
            rec["verdict"] = verdict
            results.append(rec)
            print("   -> %s | vpp=%s freq=%s" % (verdict, rec.get("vpp"), rec.get("freq")))
    finally:
        print("-- 恢复 --")
        try:
            gen.set_output(2, False, gen.output_state(2).get("LOAD", "HZ"))
            print("   CH2:", gen.output_state(2).get("state"))
        except Exception as e:
            print("   恢复失败:", e)
        gen.close()
        scope.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / ("waveform_matrix_v2_" + stamp + ".json")
    f.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pass = sum(1 for r in results if r["verdict"] == "PASS")
    n_fail = sum(1 for r in results if r["verdict"] == "FAIL")
    print("\n== 结果: %d PASS / %d FAIL / %d ERROR (共%d) ==" % (
        n_pass, n_fail, len(results) - n_pass - n_fail, len(results)))
    print("留痕: %s" % f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
