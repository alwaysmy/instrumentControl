"""RIGOL DHO 系列数字示波器驱动（DHO800/DHO900 系列，多型号预留）。

实测基准：DHO924S，LAN raw socket（TCPIP0::ip::5555::SOCKET + \\n 终止符），
经 common.find_device 自动发现；USB TMC / VXI-11 同样适用。

命令来源：docs/DHO800编程手册_output/（418 页提取版）。

用法：
    from dho_control import DHO, find_dho

    with DHO(find_dho()) as scope:
        print(scope.idn())
        vpp = scope.measure_item("VPP", 1)
        wf = scope.get_waveform(1)   # 屏幕波形 BYTE 格式 → 电压序列
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.discovery import find_device, identify, list_resources, scan  # noqa: F401
from common.visa_client import VisaClient

from . import commands as C

Model = str


def resolve_model(model: Optional[Model]) -> str:
    """型号规范化：必须以 'DHO' 开头（DHO800/DHO900 全系列同命令集）。"""
    m = (model or "DHO").strip().upper()
    if not m.startswith("DHO"):
        raise ValueError(f"型号 {model!r} 不属于 DHO 系列（DHO800/DHO900）")
    return m


class DHO:
    """RIGOL DHO 系列示波器控制封装。"""

    def __init__(
        self,
        resource: Optional[str] = None,
        model: Model = "DHO",
        timeout_ms: int = 10000,
        hosts: Optional[list[str]] = None,
        cidr: Optional[str] = None,
        allow_scan: bool = False,
    ):
        self.model = resolve_model(model)
        self.resource = resource
        self.timeout_ms = timeout_ms
        self.hosts = list(hosts) if hosts else []
        self.cidr = cidr
        self.allow_scan = allow_scan
        self.client: Optional[VisaClient] = None

    # ---------- 连接管理 ----------
    def connect(self, resource: Optional[str] = None) -> str:
        """连接设备；resource 为空时经 common.find_device 发现（USB/LAN 均可）。"""
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

    def __enter__(self) -> "DHO":
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

    def query_raw(self, cmd: str) -> bytes:
        return self._c().query_raw(cmd)

    # ---------- 信息与系统 ----------
    def idn(self) -> str:
        return self.query("*IDN?")

    def version(self) -> str:
        return self.query(C.SYST_VERS)

    def system_error(self) -> Optional[str]:
        resp = self.query(C.SYST_ERR)
        return resp or None

    def reset(self) -> None:
        """:SYSTem:RESet 恢复出厂默认（会改动面板设定，使用前备份）。"""
        self.write(C.SYST_RESET)

    def beeper(self, state: Optional[bool] = None) -> Optional[bool]:
        if state is None:
            return self.query(f"{C.SYST_BEEP}?").strip() in ("1", "ON")
        self.write(f"{C.SYST_BEEP} {'ON' if state else 'OFF'}")
        return None

    # ---------- 控制流 ----------
    def run(self) -> None:
        self.write(C.RUN)

    def stop(self) -> None:
        self.write(C.STOP)

    def single(self) -> None:
        self.write(C.SINGLE)

    def force_trigger(self) -> None:
        self.write(C.TFORCE)

    def clear(self) -> None:
        self.write(C.CLEAR)

    def autoset(self) -> None:
        """:AUToset 自动设置（会改变当前通道/时基/触发配置）。"""
        self.write(C.AUTOSET)

    def trigger_status(self) -> str:
        """:TRIGger:STATus? 触发状态（Stop/TD/Wait/TRiggered/AUTO...）。"""
        return self.query(C.TRIG_STATUS).strip()

    # ---------- 采集 ----------
    def acquire_depth(self, value: Optional[str] = None) -> Optional[str]:
        """:ACQuire:MDEPth 存储深度 AUTO|1k|10k|100k|1M|10M|25M(DHO900:50M)。"""
        if value is None:
            return self.query(C.ACQ_MDEP + "?").strip() or None
        self.write(f"{C.ACQ_MDEP} {value}")
        return None

    def acquire_type(self, value: Optional[str] = None) -> Optional[str]:
        """:ACQuire:TYPE 采集方式 NORMal|PEAK|AVERages|ULTRa（手册 3.3.4）。"""
        if value is None:
            return self.query(C.ACQ_TYPE + "?").strip() or None
        self.write(f"{C.ACQ_TYPE} {value}")
        return None

    def sample_rate(self) -> float:
        return float(self.query(C.ACQ_SRAT))

    # ---------- 通道 ----------
    def _check_ch(self, ch: int) -> int:
        n = int(ch)
        if n not in (1, 2, 3, 4):
            raise ValueError(f"invalid channel: {ch!r}（DHO 系列 1~4）")
        return n

    def channel_display(self, ch: int, on: Optional[bool] = None) -> Optional[bool]:
        n = self._check_ch(ch)
        if on is None:
            return self.query(f"{C.CHAN_DISP.format(n=n)}?").strip() in ("1", "ON")
        self.write(f"{C.CHAN_DISP.format(n=n)} {'ON' if on else 'OFF'}")
        return None

    def channel_coupling(self, ch: int, coupling: Optional[str] = None) -> Optional[str]:
        """:CHANnel<n>:COUPling DC|AC|GND。"""
        n = self._check_ch(ch)
        if coupling is None:
            return self.query(f"{C.CHAN_COUP.format(n=n)}?").strip() or None
        self.write(f"{C.CHAN_COUP.format(n=n)} {coupling.upper()}")
        return None

    def channel_scale(self, ch: int, scale: Optional[float] = None) -> Optional[float]:
        """:CHANnel<n>:SCALe 垂直档位 V/div。未开启的通道写入会被拒(-200)，自动先开启。"""
        n = self._check_ch(ch)
        if scale is not None and not self.channel_display(n):
            self.channel_display(n, True)
        if scale is None:
            resp = self.query(f"{C.CHAN_SCALE.format(n=n)}?")
            return float(resp) if resp else None
        self.write(f"{C.CHAN_SCALE.format(n=n)} {scale}")
        return None

    def channel_offset(self, ch: int, offset: Optional[float] = None) -> Optional[float]:
        """:CHANnel<n>:OFFSet 垂直偏移 V。"""
        n = self._check_ch(ch)
        if offset is None:
            resp = self.query(f"{C.CHAN_OFFS.format(n=n)}?")
            return float(resp) if resp else None
        self.write(f"{C.CHAN_OFFS.format(n=n)} {offset}")
        return None

    def channel_probe(self, ch: int, atten: Optional[float] = None) -> Optional[float]:
        """:CHANnel<n>:PROBe 探头衰减比（如 1X/10X）。"""
        n = self._check_ch(ch)
        if atten is None:
            resp = self.query(f"{C.CHAN_PROBE.format(n=n)}?")
            return float(resp) if resp else None
        self.write(f"{C.CHAN_PROBE.format(n=n)} {atten}")
        return None

    def channel_bwlimit(self, ch: int, val: Optional[str] = None) -> Optional[str]:
        """:CHANnel<n>:BWLimit OFF|20M|...（按手册机型可选值）。"""
        n = self._check_ch(ch)
        if val is None:
            return self.query(f"{C.CHAN_BWL.format(n=n)}?").strip() or None
        self.write(f"{C.CHAN_BWL.format(n=n)} {val}")
        return None

    # ---------- 时基 ----------
    def timebase_scale(self, scale: Optional[float] = None) -> Optional[float]:
        """:TIMebase:MAIN:SCALe 时基档位 s/div。"""
        if scale is None:
            resp = self.query(C.TB_SCALE + "?")
            return float(resp) if resp else None
        self.write(f"{C.TB_SCALE} {scale}")
        return None

    def timebase_offset(self, offset: Optional[float] = None) -> Optional[float]:
        """:TIMebase:MAIN:OFFSet 时基偏移 s。"""
        if offset is None:
            resp = self.query(C.TB_OFFSET + "?")
            return float(resp) if resp else None
        self.write(f"{C.TB_OFFSET} {offset}")
        return None

    # ---------- 触发（边沿） ----------
    def edge_trigger(
        self,
        source: Optional[int] = None,
        slope: Optional[str] = None,
        level: Optional[float] = None,
    ) -> None:
        """设置边沿触发三要素（只写给出的项）。slope: POSitive|NEGative|RFail。"""
        if source is not None:
            self.write(f"{C.EDGE_SOUR} CHANnel{self._check_ch(source)}")
        if slope is not None:
            self.write(f"{C.EDGE_SLOP} {slope}")
        if level is not None:
            self.write(f"{C.EDGE_LEV} {level}")

    def edge_level(self, level: Optional[float] = None) -> Optional[float]:
        if level is None:
            resp = self.query(C.EDGE_LEV + "?")
            return float(resp) if resp else None
        self.write(f"{C.EDGE_LEV} {level}")
        return None

    # ---------- 测量 ----------
    def measure_item(self, item: str, src: int) -> float:
        """:MEASure:ITEM? <item>,<src> 单次测量查询（无效测量返回 9.9E37）。"""
        item_up = item.strip()
        if item_up not in C.MEAS_ITEMS:
            raise ValueError(f"未知测量项 {item!r}，可用: {', '.join(C.MEAS_ITEMS)}")
        n = self._check_ch(src)
        resp = self.query(f"{C.MEAS_ITEM}? {item_up},CHANnel{n}").strip()
        val = float(resp)
        if val >= 9.9e37:
            raise ValueError(f"测量项 {item_up} CHANnel{n} 无有效值（返回 {resp}）")
        return val

    def clear_measurements(self) -> None:
        self.write(C.MEAS_CLEAR)

    # ---------- 波形读取 ----------
    @staticmethod
    def _parse_tmc(data: bytes) -> bytes:
        """解析 TMC 块头（#9 + 9 位 ASCII 长度）。"""
        if len(data) < 2 or data[:1] != b"#":
            raise ValueError(f"非法 TMC 头: {data[:12]!r}")
        ndigits = int(data[1:2])
        length = int(data[2 : 2 + ndigits])
        body = data[2 + ndigits :]
        if len(body) < length:
            raise ValueError(f"TMC 数据不完整: 期望 {length} 字节，实得 {len(body)}")
        return body[:length]

    def get_waveform(
        self,
        src: Union[int, str] = 1,
        mode: str = "NORMal",
        fmt: str = "BYTE",
        points: Optional[int] = None,
    ) -> dict:
        """读取波形并换算为物理量。

        mode: NORMal(屏幕)/RAW(内存，须 STOP 态)/MAXimum；
        fmt: BYTE(8bit)/WORD(16bit)/ASCii。
        返回 {"t": [s], "v": [V], "xinc","xorigin","yinc","yorigin","yref","points"}。
        """
        source = f"CHANnel{self._check_ch(src)}" if isinstance(src, int) else str(src).upper()
        self.write(f"{C.WAV_SOUR} {source}")
        self.write(f"{C.WAV_MODE} {mode}")
        fmt_up = fmt.upper()
        self.write(f"{C.WAV_FMT} {fmt_up}")
        if points is not None:
            self.write(f"{C.WAV_POINTS} {points}")

        xinc = float(self.query(C.WAV_XINC))
        xorg = float(self.query(C.WAV_XORG))
        yinc = float(self.query(C.WAV_YINC))
        yorg = float(self.query(C.WAV_YORG))
        yref = float(self.query(C.WAV_YREF))

        if fmt_up == "ASCii":
            raw_resp = self.query(C.WAV_DATA)
            volts = [float(x) for x in raw_resp.split(",")]
        elif fmt_up == "BYTE":
            raw = self._parse_tmc(self.query_raw(C.WAV_DATA))
            volts = [(b - yorg - yref) * yinc for b in raw]
        elif fmt_up == "WORD":
            raw = self._parse_tmc(self.query_raw(C.WAV_DATA))
            volts = [
                ((raw[i] | (raw[i + 1] << 8)) - yorg - yref) * yinc
                for i in range(0, len(raw) - 1, 2)
            ]
        else:
            raise ValueError(f"不支持格式 {fmt!r}（BYTE|WORD|ASCii）")

        times = [xorg + i * xinc for i in range(len(volts))]
        return {
            "t": times,
            "v": volts,
            "source": source,
            "mode": mode,
            "format": fmt_up,
            "xinc": xinc,
            "xorigin": xorg,
            "yinc": yinc,
            "yorigin": yorg,
            "yreference": yref,
            "points": len(volts),
        }

    # ---------- 快照 ----------
    def snapshot(self) -> dict:
        """只读快照（不改动设备配置）。"""
        chans = {}
        for ch in (1, 2, 3, 4):
            try:
                chans[f"ch{ch}"] = {
                    "display": self.channel_display(ch),
                    "coupling": self.channel_coupling(ch),
                    "scale_v_div": self.channel_scale(ch),
                    "offset_v": self.channel_offset(ch),
                    "probe_x": self.channel_probe(ch),
                }
            except Exception as e:
                chans[f"ch{ch}"] = {"error": str(e)}
        return {
            "idn": self.idn(),
            "version": self.version(),
            "trigger_status": self.trigger_status(),
            "acquire_depth": self.acquire_depth(),
            "acquire_type": self.acquire_type(),
            "sample_rate_hz": self.sample_rate(),
            "timebase_scale_s_div": self.timebase_scale(),
            "timebase_offset_s": self.timebase_offset(),
            "edge_level_v": self.edge_level(),
            "channels": chans,
        }


def find_dho(
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    cidr: Optional[str] = None,
    allow_scan: bool = False,
    timeout_ms: int = 3000,
) -> str:
    """发现 *IDN? 含 'DHO' 的示波器，返回资源地址；未找到抛 RuntimeError。"""
    hit = find_device(
        "DHO",
        resource=resource,
        hosts=hosts,
        allow_scan=allow_scan,
        cidr=cidr,
        timeout_ms=timeout_ms,
    )
    return hit.resource
