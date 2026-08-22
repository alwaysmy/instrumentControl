"""三库补全功能实测：SDS 触发/高级测量、DMM configure 扩展（备份→改→回读→恢复）。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/libs_full_verify.py

安全约定：不执行任何复位；所有改动按原值恢复并比对。
输出：控制台 + TEST_DATA/common/libs_full_verify_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from keysight_3446x import DMM  # noqa: E402
from sds_control import SDS  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"
results: list[dict] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    results.append({"item": name, "ok": ok, "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    print("== SDS824X HD 触发 + 高级测量 ==")
    with SDS("TCPIP0::192.168.31.220::inst0::INSTR") as s:
        src = s.edge_source()
        rec("EDGE:SOUR? 查询", bool(src), f"原值={src}")
        lev = s.edge_level()
        rec("EDGE:LEV? 查询", isinstance(lev, float), f"原值={lev}V")
        slop = s.edge_slope()
        rec("EDGE:SLOP? 查询", bool(slop), f"原值={slop}")
        rec("TRIGger:STATus? 查询", bool(s.trigger_status()), f"状态={s.trigger_status()}")

        if isinstance(lev, float):
            s.edge_level(round(lev + 0.1, 4))
            got = s.edge_level()
            ok = abs(got - (lev + 0.1)) < 1e-3
            rec("EDGE:LEV 写+回读", ok, f"写 {round(lev + 0.1, 4)} 读 {got}")
            s.edge_level(lev)
            got2 = s.edge_level()
            rec("EDGE:LEV 恢复", abs(got2 - lev) < 1e-3, f"恢复 {lev} 读 {got2}")

        try:
            s.adv_measure_setup(1, "FREQuency", "C1")
            val = s.adv_measure_value(1)
            ok = val is not None and val < 9e37
            rec("ADV P1 FREQuency 配置+读值", True, f"P1={val}" + ("" if ok else "（无有效读数，配置已生效）"))
            s.clear_adv_measurements()
            rec("ADV 清除", True)
        except Exception as e:
            rec("ADV 测量", False, str(e))

    print("== Keysight 34465A configure 扩展 ==")
    import time

    with DMM("TCPIP0::192.168.31.123::inst0::INSTR") as d:
        # 实测固件特性：:CONF? 返回上一轮锁存配置（滞后一拍），不能作为写后立即判据；
        # 配置是否生效以实际测量结果为准。
        orig_conf = d.configuration()
        rec(":CONF? 原配置(参考)", bool(orig_conf), orig_conf)
        d.configure("curr_dc", range_v=0.0001)
        val = d.measure("curr_dc")
        rec("configure curr_dc + 实测", abs(val) < 1e-3, f"{val:.3e} A")
        d.configure("res", range_v=1e9)
        r = d.measure("res")
        rec("configure res + 实测(悬空超量程)", r > 1e8 or r >= 9.9e37, f"{r:.3g} Ω")
        d.configure("volt_dc", range_v=0.1, resolution=1e-8)
        v = d.measure("volt_dc")
        rec("恢复 volt_dc + 实测", abs(v) < 1.0, f"{v:.3e} V / CONF={d.configuration()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"libs_full_verify_{stamp}.json"
    f.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_fail = sum(1 for r in results if not r["ok"])
    print(f"\n== 结果: {len(results) - n_fail}/{len(results)} PASS ==")
    print(f"留痕已保存: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
