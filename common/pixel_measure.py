"""像素级波形测量：从仪器截屏（BMP）直接算 Vpp / 频率 / 直流分量。

**为什么在产品里**：SDS800X HD 的高级测量引擎 `VALue?` 始终返回 `****`（疑似
选件限制），视觉通道是唯一可用的闭环测量手段。这套算法原先只活在
`TEST_SCRIPTS/common/pixel_measure.py` 里 —— 属于"测试里才有、产品里反而缺"的能力。

**纯函数，不碰设备**：输入是截屏字节 + 通道号 + 网格标定 + 当前档位，
输出是物理量。取档位、截屏由调用方负责（见 `sds_control.SDS`）。

    from common.pixel_measure import extract_trace, measure
    trace = extract_trace(sds.screenshot(), 4)
    r = measure(trace, vdiv=1.0, tdiv=1e-3)
    print(r["vpp"], r["freq_hz"])
"""
from __future__ import annotations

import struct
from collections import defaultdict
from typing import Mapping

# 通道颜色（RIGOL/Siglent 默认色板；容差见 `_TOL`）
CH_COLORS: dict[int, tuple[int, int, int]] = {
    1: (240, 240, 0),
    2: (0, 240, 240),
    3: (240, 80, 240),
    4: (32, 240, 32),
}
_TOL = 70

# 屏幕网格（SDS800X HD 1024x600 截屏；换机型请传 grid=）
GRID: dict[str, int] = {"x0": 20, "x1": 935, "y0": 48, "y1": 552, "divs": 10}


def extract_trace(data: bytes, ch: int, *,
                  grid: Mapping[str, int] = GRID,
                  tol: int = _TOL) -> dict[int, int]:
    """提取通道轨迹：每列取该颜色像素 Y 的中位数。返回 ``{col: y}``。

    支持 32 位 BMP（SDS 截屏格式）；`h_raw < 0` 表示自顶向下存储。
    """
    if ch not in CH_COLORS:
        raise ValueError(f"未知通道 {ch!r}，可选：{sorted(CH_COLORS)}")
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
        for c in range(grid["x0"], min(grid["x1"], w)):
            i = base + c * 4
            b, g, rr = data[i], data[i + 1], data[i + 2]
            if abs(rr - tr) < tol and abs(g - tg) < tol and abs(b - tb) < tol:
                disp_r = r if top_down else h - 1 - r
                if grid["y0"] <= disp_r <= grid["y1"]:
                    cols[c].append(disp_r)
    return {c: sorted(v)[len(v) // 2] for c, v in cols.items() if v}


def measure(trace: Mapping[int, int], *, vdiv: float, tdiv: float,
            ofst_v: float = 0.0, apply_offset: bool = False,
            grid: Mapping[str, int] = GRID,
            min_columns: int = 20) -> dict:
    """由轨迹算 Vpp / 频率 / 直流中心。

    ``tdiv`` 是时基档位（秒/格），``vdiv`` 是垂直档位（伏/格）。
    ``apply_offset`` 默认 **False**：`OFST?` 的单位与"网格中心对应 0 V"的
    假设没有实测对齐过，叠加会把结果推偏；保持与历史脚本一致。

    ``min_columns`` 不足时抛 `ValueError`（调用方按"无法测量"处理）。
    """
    if len(trace) < min_columns:
        raise ValueError(f"轨迹点不足（{len(trace)} 列 < {min_columns}）")

    grid_top, grid_bottom = grid["y0"], grid["y1"]
    mid_px = (grid_top + grid_bottom) / 2
    px_per_div = (grid_bottom - grid_top) / grid["divs"]
    off = ofst_v if apply_offset else 0.0

    def y_to_v(y: float) -> float:
        return (mid_px - y) / px_per_div * vdiv + off

    cols = sorted(trace)
    ys = [trace[c] for c in cols]

    # 过零估频：先按列滑动平均去噪（粗带中位数抖动会产生大量虚假过零）
    win = max(3, len(ys) // 50)
    smoothed = [
        sum(ys[max(0, i - win): i + win]) / len(ys[max(0, i - win): i + win])
        for i in range(len(ys))
    ]
    center = sum(smoothed) / len(smoothed)
    hysteresis_px = px_per_div * 0.05          # 迟滞带：中线 ±5% 格宽内不翻转
    crossings = 0
    prev_state = 0
    for y in smoothed:
        state = 1 if y < center - hysteresis_px else (-1 if y > center + hysteresis_px else 0)
        if state != 0 and prev_state != 0 and state != prev_state:
            crossings += 1
        if state != 0:
            prev_state = state

    span_s = (cols[-1] - cols[0]) * tdiv / grid["divs"]
    v_hi = y_to_v(min(ys))
    v_lo = y_to_v(max(ys))
    return {
        "columns": len(cols),
        "span_s": span_s,
        "v_hi": v_hi,
        "v_lo": v_lo,
        "vpp": v_hi - v_lo,
        "crossings": crossings,
        "freq_hz": crossings / (2 * span_s) if span_s > 0 else 0.0,
        "dc_v": y_to_v(center),
        "applied_ofst_v": off,
    }
