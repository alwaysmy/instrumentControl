"""dho_control — RIGOL DHO 系列数字示波器控制库（DHO800/DHO900 系列）。

用法：
    from dho_control import DHO, find_dho

    with DHO(find_dho()) as scope:
        print(scope.idn())
        print(scope.measure_item("VPP", 1))
        wf = scope.get_waveform(1)

依赖：项目根在 sys.path（common 统一发现层 + VisaClient）。
"""
from .commands import ACQ_DEPTHS, MEAS_ITEMS, WAV_SOURCES
from .dho import DHO, find_dho, resolve_model

__all__ = [
    "ACQ_DEPTHS",
    "DHO",
    "MEAS_ITEMS",
    "WAV_SOURCES",
    "find_dho",
    "resolve_model",
]
