"""OFST+1V FAIL case 截图诊断：verbose auto_scale + 前后截图对比。"""
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
stamp = datetime.now().strftime("%H%M%S")

# 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
gen = SDG(resolve("sdg"))
scope = SDS(resolve("sds"))
gen.connect()
scope.connect()
try:
    gen.set_basic_wave(2, WVTP="SINE", FRQ="1000HZ", AMP="2V", OFST="1V")
    gen.set_output(2, True, gen.output_state(2).get("LOAD", "HZ"))
    time.sleep(1.5)
    print("SDG 回读:", {k: gen.basic_wave(2).get(k) for k in ("WVTP", "FRQ", "AMP", "OFST")})

    # auto_scale 前截图
    p0 = OUT_DIR / f"ofst_before_{stamp}.png"
    scope.screenshot_png(p0)
    print("前截图:", p0)
    print("定标前:", scope.diagnose_trigger())

    r = scope.auto_scale(4, verbose=True)
    print(json.dumps(r, ensure_ascii=False, indent=1))

    time.sleep(1.5)
    p1 = OUT_DIR / f"ofst_after_{stamp}.png"
    scope.screenshot_png(p1)
    print("后截图:", p1)
    print("终态诊断:", scope.diagnose_trigger())
    print("PKPK:", scope.query(":MEASure:SIMPle:VALue? PKPK"))
    print("MAX :", scope.query(":MEASure:SIMPle:VALue? MAX"))
    print("MIN :", scope.query(":MEASure:SIMPle:VALue? MIN"))
    print("OFST:", scope.query("C4:OFST?"), " VDIV:", scope.query("C4:VDIV?"))
finally:
    gen.set_output(2, False, gen.output_state(2).get("LOAD", "HZ"))
    gen.close()
    scope.close()
