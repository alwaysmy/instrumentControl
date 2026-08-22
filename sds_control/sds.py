"""Siglent SDS 系列（SDS800X HD 基准）示波器控制库。

实测基准：SDS824X HD（VXI-11 inst0）。命令来源见 commands.py 头部。
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.discovery import find_device, identify, list_resources, scan  # noqa: F401
from common.visa_client import VisaClient

from . import commands as C


def _num(text: str) -> float:
    """从带单位后缀的响应中提取数值（如 '2.00E-03S' → 2e-3；'C1:ATTN 10' 由调用方先剥离）。"""
    m = re.search(r"[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?", text)
    if m is None:
        raise ValueError(f"无数字可解析: {text!r}")
    return float(m.group().replace("D", "E").replace("d", "e"))


class SDS:
    """Siglent SDS 系列示波器控制封装。"""

    def __init__(
        self,
        resource: Optional[str] = None,
        model: str = "SDS",
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

    def __enter__(self) -> "SDS":
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
        resp = self._c().query(cmd).strip()
        # SDS 多数查询响应带回显头（如发 "C1:VDIV?" 收 "C1:VDIV 5.00E+00V"）；
        # 仅当响应以命令头部开头时才剥离，避免误伤 *IDN? 等无回显响应。
        cmd_head = cmd.lstrip(":").split(" ")[0].split("?")[0]
        if " " in resp and resp.upper().startswith(cmd_head.upper()):
            return resp.split(" ", 1)[1].strip()
        return resp

    def write(self, cmd: str) -> None:
        self._c().write(cmd)

    def query_raw(self, cmd: str) -> bytes:
        return self._c().inst.query_raw(cmd)

    # ---------- 信息 ----------
    def idn(self) -> str:
        return self.query("*IDN?")

    def system_error(self) -> Optional[str]:
        resp = self.query(C.SYST_ERR)
        return resp or None

    def run(self) -> None:
        self.write(C.RUN)

    def stop(self) -> None:
        self.write(C.STOP)

    def autoset(self) -> None:
        self.write(C.AUTOSET)

    # ---------- 通道 ----------
    def _ch(self, ch: int) -> int:
        n = int(ch)
        if n not in (1, 2, 3, 4):
            raise ValueError(f"invalid channel: {ch!r}")
        return n

    def channel_scale(self, ch: int, scale_v: Optional[float] = None) -> Optional[float]:
        n = self._ch(ch)
        if scale_v is None:
            return _num(self.query(f"C{n}:VDIV?"))
        self.write(f"C{n}:VDIV {scale_v}V")
        return None

    def channel_offset(self, ch: int, offset_v: Optional[float] = None) -> Optional[float]:
        n = self._ch(ch)
        if offset_v is None:
            return _num(self.query(f"C{n}:OFST?"))
        self.write(f"C{n}:OFST {offset_v}V")
        return None

    def channel_attenuation(self, ch: int) -> float:
        """探头衰减比（响应如 'C1:ATTN 10' → 10.0；D1M 表示 1M:1 数字探针）。"""
        raw = self.query(f"C{self._ch(ch)}:ATTN?")
        try:
            return float(raw)
        except ValueError:
            return float(raw.replace("D", "E")) if "D" in raw else float(raw.rstrip("M") or 0)

    def channel_coupling(self, ch: int, coupling: Optional[str] = None) -> Optional[str]:
        n = self._ch(ch)
        if coupling is None:
            raw = self.query(f"C{n}:COUPLING?").strip()
            # 响应头为缩写形式（发 COUPLING? 收 "C1:CPL D1M"），手动剥离
            if raw.upper().startswith("C") and " " in raw[:10]:
                return raw.split(" ", 1)[1].strip()
            return raw
        self.write(f"C{n}:COUPLING {coupling.upper()}")
        return None

    # ---------- 时基/触发 ----------
    def timebase_scale(self) -> float:
        return _num(self.query(C.TB_SCALE))

    def trigger_delay(self) -> float:
        return _num(self.query(C.TRIG_DELAY))

    def trigger_mode(self) -> str:
        return self.query(C.TRIG_MODE).strip()

    def trigger_status(self) -> str:
        return self.query(C.TRIG_STATUS).strip()

    def edge_source(self, source: Optional[str] = None) -> Optional[str]:
        if source is None:
            return self.query(C.TRIG_EDGE_SOUR).strip()
        self.write(C.TRIG_EDGE_SOUR_W.format(src=source.upper()))
        return None

    def edge_level(self, level: Optional[float] = None) -> Optional[float]:
        if level is None:
            return _num(self.query(C.TRIG_EDGE_LEV))
        self.write(C.TRIG_EDGE_LEV_W.format(val=level))
        return None

    def edge_slope(self, slope: Optional[str] = None) -> Optional[str]:
        if slope is None:
            return self.query(C.TRIG_EDGE_SLOP).strip()
        self.write(f"TRIG:EDGE:SLOP {slope}")
        return None

    # ---------- 采集 ----------
    def acquire_depth(self, value: Optional[str] = None) -> Optional[str]:
        if value is None:
            return self.query(C.ACQ_MDEP).strip()
        self.write(f"{C.ACQ_MDEP} {value}")
        return None

    def sample_rate(self) -> float:
        return _num(self.query(C.ACQ_SRAT))

    # ---------- 测量 ----------
    def measure_summary(self) -> dict:
        """:MEAS? 返回当前已打开测量项的统计值串，原样解析为键值对。"""
        raw = self.query(C.MEAS_ALL)
        out: dict = {}
        for token in raw.split(","):
            k, _, v = token.partition(":")
            k = k.strip()
            if k:
                out[k] = v.strip()
        return out

    MEAS_TYPES = (
        "VPP", "VMAX", "VMIN", "VAMP", "VTOP", "VBASE", "PERiod",
        "FREQuency", "RISetime", "FALLtime", "PWIDth", "NWIDth", "DUTy",
    )

    def adv_measure_setup(self, slot: int, mtype: str, src: str = "C1") -> None:
        """配置高级测量槽 P<n>（TYPE + 信源）。slot 1~8，mtype 见 MEAS_TYPES。"""
        if not (1 <= int(slot) <= 8):
            raise ValueError(f"invalid slot: {slot}")
        if mtype not in self.MEAS_TYPES:
            raise ValueError(f"未知测量类型 {mtype!r}，可用: {', '.join(self.MEAS_TYPES)}")
        self.write(f":MEASure:ADVanced:P{int(slot)}:SOURce1 {src.upper()}")
        self.write(f":MEASure:ADVanced:P{int(slot)}:TYPE {mtype}")

    def adv_measure_value(self, slot: int) -> Optional[float]:
        """读取高级测量槽 P<n> 当前值；'****'(无有效读数) 返回 None，
        9.9E37(超界) 原样返回由调用方判断。"""
        raw = self.query(C.MEAS_ADV_VAL.format(n=int(slot))).strip()
        try:
            return _num(raw)
        except ValueError:
            return None

    def clear_adv_measurements(self) -> None:
        self.write(C.MEAS_ADV_CLEAR)

    # ---------- 波形读取 ----------
    @staticmethod
    def _strip_tmc(data: bytes) -> bytes:
        idx = data.find(b"#")
        ndigits = int(data[idx + 1 : idx + 2])
        length = int(data[idx + 2 : idx + 2 + ndigits])
        body = data[idx + 2 + ndigits :]
        if len(body) < length:
            raise ValueError(f"TMC 数据不完整: 期望 {length}，实得 {len(body)}")
        return body[:length]

    def _preamble(self, src: str) -> dict:
        raw = self._strip_tmc(self.query_raw(C.WAV_PREAMBLE))
        out: dict = {}
        for key, (off, fmt) in C.PREAMBLE_OFFSETS.items():
            size = {"h": 2, "i": 4, "f": 4, "d": 8}[fmt]
            chunk = raw[off : off + size]
            out[key] = struct.unpack("<" + fmt, chunk)[0]
        out["tdiv"] = C.TDIV_ENUM[out["tdiv"]]
        out["vdiv"] *= out["probe"]
        out["offset"] *= out["probe"]
        return out

    def get_waveform(self, src: Union[int, str] = 1, points: Optional[int] = None) -> dict:
        """读取模拟通道波形并换算物理量（分片读取，官方协议）。

        电压 = raw/code*vdiv - offset；时间 = -(tdiv*10/2) + i*interval + delay。
        """
        source = f"C{int(src)}" if isinstance(src, int) else str(src).upper()
        self.write(f"{C.WAV_SOUR} {source}")
        pre = self._preamble(source)
        total = pre["point_num"]
        max_pts = int(float(self.query(C.WAV_MAXPOINT)))
        width = "WORD" if pre["adc_bit"] > 8 else "BYTE"
        self.write(f"{C.WAV_WIDTH} {width}")
        if points is not None:
            total = min(points, total)
            self.write(f"{C.WAV_POINTS} {total}")

        chunks: list[bytes] = []
        start = 0
        while start < total:
            n = min(max_pts, total - start)
            self.write(f"{C.WAV_START} {start}")
            chunks.append(self._strip_tmc(self.query_raw(C.WAV_DATA)))
            start += n
        blob = b"".join(chunks)[:total * (2 if width == "WORD" else 1)]

        if width == "WORD":
            codes = struct.unpack(f"<{len(blob)//2}h", blob)
        else:
            codes = struct.unpack(f"<{len(blob)}b", blob)
        volts = [c / pre["code"] * pre["vdiv"] - pre["offset"] for c in codes]
        times = [
            -(pre["tdiv"] * 10 / 2) + i * pre["interval"] + pre["delay"]
            for i in range(len(codes))
        ]
        return {
            "t": times,
            "v": volts,
            "source": source,
            "points": len(volts),
            "interval_s": pre["interval"],
            "vdiv_v": pre["vdiv"],
            "adc_bit": pre["adc_bit"],
        }

    def screenshot_bmp(self) -> bytes:
        """:PRIN? BMP 截屏原始字节（含 TMC 头则剥离）。"""
        data = self.query_raw(C.SCREEN_BMP)
        return self._strip_tmc(data) if data.find(b"#") == 0 else data

    # ---------- 快照 ----------
    def snapshot(self) -> dict:
        chans = {}
        for ch in (1, 2, 3, 4):
            try:
                chans[f"ch{ch}"] = {
                    "coupling": self.channel_coupling(ch),
                    "attenuation_x": self.channel_attenuation(ch),
                    "scale_v_div": self.channel_scale(ch),
                    "offset_v": self.channel_offset(ch),
                }
            except Exception as e:
                chans[f"ch{ch}"] = {"error": str(e)}
        return {
            "idn": self.idn(),
            "acquire_depth": self.acquire_depth(),
            "sample_rate_hz": self.sample_rate(),
            "timebase_scale_s_div": self.timebase_scale(),
            "trigger_delay_s": self.trigger_delay(),
            "trigger_mode": self.trigger_mode(),
            "channels": chans,
        }


def find_sds(
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    cidr: Optional[str] = None,
    allow_scan: bool = False,
    timeout_ms: int = 3000,
) -> str:
    """发现 *IDN? 含 'SDS' 的 Siglent 示波器，返回资源地址。"""
    hit = find_device(
        "SDS",
        resource=resource,
        hosts=hosts,
        allow_scan=allow_scan,
        cidr=cidr,
        timeout_ms=timeout_ms,
    )
    return hit.resource
