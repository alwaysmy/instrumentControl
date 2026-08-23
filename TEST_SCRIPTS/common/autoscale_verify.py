"""auto_scale 端到端验证：SDG CH2 -> SDS C4，修触发+自动定标+测量闭环。"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sdg_control import SDG  # noqa: E402
from sds_control import SDS  # noqa: E402

gen = SDG("TCPIP0::192.168.31.206::inst0::INSTR")
scope = SDS("TCPIP0::192.168.31.220::inst0::INSTR")
gen.connect()
scope.connect()
try:
    gen.set_output(2, True)
    time.sleep(0.5)
    r = scope.auto_scale(4)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    vpp = scope.measure_simple("PKPK", "C4")
    freq = scope.measure_simple("FREQ", "C4")
    ok = abs(freq - 1000) / 1000 < 0.05 and abs(vpp - 2.0) / 2.0 < 0.2
    print(f"终测: Vpp={vpp:.3f}V Freq={freq:.1f}Hz -> {'PASS' if ok else 'FAIL'}")
finally:
    gen.set_output(2, False)
    gen.close()
    scope.close()
