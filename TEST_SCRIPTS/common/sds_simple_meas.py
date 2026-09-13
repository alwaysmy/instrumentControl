"""SDS SIMPle 测量组验证（正确语法：SOURce 与 ITEM 分离，每步查错队列）。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402
from sdg_control import SDG  # noqa: E402
from sds_control import SDS  # noqa: E402


def main() -> int:
    # 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
    gen = SDG(resolve("sdg"))
    scope = SDS(resolve("sds"))
    gen.connect()
    scope.connect()

    def drain(tag: str) -> None:
        n = 0
        while True:
            e = scope.query(":SYST:ERR?").strip()
            if e.startswith("+0") or "No error" in e:
                break
            n += 1
            print(f"  [{tag}] 队列: {e}")
            if n > 30:
                break
        if n == 0:
            print(f"  [{tag}] 错误队列干净")

    try:
        drain("初始")
        gen.set_output(2, True, gen.output_state(2).get("LOAD", "HZ"))
        time.sleep(0.3)
        for cmd in (
            ":MEASure:SIMPle:SOURce C4",
            ":MEASure:SIMPle:ITEM FREQ,ON",
            ":MEASure:SIMPle:ITEM PKPK,ON",
        ):
            scope.write(cmd)
            time.sleep(0.2)
            e = scope.query(":SYST:ERR?").strip()
            print(f"  {cmd} -> ERR: {e}")
        time.sleep(1.5)
        for q in (":MEASure:SIMPle:VALue? FREQ", ":MEASure:SIMPle:VALue? PKPK"):
            v = scope.query(q)
            print(f"  >>> {q} = {v}")
        drain("读值后")
    finally:
        gen.set_output(2, False, gen.output_state(2).get("LOAD", "HZ"))
        gen.close()
        scope.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
