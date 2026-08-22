"""sdg_control — Siglent SDG 系列函数/任意波形发生器控制库（SDG2000X 基准）。"""
from .commands import BSWV_KEYS
from .sdg import SDG, find_sdg

__all__ = ["BSWV_KEYS", "SDG", "find_sdg"]
