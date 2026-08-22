"""跨设备生成+测量覆盖测试：SDG CH2 (SINE 1kHz/2V) → SDS CH4。

安全约定：
    - 全程备份→改→回读→恢复；不执行复位；
    - 结束时 SDG CH2 输出关闭、SDS 恢复原通道状态并清高级测量。
输出：控制台 + TEST_DATA/common/cross_test_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sdg_control import SDG  # noqa: E402
from sds_control import SDS  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"
results: list[dict] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    results.append({"item": name, "ok": ok, "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    gen = SDG("TCPIP0::192.168.31.206::inst0::INSTR")
    scope = SDS("TCPIP0::192.168.31.220::inst0::INSTR")
    gen.connect()
    scope.connect()
    try:
        _run_tests(gen, scope)
    finally:
        print("\n-- finally 恢复 --")
        try:
            gen.set_output(2, False)
            rec("finally: SDG CH2 输出关闭", gen.output_state(2).get("state") == "OFF")
        except Exception as e:
            rec("finally: SDG 恢复", False, str(e))
        try:
            scope.clear_adv_measurements()
            rec("finally: 清高级测量", True)
        except Exception as e:
            rec("finally: SDS 清测量", False, str(e))
        gen.close()
        scope.close()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"cross_test_{stamp}.json"
    f.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_fail = sum(1 for r in results if not r["ok"])
    print(f"\n== 结果: {len(results) - n_fail}/{len(results)} PASS ==")
    print(f"留痕已保存: {f}")
    return 1 if n_fail else 0


def _run_tests(gen: SDG, scope: SDS) -> None:
        # ---- 备份 ----
        ch2_bswv_backup = gen.basic_wave(2)
        ch2_out_backup = gen.output_state(2).get("state")
        c4_disp = scope.query("C4:TRA?").strip()
        c4_vdiv = scope.channel_scale(4)
        tdiv = scope.timebase_scale()
        rec("备份", True, f"CH2={ch2_out_backup} BSWV={ch2_bswv_backup.get('WVTP')}"
                          f"{ch2_bswv_backup.get('FRQ')} C4_disp={c4_disp} C4_VDIV={c4_vdiv}")

        # ---- 1. 生成：开 CH2 输出 ----
        gen.set_output(2, True)
        time.sleep(0.5)
        st = gen.output_state(2).get("state")
        rec("SDG CH2 输出 ON", st == "ON", f"state={st}")

        # ---- 2. 示波器配置 C4 ----
        scope.write("C4:TRA ON")
        scope.write("C4:VDIV 1V")          # 2Vpp → 2 格
        scope.write("TDIV 200e-6")         # 1ms 周期 → 屏幕约 5 周期
        time.sleep(1.0)                    # 等采集稳定
        rec("SDS C4 配置", True, f"VDIV={scope.channel_scale(4)} TDIV={scope.timebase_scale()}")

        # ---- 3. 测量：高级测量槽（配置后需等测量引擎就绪，'****' 时重试）----
        scope.adv_measure_setup(1, "FREQuency", "C4")
        scope.adv_measure_setup(2, "VPP", "C4")
        freq = vpp = None
        for attempt in range(4):
            time.sleep(1.5)
            freq = scope.adv_measure_value(1)
            vpp = scope.adv_measure_value(2)
            if freq is not None and vpp is not None:
                break
        rec("高级测量就绪", freq is not None and vpp is not None,
            f"尝试 {attempt + 1} 次: P1={freq} P2={vpp}")
        ok_f = freq is not None and abs(freq - 1000) / 1000 < 0.05
        ok_v = vpp is not None and abs(vpp - 2.0) / 2.0 < 0.15
        rec("测频率 ≈1kHz", ok_f, f"P1={freq}")
        rec("测VPP ≈2V", ok_v, f"P2={vpp}")

        # ---- 4. 波形读取交叉验证 ----
        # 已知问题：SDS800X HD 的 PREamble DESC 布局与手册示例偏移不符（读出全零），
        # 波形读取待专研该型号结构体；此处容错跳过不阻塞。
        try:
            wf = scope.get_waveform(4, points=2000)
            v_min, v_max = min(wf["v"]), max(wf["v"])
            wf_vpp = v_max - v_min
            crossings = sum(
                1 for i in range(1, len(wf["v"]))
                if wf["v"][i - 1] < 0 <= wf["v"][i]
            )
            span_s = wf["t"][-1] - wf["t"][0]
            est_freq = crossings / span_s if span_s > 0 else 0
            rec("波形 VPP 一致", abs(wf_vpp - (vpp or 0)) / max(vpp or 1, 1e-9) < 0.3,
                f"波形VPP={wf_vpp:.3f} vs 测量={vpp}")
            rec("波形过零估频 ≈1kHz", abs(est_freq - 1000) / 1000 < 0.1,
                f"估频={est_freq:.1f}Hz ({crossings} 次上行过零)")
        except Exception as e:
            rec("波形读取（SDS800X HD DESC 布局待专研）", False, f"{type(e).__name__}: {e}")

        # ---- 5. 变频联动 ----
        gen.set_basic_wave(2, FRQ="10000HZ")
        time.sleep(1.5)
        freq2 = scope.adv_measure_value(1)
        ok_f2 = freq2 is not None and abs((freq2 or 0) - 10000) / 10000 < 0.05
        rec("变频 10kHz 联动测量", ok_f2, f"P1={freq2}")
        gen.set_basic_wave(2, FRQ="1000HZ")
        time.sleep(1.0)

        # ---- 恢复 ----
        gen.set_output(2, False)
        rec("SDG CH2 输出关闭", gen.output_state(2).get("state") == "OFF")
        scope.clear_adv_measurements()
        scope.write(f"C4:TRA {'ON' if 'ON' in c4_disp.upper() else 'OFF'}")
        if isinstance(c4_vdiv, float):
            scope.write(f"C4:VDIV {c4_vdiv}V")
        scope.write(f"TDIV {tdiv}")
        rec("恢复 SDS C4/时基", True, f"C4_disp={scope.query('C4:TRA?').strip()}")


if __name__ == "__main__":
    sys.exit(main())
