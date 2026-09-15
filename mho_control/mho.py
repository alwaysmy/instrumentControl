"""mho_control — RIGOL MHO900 系列（MHO934/MHO954/MHO984）数字示波器控制库。

**2026-09-15 起与 dho_control 共用内核** `rigol_scope`（两系列命令集 97% 重合，
证据见 `docs/rigol_scope_compare_20260915.md`）；本文件只声明家族与型号解析，
其余实现（波形/测量/截屏/快照/校验）在内核里——**修一处两系列同时受益**。

实测基准：MHO984D（`RIGOL TECHNOLOGIES,MHO984D,MHO9B282003181,00.01.00`），
本系列 4 通道 12bit，1~2ch 4GSa/s / 3~4ch 1GSa/s，标准深度 100Mpts。
命令来源：`docs/MHO900编程手册_output/`（480 页提取版）。

复位族（`:SYSTem:RESet` 重启 / `*RST` 恢复出厂）**不在公开 API 里**——
常量与语义说明见 `commands.py`，受控入口 `TEST_SCRIPTS/common/rigol_scope_reset.py --allow-reset`。

用法：
    from mho_control import MHO, find_mho

    with MHO(find_mho()) as scope:
        print(scope.idn())
        vpp = scope.measure_item("VPP", 1)
        wf  = scope.get_waveform(1, points=1000)       # 屏幕波形 → 电压/时间序列
        png = scope.screenshot_png(Path("shot.png"))   # 原生 PNG，无需转码
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rigol_scope import MHO_FAMILY as _FAMILY, RigolScope, find_scope  # noqa: E402

Model = str


def resolve_model(model: Optional[Model]) -> str:
    """型号规范化：必须以 'MHO' 开头（MHO900 系列同命令集）。"""
    m = (model or "MHO").strip().upper()
    if not m.startswith("MHO"):
        raise ValueError(f"型号 {model!r} 不属于 MHO900 系列（MHO934/MHO954/MHO984）")
    return m


class MHO(RigolScope):
    """RIGOL MHO900 系列示波器（实现见 `rigol_scope.scope.RigolScope`）。"""

    FAMILY = _FAMILY


def find_mho(resource: Optional[str] = None, hosts: Optional[list[str]] = None,
             cidr: Optional[str] = None, allow_scan: bool = False,
             timeout_ms: int = 3000) -> str:
    """发现 *IDN? 含 'MHO' 的示波器，返回资源地址；未找到抛 RuntimeError。"""
    return find_scope(_FAMILY, resource=resource, hosts=hosts, cidr=cidr,
                      allow_scan=allow_scan, timeout_ms=timeout_ms)
