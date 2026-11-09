"""像素级波形测量（薄壳）：实现在 `common/pixel_measure.py`（产品侧）。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/pixel_measure.py [ch]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.pixel_measure import extract_trace, measure  # noqa: E402
from common.resolver import resolve                      # noqa: E402
from sds_control import SDS                              # noqa: E402
from sds_control.sds import _num                         # noqa: E402


def main() -> int:
    ch = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    # 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
    with SDS(resolve("sds")) as s:
        vdiv = _num(s.query(f"C{ch}:VDIV?"))
        ofst = _num(s.query(f"C{ch}:OFST?"))
        tdiv = s.timebase_scale()
        print(f"C{ch}: VDIV={vdiv}V OFST={ofst}V TDIV={tdiv}s")
        data = s.screenshot()

    trace = extract_trace(data, ch)
    try:
        r = measure(trace, vdiv=vdiv, tdiv=tdiv, ofst_v=ofst)
    except ValueError as e:
        print(f"{e}，无法测量")
        return 1

    print(f"轨迹覆盖 {r['columns']} 列 ({r['span_s']:.3e}s)")
    print(f">>> Vhi={r['v_hi']:+.3f}V  Vlo={r['v_lo']:+.3f}V  Vpp≈{r['vpp']:.3f}V")
    print(f">>> 过零估频 ≈ {r['freq_hz']:.1f} Hz  (上行+下行共 {r['crossings']} 次)")
    print(f">>> 直流中心 ≈ {r['dc_v']:+.3f} V")
    return 0


if __name__ == "__main__":
    sys.exit(main())
