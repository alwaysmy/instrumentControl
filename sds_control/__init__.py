"""sds_control — Siglent SDS 系列示波器控制库（SDS800X HD 基准）。"""
from .commands import PREAMBLE_OFFSETS, TDIV_ENUM
from .sds import SDS, find_sds

__all__ = ["PREAMBLE_OFFSETS", "SDS", "TDIV_ENUM", "find_sds"]
