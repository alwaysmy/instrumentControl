"""Keysight Truevolt 系列（34461A/34465A/34470A）六位半万用表控制库。

实测基准：34465A（VXI-11 inst0）。标准 Keysight SCPI，手册见 docs/。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.discovery import find_device, identify, list_resources, scan  # noqa: F401
from common.visa_client import VisaClient

from . import commands as C


def _num(text: str) -> float:
    """从带单位后缀的响应中提取数值（如 '-5.23E-05  VDC' → -5.23e-5）。"""
    m = re.search(r"[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?", text)
    if m is None:
        raise ValueError(f"无数字可解析: {text!r}")
    return float(m.group().replace("D", "E").replace("d", "e"))

FUNCTIONS = {
    "volt_dc": C.MEAS_VOLT_DC,
    "volt_ac": C.MEAS_VOLT_AC,
    "curr_dc": C.MEAS_CURR_DC,
    "curr_ac": C.MEAS_CURR_AC,
    "res": C.MEAS_RES,
    "fres": C.MEAS_FRES,
    "cont": C.MEAS_CONT,
    "cap": C.MEAS_CAP,
    "diod": C.MEAS_DIOD,
    "freq": C.MEAS_FREQ,
}


class DMM:
    """Keysight Truevolt 系列万用表控制封装。"""

    def __init__(
        self,
        resource: Optional[str] = None,
        model: str = "3446",          # *IDN? 含 34460A/34461A/34465A/34470A
        timeout_ms: int = 10000,
        hosts: Optional[list[str]] = None,
        cidr: Optional[str] = None,
        allow_scan: bool = False,
    ):
        self.model = model
        self.resource = resource
        self.timeout_ms = timeout_ms
        self.hosts = list(hosts) if hosts else []
        self.cidr = cidr
        self.allow_scan = allow_scan
        self.client: Optional[VisaClient] = None

    def connect(self, resource: Optional[str] = None) -> str:
        if resource:
            self.resource = resource
        if not self.resource:
            hit = find_device(
                self.model,
                hosts=self.hosts or None,
                allow_scan=self.allow_scan,
                cidr=self.cidr,
                timeout_ms=min(self.timeout_ms, 5000),
            )
            self.resource = hit.resource
        assert self.resource is not None
        self.client = VisaClient(self.resource, timeout_ms=self.timeout_ms)
        return self.resource

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def __enter__(self) -> "DMM":
        if self.client is None:
            self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _c(self) -> VisaClient:
        if self.client is None:
            raise RuntimeError("未连接设备，请先 connect()")
        return self.client

    def query(self, cmd: str) -> str:
        return self._c().query(cmd)

    def write(self, cmd: str) -> None:
        self._c().write(cmd)

    # ---------- 信息 ----------
    def idn(self) -> str:
        return self.query(C.IDN)

    def options(self) -> str:
        """*OPT? 选件（BOC/TEMP 等，无选件为 '0,0,0,0,0'）。"""
        return self.query(C.OPT)

    def system_error(self) -> Optional[str]:
        resp = self.query(C.SYST_ERR)
        return resp if resp and not resp.startswith("+0") else None

    # ---------- 测量 ----------
    def measure(self, function: str) -> float:
        """单次测量。function 见 keysight_3446x.commands.FUNCTIONS 键名。

        连续性/二极管返回欧姆或伏特原始值（连续性短接 ≈ <10Ω）。
        """
        cmd = FUNCTIONS.get(function)
        if cmd is None:
            raise ValueError(f"未知功能 {function!r}，可用: {', '.join(FUNCTIONS)}")
        return float(self.query(cmd))

    def read(self) -> float:
        """:READ? 按当前 :CONF 功能测量一次。"""
        return _num(self.query(C.READ))

    def last_reading(self) -> float:
        """:DATA:LAST? 取最近读数，不触发新测量（响应可能带 'VDC' 等单位后缀）。"""
        return _num(self.query(C.DATA_LAST))

    # ---------- 配置 ----------
    def configure(self, function: str, range_v: Optional[float] = None,
                  resolution: Optional[float] = None) -> None:
        """:CONF 设定测量功能/量程/分辨率（不触发测量）。"""
        base = {
            "volt_dc": "VOLT:DC", "volt_ac": "VOLT:AC",
            "curr_dc": "CURR:DC", "curr_ac": "CURR:AC",
            "res": "RES", "fres": "FRES",
            "cap": "CAP", "freq": "FREQ",
        }.get(function)
        if base is None:
            raise ValueError(f"configure 暂不支持 {function!r}，可用: volt_dc/volt_ac/"
                             f"curr_dc/curr_ac/res/fres/cap/freq")
        cmd = f":CONF {base}"
        if range_v is not None:
            cmd += f" {range_v}"
        if resolution is not None:
            cmd += f",{resolution}"
        self.write(cmd)

    def configuration(self) -> str:
        return self.query(C.CONF_Q)

    def set_nplc(self, nplc: float) -> None:
        """电压 DC 积分时间（PLC 倍数，0.02~100；越大越慢越准）。"""
        self.write(f"{C.SENS_VOLT_NPLC} {nplc}")

    def get_nplc(self) -> float:
        return float(self.query(C.SENS_VOLT_NPLC + "?"))

    # ---------- 快照 ----------
    def snapshot(self) -> dict:
        return {
            "idn": self.idn(),
            "options": self.options(),
            "error": self.system_error(),
            "configuration": self.configuration(),
            "last_reading": self.last_reading(),
        }


def find_dmm(
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    cidr: Optional[str] = None,
    allow_scan: bool = False,
    timeout_ms: int = 3000,
) -> str:
    hit = find_device(
        "3446",
        resource=resource,
        hosts=hosts,
        allow_scan=allow_scan,
        cidr=cidr,
        timeout_ms=timeout_ms,
    )
    return hit.resource
