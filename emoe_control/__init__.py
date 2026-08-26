"""emoe_control — Emoe R&D EmoeCalibrator 校准器控制库（骨架版）。

⚠ 编程手册未提供：仅含设备发现与 *IDN?（已实测）。业务命令待手册。
"""
from .calibrator import EmoeCalibrator, find_emoe

__all__ = ["EmoeCalibrator", "find_emoe"]
