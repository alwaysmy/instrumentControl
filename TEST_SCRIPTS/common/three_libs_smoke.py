"""三库只读冒烟：SDS824X HD / SDG2122X / 34465A（不改任何设备设置）。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/three_libs_smoke.py

输出：控制台 + TEST_DATA/common/three_libs_smoke_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from keysight_3446x import DMM  # noqa: E402
from sdg_control import SDG  # noqa: E402
from sds_control import SDS  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"


def main() -> int:
    out: dict = {"timestamp": datetime.now().isoformat(timespec="seconds")}

    print("== SDS824X HD ==")
    with SDS("TCPIP0::192.168.31.220::inst0::INSTR") as s:
        out["SDS"] = s.snapshot()
        print(f"  idn : {out['SDS']['idn']}")
        print(f"  ch1 : {out['SDS']['channels']['ch1']}")
        print(f"  时基 : {out['SDS']['timebase_scale_s_div']} s/div")

    print("== SDG2122X ==")
    with SDG("TCPIP0::192.168.31.206::inst0::INSTR") as g:
        out["SDG"] = {
            "idn": g.idn(),
            "ch1_bswv": g.basic_wave(1),
            "ch1_output": g.output_state(1),
            "error": g.system_error(),
        }
        print(f"  idn : {out['SDG']['idn']}")
        print(f"  ch1 BSWV: {out['SDG']['ch1_bswv']}")

    print("== Keysight 34465A ==")
    with DMM("TCPIP0::192.168.31.123::inst0::INSTR") as d:
        out["DMM"] = {
            "idn": d.idn(),
            "options": d.options(),
            "configuration": d.configuration(),
            "volt_dc": d.measure("volt_dc"),
            "last_reading": d.last_reading(),
        }
        print(f"  idn : {out['DMM']['idn']}")
        print(f"  VDC : {out['DMM']['volt_dc']:.6e} V")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"three_libs_smoke_{stamp}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"留痕已保存: {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
