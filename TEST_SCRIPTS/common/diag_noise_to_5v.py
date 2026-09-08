"""复现 matrix NOISE->5V 序列，逐步查 SDG 错误队列与 AMP 回读。"""
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
    gen.set_output(2, True, gen.output_state(2).get("LOAD", "HZ"))
    time.sleep(0.3)

    print("-- NOISE case --")
    gen.set_basic_wave(2, WVTP="NOISE", FRQ="1000HZ", AMP="2V", OFST="0V")
    time.sleep(0.3)
    print("  SDG ERR:", gen.query(":SYST:ERR?").strip())
    print("  AMP 回读:", gen.basic_wave(2).get("AMP"))

    print("-- 切 5V SINE --")
    gen.set_basic_wave(2, WVTP="SINE", FRQ="1000HZ", AMP="5V", OFST="0V")
    time.sleep(0.3)
    print("  SDG ERR:", gen.query(":SYST:ERR?").strip())
    b = gen.basic_wave(2)
    print("  回读 WVTP=%s AMP=%s" % (b.get("WVTP"), b.get("AMP")))

    time.sleep(1.0)
    print("  SDS PKPK:", scope.query(":MEASure:SIMPle:VALue? PKPK"))
finally:
    gen.set_output(2, False, gen.output_state(2).get("LOAD", "HZ"))
    gen.close()
    scope.close()
