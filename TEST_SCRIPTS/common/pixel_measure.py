"""像素级波形测量：从截屏轨迹直接计算 Vpp / 频率 / 直流分量。

背景：SDS800X HD 高级测量引擎 VALue? 始终返回 '****'（疑似选件限制），
改用视觉通道闭环：BMP 像素 -> 波形重建 -> 物理量。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/pixel_measure.py [ch]
"""
from __future__ import annotations

import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve
from sds_control import SDS
from sds_control.sds import _num

CH_COLORS = {1: (240, 240, 0), 2: (0, 240, 240), 3: (240, 80, 240), 4: (32, 240, 32)}
GRID = {"x0": 20, "x1": 935, "y0": 48, "y1": 552, "divs": 10}


def extract_trace(data: bytes, ch: int) -> dict[int, int]:
    """提取通道轨迹：每列取该色像素的 Y 中位。返回 {col: y}。"""
    w = struct.unpack("<i", data[18:22])[0]
    h_raw = struct.unpack("<i", data[22:26])[0]
    top_down = h_raw < 0
    h = abs(h_raw)
    offset = struct.unpack("<I", data[10:14])[0]
    row_size = ((w * 4 + 3) // 4) * 4
    tr, tg, tb = CH_COLORS[ch]
    cols: dict[int, list[int]] = defaultdict(list)
    for r in range(h):
        base = offset + r * row_size
        for c in range(GRID["x0"], min(GRID["x1"], w)):
            i = base + c * 4
            b, g, rr = data[i], data[i + 1], data[i + 2]
            if abs(rr - tr) < 70 and abs(g - tg) < 70 and abs(b - tb) < 70:
                disp_r = r if top_down else h - 1 - r
                if GRID["y0"] <= disp_r <= GRID["y1"]:
                    cols[c].append(disp_r)
    return {c: sorted(v)[len(v) // 2] for c, v in cols.items() if v}


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
    if len(trace) < 20:
        print(f"轨迹点不足({len(trace)}列)，无法测量")
        return 1

    grid_top, grid_bottom = GRID["y0"], GRID["y1"]
    mid_px = (grid_top + grid_bottom) / 2
    px_per_div = (grid_bottom - grid_top) / GRID["divs"]

    ys = list(trace.values())
    y_max_v = max(trace.items(), key=lambda kv: kv[1])
    y_min_v = min(trace.items(), key=lambda kv: kv[1])

    def y_to_v(y: float) -> float:
        return (mid_px - y) / px_per_div * vdiv + ofst * 0

    v_hi = y_to_v(min(ys))
    v_lo = y_to_v(max(ys))
    vpp_px_based = v_hi - v_lo

    # 过零估频：先按列滑动平均去噪（轨迹粗带中位数抖动会产生大量虚假过零）
    cols = sorted(trace)
    ys_seq = [trace[c] for c in cols]
    win = max(3, len(ys_seq) // 50)
    smoothed = [
        sum(ys_seq[max(0, i - win) : i + win]) / len(ys_seq[max(0, i - win) : i + win])
        for i in range(len(ys_seq))
    ]
    center = sum(smoothed) / len(smoothed)
    hysteresis_px = px_per_div * 0.05  # 迟滞带：中线±5%格宽内不翻转
    crossings = 0
    prev_state = 0
    for y in smoothed:
        state = 1 if y < center - hysteresis_px else (-1 if y > center + hysteresis_px else 0)
        if state != 0 and prev_state != 0 and state != prev_state:
            crossings += 1
        if state != 0:
            prev_state = state
    span_s = (cols[-1] - cols[0]) * tdiv / GRID["divs"]
    freq_est = crossings / (2 * span_s) if span_s > 0 else 0.0

    dc = y_to_v(center)
    print(f"轨迹覆盖 {len(cols)} 列 ({span_s:.3e}s)")
    print(f">>> Vhi={v_hi:+.3f}V  Vlo={v_lo:+.3f}V  Vpp≈{vpp_px_based:.3f}V")
    print(f">>> 过零估频 ≈ {freq_est:.1f} Hz  (上行+下行共 {crossings} 次)")
    print(f">>> 直流中心 ≈ {dc:+.3f} V")
    return 0


if __name__ == "__main__":
    sys.exit(main())
