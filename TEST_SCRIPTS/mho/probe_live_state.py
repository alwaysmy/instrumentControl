"""MHO 现场状态只读探针（不改任何设置）——用于"复现顶轨问题"前的现状核对。

跑法：
    python TEST_SCRIPTS/mho/probe_live_state.py
输出：连接到的资源串、触发/时基、各通道档位偏置探头比与**实测轨值**
（VTOP/VBASe/VMAX/VMIN/VPP/VAVG/FREQuency；无有效值即标出来）。
只查询 + 打开测量项（显示层面的变化），结束后清测量项。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402
from mho_control import MHO  # noqa: E402

res = resolve("mho")
print(f"resource: {res}")
with MHO(res) as s:
    print("idn:", s.idn())
    st = s.snapshot()
    for k, v in st.items():
        if k != "channels":
            print(f"  {k}: {v}")
    print("  通道状态：")
    for ch, c in st["channels"].items():
        print(f"    {ch}: {json.dumps(c, ensure_ascii=False)}")
    print("  实测轨值（无有效值即设备哨兵 9.9E37 → 这里标 None）：")
    for ch in range(1, 5):
        info = st["channels"].get(f"ch{ch}", {})
        if not info.get("display"):
            print(f"    ch{ch}: 显示 OFF —— 跳过（OFF 时本来也不采集）")
            continue
        row = {}
        for it in ("VTOP", "VBASe", "VMAX", "VMIN", "VPP", "VAVG", "FREQuency"):
            try:
                row[it] = round(s.measure_item(it, ch), 6)
            except ValueError:
                row[it] = None
        print(f"    ch{ch}: {json.dumps(row, ensure_ascii=False)}")
    s.measure_clear()
    print("已清测量项")
