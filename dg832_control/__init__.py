"""dg832_control — RIGOL DG800 系列（DG832 基准）函数/任意波形发生器控制库。

**单一来源**：驱动器本体 `dg832.py` 自 2026-09-15 起以本仓为唯一维护点
（原 `D:\\ChatWorkspace\\DG832使用\\` 与 skill 内的两份副本已退役、不再单独维护；
三份曾逐字节相同，md5 `d1e33622…`，迁移时按原样复制未改一行）。

实测基准：DG832（双通道 35 MHz / 125 MSa/s / 16 bit），USB-TMC
`USB0::0x1AB1::0x0643::<serial>::INSTR`，固件 00.02.06.00.01。

依赖：**完整版 NI-VISA ≥ 24.x**（Ultra Sigma 自带的旧版 IVI visa 3.2 会卡死）+ pyvisa。
手册与笔记见 `docs/`（`02_编程手册.txt` 是本库命令出处的审计参照物）。

用法：
    from dg832_control import DG832, discover

    with DG832() as gen:          # 资源串缺省时自动发现
        print(gen.idn())
        gen.set_voltage_limit(1, high=3.3, low=-3.3, state=True)   # 保护先行
        gen.set_wave(1, "sine", freq=1000, amp=2.0, offset=0.0)
        gen.output(1, True)
"""
from .dg832 import (
    DEFAULT_MODEL,
    MODEL_REGISTRY,
    ConnectionError_,
    DG832,
    DgError,
    ModelUnsupportedError,
    ParamValidationError,
    ProtectRangeError,
    ProtectRequiredError,
    discover,
    resolve_model,
)

__all__ = [
    "DEFAULT_MODEL",
    "MODEL_REGISTRY",
    "ConnectionError_",
    "DG832",
    "DgError",
    "ModelUnsupportedError",
    "ParamValidationError",
    "ProtectRangeError",
    "ProtectRequiredError",
    "discover",
    "resolve_model",
]
