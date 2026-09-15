"""mho_control — RIGOL MHO900 系列（MHO934/MHO954/MHO984）数字示波器控制库。

实测基准机型：MHO984D（12bit / 4 通道 / 100Mpts）。命令来源见 `commands.py` 头部。

用法：
    from mho_control import MHO, find_mho

    with MHO(find_mho()) as scope:
        print(scope.idn())
        print(scope.measure_item("VPP", 1))
        wf = scope.get_waveform(1, points=1000)
        png = scope.screenshot_png(Path("shot.png"))

依赖：项目根在 sys.path（common 统一发现层 + VisaClient）。
"""
from .commands import (
    ACQ_DEPTHS,
    ACQ_TYPES,
    CHAN_COUPLINGS,
    DISP_FORMATS,
    EDGE_SLOPES,
    MEAS_ITEMS,
    MEAS_ITEMS_DUAL,
    MEAS_ITEMS_SINGLE,
    TRIG_STATES,
    TRIG_SWEEPS,
    TRIG_TYPES,
    WAV_FORMATS,
    WAV_MODES,
    WAV_SOURCES,
)
from rigol_scope import INVALID_MEASURE  # 哨兵值定义在共享内核（两系列同）
from .mho import MHO, find_mho, resolve_model

__all__ = [
    "ACQ_DEPTHS",
    "ACQ_TYPES",
    "CHAN_COUPLINGS",
    "DISP_FORMATS",
    "EDGE_SLOPES",
    "INVALID_MEASURE",
    "MEAS_ITEMS",
    "MEAS_ITEMS_DUAL",
    "MEAS_ITEMS_SINGLE",
    "MHO",
    "TRIG_STATES",
    "TRIG_SWEEPS",
    "TRIG_TYPES",
    "WAV_FORMATS",
    "WAV_MODES",
    "WAV_SOURCES",
    "find_mho",
    "resolve_model",
]
