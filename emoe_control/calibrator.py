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

    串口探测带驱动挂起硬超时（6s）；被占用/无响应的口跳过并打印提示。
    未找到抛 RuntimeError。
    """
    import pyvisa
    import threading

    candidates: list[str] = []
    try:
        rm = pyvisa.ResourceManager()
        try:
            resources = list(rm.list_resources())
        finally:
            rm.close()
    except Exception as e:
        raise RuntimeError(f"VISA 资源列举失败: {e}")
    for r in resources:
        up = r.upper()
        if up.startswith("ASRL") or "EMOE" in up or "INSTR" in up:
            candidates.append(r)

    seen: set[str] = set()
    for r in candidates:
        if r in seen:
            continue
        seen.add(r)
        result: dict = {}

        def work(r=r):
            rm2 = None
            try:
                rm2 = pyvisa.ResourceManager()
                inst = rm2.open_resource(
                    r,
                    open_timeout=2000,
                    read_termination="\n",
                    write_termination="\n",
                )
                inst.timeout = timeout_ms
                try:
                    idn = inst.query("*IDN?").strip()
                    if idn:
                        result["idn"] = idn
                finally:
                    inst.close()
            except Exception as e:
                code = getattr(e, "error_code", 0)
                if "BUSY" in str(e).upper() or code == -1073807346:
                    result["note"] = "被占用"
                else:
                    result["note"] = type(e).__name__
            finally:
                if rm2 is not None:
                    rm2.close()

        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(6.0)
        idn = result.get("idn", "")
        if "EmoeCalibrator" in idn:
            print(f"[find_emoe] 命中 {r} -> {idn}", file=sys.stderr)
            return r
        note = result.get("note", "")
        print(f"[find_emoe] {r}: {idn or note or '无响应'}", file=sys.stderr)
    raise RuntimeError("未找到 *IDN? 含 'EmoeCalibrator' 的设备（检查串口接线/占用）")
