"""Siglent SDG 系列（SDG2000X 基准）函数/任意波形发生器控制库。

实测基准：SDG2122X（VXI-11 inst0）。输出类写操作会真实开关信号，调用方自担安全责任。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.discovery import find_device, identify, list_resources, scan  # noqa: F401
from common.visa_client import VisaClient

from . import commands as C


class SDG:
    """Siglent SDG 系列信号源控制封装。"""

    def __init__(
        self,
        resource: Optional[str] = None,
        model: str = "SDG",
        timeout_ms: int = 8000,
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

    def __enter__(self) -> "SDG":
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
        return self.query("*IDN?")

    def system_error(self) -> Optional[str]:
        resp = self.query(C.SYST_ERR)
        return resp or None

    def version(self) -> str:
        return self.query(C.SYST_VERS)

    # ---------- 通道 ----------
    @staticmethod
    def _ch(ch: int | str) -> str:
        s = f"C{int(ch)}" if isinstance(ch, int) else str(ch).upper()
        if s not in ("C1", "C2"):
            raise ValueError(f"invalid channel: {ch!r}")
        return s

    def output_state(self, ch: int | str) -> dict:
        """:OUTP? 响应键值串 → dict（含 LOAD/PLRT/POWERON_STATE 等）。"""
        raw = self.query(f"{C.OUTP_Q.format(ch=self._ch(ch))}").strip()
        parts = raw.split(" ", 1)
        out: dict = {"raw": raw}
        if len(parts) == 2:
            tokens = parts[1].split(",")
            out["state"] = tokens[0]
            for i in range(1, len(tokens) - 1, 2):
                out[tokens[i].strip(",")] = tokens[i + 1]
        return out

    def _check_load(self, ch: int | str, expect_load: str) -> str:
        """负载设置校验（防幅度误判）：声明值与实际不符时抛错并回传实际值。

        仅校验不设置——SDG 的 AMP 设定值与负载强相关（HZ 高阻下即 Vpp，
        50Ω 下实际幅度减半），输出开关前必须声明当前负载避免误判。
        """
        st = self.output_state(ch)
        actual = str(st.get("LOAD", "")).strip().upper()
        claimed = str(expect_load).strip().upper()
        if claimed != actual:
            raise RuntimeError(
                f"负载设置校验失败：声明 {claimed}，实际 {actual}。"
                f"请先 output_state(ch) 确认当前 LOAD（HZ=高阻 / 50=50Ω）后重试"
            )
        return actual

    def set_output(self, ch: int | str, on: bool, expect_load: str) -> None:
        """⚠ 开关通道输出（真实信号变化）。

        expect_load（必填）：调用方声明的当前负载设置（HZ 高阻 / 50 欧），
        仅校验不设置；与实际不符立即拒绝并回传实际值（防幅度误判）。
        """
        self._check_load(ch, expect_load)
        self.write(f"{C.OUTP_W.format(ch=self._ch(ch), state='ON' if on else 'OFF')}")

    def basic_wave(self, ch: int | str) -> dict:
        """:BSWV? 基础波形参数整体查询，解析为 {WVTP:SINE, FRQ:'1000HZ', ...}。"""
        raw = self.query(f"{C.BSWV_Q.format(ch=self._ch(ch))}").strip()
        parts = raw.split(" ", 1)
        out: dict = {}
        if len(parts) == 2:
            tokens = parts[1].split(",")
            for i in range(0, len(tokens) - 1, 2):
                out[tokens[i]] = tokens[i + 1]
        return out

    def set_basic_wave(self, ch: int | str, **params) -> None:
        """:BSWV 键值对设置。例：set_basic_wave(1, WVTP="SINE", FRQ="2000HZ", AMP="1.5V")。
        ⚠ 改变输出参数（若输出开启则实时生效）。"""
        kv = ",".join(f"{k},{v}" for k, v in params.items())
        self.write(f"{C.BSWV_W.format(ch=self._ch(ch), params=kv)}")

    def mod_wave(self, ch: int | str) -> dict:
        """:MDWV? 调制参数查询（STATE/TYPE/SRC 等）。"""
        return self._kv_query(f"{C.MDWV_Q.format(ch=self._ch(ch))}")

    def sweep_wave(self, ch: int | str) -> dict:
        """:SWWV? 扫频参数查询（STATE/START/STOP/TIME 等）。"""
        return self._kv_query(f"{C.SWWV_Q.format(ch=self._ch(ch))}")

    def arb_wave(self, ch: int | str) -> dict:
        """:ARWV? 任意波参数查询（索引/文件名）。"""
        return self._kv_query(f"{C.ARWV_Q.format(ch=self._ch(ch))}")

    def _kv_query(self, cmd: str) -> dict:
        """通用键值串解析："C1:XXX A,B,C,D" → {A:B, C:D}。"""
        raw = self.query(cmd).strip()
        parts = raw.split(" ", 1)
        out: dict = {"raw": raw}
        if len(parts) == 2:
            tokens = parts[1].split(",")
            for i in range(0, len(tokens) - 1, 2):
                out[tokens[i]] = tokens[i + 1]
        return out

    # ---------- 快照 ----------
    def snapshot(self) -> dict:
        return {
            "idn": self.idn(),
            "version": self.version(),
            "error": self.system_error(),
            "ch1_output": self.output_state(1),
            "ch2_output": self.output_state(2),
            "ch1_basic_wave": self.basic_wave(1),
            "ch2_basic_wave": self.basic_wave(2),
            "ch1_mod": self.mod_wave(1),
            "ch2_mod": self.mod_wave(2),
        }


def find_sdg(
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    cidr: Optional[str] = None,
    allow_scan: bool = False,
    timeout_ms: int = 3000,
) -> str:
    hit = find_device(
        "SDG",
        resource=resource,
        hosts=hosts,
        allow_scan=allow_scan,
        cidr=cidr,
        timeout_ms=timeout_ms,
    )
    return hit.resource
