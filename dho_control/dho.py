"""dho_control — RIGOL DHO800/DHO900 系列数字示波器控制库。

**2026-09-15 起与 mho_control 共用内核** `rigol_scope`（两系列命令集 97% 重合，
DHO 驱动原有 40 条命令 100% 存在于 MHO 手册，故并到同一实现；证据见
`docs/rigol_scope_compare_20260915.md`）。本文件只声明家族与型号解析。

合并后 DHO 侧的行为变化（都是**补齐**，且都依据 DHO 手册）：
    ① 修复 ASCII 波形死分支（旧版 `fmt.upper()` 后与混合大小写字面量比较，恒抛异常）；
    ② `get_waveform` 增加 points 上限（NORMal 1~1000）与 RAW 需 STOP 的前置校验；
    ③ 波形分片读取（RAW 大深度不再单帧几十 MB）；
    ④ 新增 `measure_clear()`（DHO 命令是 `:MEASure:CLEar`）、`screenshot()`/`screenshot_png()`
       （`:DISPlay:DATA?`，手册 3.9.7）、双信源测量项（RRDelay/RRPHase 等，DHO 手册同样记载）；
    ⑤ 删除 `reset()`（`:SYSTem:RESet`，属 AGENTS.md 禁发命令；需要复位走测试脚本+显式授权）。

⚠ **合并后尚未在 DHO 真机复验**：本实验台当前无 DHO（LAN 扫描只发现 MHO）。
离线闭环见 `TEST_SCRIPTS/common/verify_rigol_scope_shared.py`；
DHO 回到实验台后请补跑该库的真机验收（清单见该脚本头部注释）。

实测基准（合并前留痕）：DHO924S，LAN raw socket（`TCPIP0::<host>::5555::SOCKET`）。
命令来源：`docs/DHO800编程手册_output/`（418 页，与 DHO800_DHO900_ProgrammingGuide_CN.pdf 同一文档）。

用法不变：
    from dho_control import DHO, find_dho

    with DHO(find_dho()) as scope:
        print(scope.idn())
        vpp = scope.measure_item("VPP", 1)
        wf = scope.get_waveform(1)   # 屏幕波形 BYTE 格式 → 电压序列
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rigol_scope import DHO_FAMILY as _FAMILY, RigolScope, find_scope  # noqa: E402

Model = str


def resolve_model(model: Optional[Model]) -> str:
    """型号规范化：必须以 'DHO' 开头（DHO800/DHO900 全系列同命令集）。"""
    m = (model or "DHO").strip().upper()
    if not m.startswith("DHO"):
        raise ValueError(f"型号 {model!r} 不属于 DHO 系列（DHO800/DHO900）")
    return m


class DHO(RigolScope):
    """RIGOL DHO800/900 系列示波器（实现见 `rigol_scope.scope.RigolScope`）。"""

    FAMILY = _FAMILY


def find_dho(resource: Optional[str] = None, hosts: Optional[list[str]] = None,
             cidr: Optional[str] = None, allow_scan: bool = False,
             timeout_ms: int = 3000) -> str:
    """发现 *IDN? 含 'DHO' 的示波器，返回资源地址；未找到抛 RuntimeError。"""
    return find_scope(_FAMILY, resource=resource, hosts=hosts, cidr=cidr,
                      allow_scan=allow_scan, timeout_ms=timeout_ms)
