"""单步复现 SQUARE 测量失败：全程诊断触发/错误队列/截图。"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sdg_control import SDG  # noqa: E402
from sds_control import SDS  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"

gen = SDG("TCPIP0::192.168.31.206::inst0::INSTR")
scope = SDS("TCPIP0::192.168.31.220::inst0::INSTR")
gen.connect()
scope.connect()
try:
    gen.set_basic_wave(2, WVTP="SQUARE", FRQ="1000HZ", AMP="2V", OFST="0V")
    time.sleep(0.3)
    print("SDG 设置后 ERR:", scope.query(":SYST:ERR?").strip())
    gen.set_output(2, True, gen.output_state(2).get("LOAD", "HZ"))
    time.sleep(1.0)

    diag = scope.diagnose_trigger()
    print("触发(改前):", diag)

    scale = scope.auto_scale(4)
    print("auto_scale:", json.dumps(scale, ensure_ascii=False))

    time.sleep(2)
    diag2 = scope.diagnose_trigger()
    print("触发(测前):", diag2)

    for item in ("PKPK", "FREQ", "PER", "PWID"):
        v = scope.query(":MEASure:SIMPle:VALue? " + item)
        print("VAL %s -> %s" % (item, v))
    e = scope.query(":SYST:ERR?").strip()
    print("ERR:", e)

    stamp = time.strftime("%H%M%S")
    png = OUT_DIR / ("sds_square_" + stamp + ".png")
    scope.screenshot_png(png)
    print("截图:", png)
finally:
    gen.set_output(2, False, gen.output_state(2).get("LOAD", "HZ"))
    gen.close()
    scope.close()
