"""Emoe R&D EmoeCalibrator 校准器控制库（骨架版）。

⚠ 编程手册未提供：仅实现设备发现与 *IDN? 识别（已实测），业务命令
（输出/量程/设置）待手册到位后按手册逐条补充，禁止猜测。

实测环境（2026-08-24）：串口 ASRL31::INSTR，*IDN? =
'Emoe R&D,EmoeCalibrator,<serial>,<asset>'
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import discovery as cd
from common.visa_client import VisaClient

from . import commands as C


class EmoeCalibrator:
    """Emoe R&D 校准器控制封装（骨架：连接/识别/错误队列）。"""

    def __init__(
        self,
        resource: Optional[str] = None,
        timeout_ms: int = 5000,
    ):
        self.resource = resource
        self.timeout_ms = timeout_ms
        self.client: Optional[VisaClient] = None

    def connect(self, resource: Optional[str] = None) -> str:
        if self.client is not None:
            self.close()  # 二次连接先关旧会话，防泄漏
        if resource:
            self.resource = resource
        if not self.resource:
            self.resource = find_emoe()
        assert self.resource is not None
        self.client = VisaClient(self.resource, timeout_ms=self.timeout_ms)
        return self.resource

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def __enter__(self) -> "EmoeCalibrator":
        if self.client is None:
            self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- 底层 ----------
    def _c(self) -> VisaClient:
        if self.client is None:
            raise RuntimeError("未连接设备，请先 connect()")
        return self.client

    def query(self, cmd: str) -> str:
        return self._c().query(cmd)

    def write(self, cmd: str) -> None:
        self._c().write(cmd)

    # ---------- 已验证能力 ----------
    def idn(self) -> str:
        """*IDN? 设备标识（IEEE 488.2 四字段）。已实测 ✓"""
        return self.query(C.IDN)

    def system_error(self) -> Optional[str]:
        """:SYST:ERR? 错误队列（标准 SCPI 命令，存在性待确认——失败返回 None）。"""
        try:
            resp = self.query(C.SYST_ERR).strip()
            if resp.startswith("+0") or "No error" in resp:
                return None
            return resp
        except Exception:
            return None

    # ---------- 待手册补充 ----------
    # 业务命令（校准输出/量程/极性等）严禁猜测。
    # 手册到位后的开发流程见 AGENTS.md 一、SCPI 客户端铁律。


def find_emoe(timeout_ms: int = 1500) -> str:
    """扫描本机串口 + VISA 资源，返回 *IDN? 含 'EmoeCalibrator' 的资源地址。

    串口经**子进程**探测（驱动挂起即在硬超时后杀掉子进程）——本进程线程探测会留下
    卡死线程、此后任何 VISA 调用都会打死进程，见 `common/discovery.py::
    probe_serial_isolated` 的说明。被占用/无响应的口跳过并打印提示。
    非串口资源在本进程直接识别（open_timeout 可兜底）。未找到抛 RuntimeError。
    """
    candidates: list[str] = []
    try:
        resources = cd.list_resources()
    except Exception as e:
        raise RuntimeError(f"VISA 资源列举失败: {e}")
    for r in resources:
        up = r.upper()
        if up.startswith("ASRL") or "EMOE" in up or "INSTR" in up:
            candidates.append(r)

    serial = [r for r in candidates if r.upper().startswith("ASRL")]
    idn_of: dict[str, str] = {}
    note_of: dict[str, str] = {}
    if serial:
        for entry in cd.probe_serials_isolated(serial, timeout_ms):
            idn_of[entry["resource"]] = entry.get("idn") or ""
            note_of[entry["resource"]] = entry.get("note") or ""

    for r in candidates:
        if r.upper().startswith("ASRL"):
            idn, note = idn_of.get(r, ""), note_of.get(r, "")
        else:
            idn, note = cd.identify(r, timeout_ms) or "", ""
        if "EmoeCalibrator" in idn:
            print(f"[find_emoe] 命中 {r} -> {idn}", file=sys.stderr)
            return r
        print(f"[find_emoe] {r}: {idn or note or '无响应'}", file=sys.stderr)
    raise RuntimeError("未找到 *IDN? 含 'EmoeCalibrator' 的设备（检查串口接线/占用）")
