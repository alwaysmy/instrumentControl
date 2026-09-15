"""RIGOL 示波器共享内核：DHO800/900 与 MHO900 的**同一套**控制实现。

为什么能共享：两系列 97% 命令键重合，DHO 驱动用到的 40 条命令 100% 存在于 MHO 手册
（反向仅差 2 条：`:ACQuire:BITS`、`:CHANnel<n>:Impedance`）。量化证据与差异表见
`docs/rigol_scope_compare_20260915.md` 与 `rigol_scope/families.py`。

差异一律走 `Family` 表（清测量命令、采集方式第四态、能力开关有无、点数上限…），
本文件不出现任何家族专有字面量——这样"哪些不一样"永远只有一处可查。

实现来源：以 `mho_control` 那份**真机验证过**的实现为基准（MHO984D 45/45 PASS，
含双信源测量、波形分片、RAW/STOP 前置校验、原生 PNG 截图），DHO 由此获得同等待遇，
并顺带修掉 DHO 旧实现的三处缺陷（ASCII 死分支、不校验 points、不分片）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.discovery import find_device, identify, list_resources, scan  # noqa: F401,E402
from common.visa_client import VisaClient  # noqa: E402

from .families import Family, family_of  # noqa: E402

# RIGOL 对无效测量统一返回该哨兵值（实测 MHO984D：无有效读数即 9.9000E+37）
INVALID_MEASURE = 9.9e37


class RigolScope:
    """DHO800/900 与 MHO900 共用的示波器控制封装（家族差异见 `Family`）。"""

    FAMILY: Family  # 子类覆盖（dho_control.DHO / mho_control.MHO）

    def __init__(
        self,
        resource: Optional[str] = None,
        model: Optional[str] = None,
        timeout_ms: int = 10000,
        hosts: Optional[list[str]] = None,
        cidr: Optional[str] = None,
        allow_scan: bool = False,
    ):
        self.family = self.FAMILY if model is None else family_of(model)
        self.model = model or self.family.name
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
                self.family.name,
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

    def __enter__(self) -> "RigolScope":
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
        """:SYSTem:VERSion? SCPI 版本（MHO 实测 '3.0'）。"""
        return self.query(":SYSTem:VERSion?")

    def system_error(self) -> Optional[str]:
        """读一条错误队列（'' 或 '0,"No error"' 视为无错）。"""
        resp = self.query(":SYSTem:ERRor?").strip()
        if not resp or resp.startswith("0,") or resp.startswith("+0,"):
            return None
        return resp

    def drain_errors(self, limit: int = 20) -> list[str]:
        """排空错误队列（写序列前必须先 drain，否则滞后报错张冠李戴）。"""
        errs: list[str] = []
        for _ in range(limit):
            e = self.system_error()
            if e is None:
                break
            errs.append(e)
        return errs

    def beeper(self, state: Optional[bool] = None) -> Optional[bool]:
        if state is None:
            return self.query(":SYSTem:BEEPer?").strip() in ("1", "ON")
        self.write(f":SYSTem:BEEPer {'ON' if state else 'OFF'}")
        return None

    # ---------- 控制流 ----------
    def run(self) -> None:
        self.write(":RUN")

    def stop(self) -> None:
        """:STOP —— RAW 模式读内存波形前必须处于停止态（两手册同）。"""
        self.write(":STOP")

    def single(self) -> None:
        self.write(":SINGle")

    def force_trigger(self) -> None:
        self.write(":TFORce")

    def clear(self) -> None:
        """清除屏幕波形。"""
        self.write(":CLEar")

    def autoset(self) -> None:
        """:AUToset 自动设置（**全局破坏性**：调整所有通道档位/时基/触发）。"""
        self.write(":AUToset")

    def trigger_status(self) -> str:
        """:TRIGger:STATus? → TD|WAIT|RUN|AUTO|STOP。"""
        return self.query(":TRIGger:STATus?").strip()

    # ---------- 采集 ----------
    def acquire_depth(self, value: Optional[str] = None) -> Optional[str]:
        """:ACQuire:MDEPth 存储深度（取值随家族，见 Family.acq_depths）。"""
        if value is None:
            return self.query(":ACQuire:MDEPth?").strip() or None
        if value.upper() != "AUTO" and value not in self.family.acq_depths:
            raise ValueError(
                f"{self.family.name} 不支持的存储深度 {value!r}（可选 {self.family.acq_depths}）")
        self.write(f":ACQuire:MDEPth {value}")
        return None

    def acquire_type(self, value: Optional[str] = None) -> Optional[str]:
        """:ACQuire:TYPE 采集方式（**第四态随家族**：DHO=ULTRa / MHO=HRESolution）。"""
        if value is None:
            return self.query(":ACQuire:TYPE?").strip() or None
        if value.upper() not in [v.upper() for v in self.family.acq_types]:
            raise ValueError(
                f"{self.family.name} 不支持的采集方式 {value!r}（可选 {self.family.acq_types}）")
        self.write(f":ACQuire:TYPE {value}")
        return None

    def acquire_bits(self, value: Optional[int] = None) -> Optional[int]:
        """:ACQuire:BITS 位组长度 14|16（**仅 MHO**；DHO 无此命令）。"""
        if self.family.acq_bits is None:
            raise ValueError(f"{self.family.name} 无 :ACQuire:BITS 命令（MHO900 才有）")
        if value is None:
            resp = self.query(":ACQuire:BITS?").strip()
            return int(float(resp)) if resp else None
        if int(value) not in self.family.acq_bits:
            raise ValueError(f"invalid bits: {value!r}（可选 {self.family.acq_bits}）")
        self.write(f":ACQuire:BITS {int(value)}")
        return None

    def sample_rate(self) -> float:
        """当前采样率（MHO 实测随通道数下降：1~2ch 4GSa/s、3~4ch 1GSa/s）。"""
        return float(self.query(":ACQuire:SRATe?"))

    # ---------- 通道 ----------
    def _check_ch(self, ch: int) -> int:
        n = int(ch)
        if not 1 <= n <= self.family.channels:
            raise ValueError(
                f"invalid channel: {ch!r}（{self.family.name} 共 {self.family.channels} 通道）")
        return n

    def channel_display(self, ch: int, on: Optional[bool] = None) -> Optional[bool]:
        n = self._check_ch(ch)
        if on is None:
            return self.query(f":CHANnel{n}:DISPlay?").strip() in ("1", "ON")
        self.write(f":CHANnel{n}:DISPlay {'ON' if on else 'OFF'}")
        return None

    def channel_scale(self, ch: int, scale: Optional[float] = None) -> Optional[float]:
        """:CHANnel<n>:SCALe 垂直档位 V/div。未开启通道写 SCALe 会被拒(-200)，自动先开启。"""
        n = self._check_ch(ch)
        if scale is not None and not self.channel_display(n):
            self.channel_display(n, True)
        if scale is None:
            resp = self.query(f":CHANnel{n}:SCALe?")
            return float(resp) if resp else None
        self.write(f":CHANnel{n}:SCALe {scale}")
        return None

    def channel_offset(self, ch: int, offset: Optional[float] = None) -> Optional[float]:
        n = self._check_ch(ch)
        if offset is None:
            resp = self.query(f":CHANnel{n}:OFFSet?")
            return float(resp) if resp else None
        self.write(f":CHANnel{n}:OFFSet {offset}")
        return None

    def channel_coupling(self, ch: int, coupling: Optional[str] = None) -> Optional[str]:
        n = self._check_ch(ch)
        if coupling is None:
            return self.query(f":CHANnel{n}:COUPling?").strip() or None
        if coupling.upper() not in [c.upper() for c in self.family.chan_couplings]:
            raise ValueError(f"invalid coupling: {coupling!r}（可选 {self.family.chan_couplings}）")
        self.write(f":CHANnel{n}:COUPling {coupling.upper()}")
        return None

    def channel_probe(self, ch: int, atten: Optional[float] = None) -> Optional[float]:
        n = self._check_ch(ch)
        if atten is None:
            resp = self.query(f":CHANnel{n}:PROBe?")
            return float(resp) if resp else None
        self.write(f":CHANnel{n}:PROBe {atten}")
        return None

    def channel_bwlimit(self, ch: int, val: Optional[str] = None) -> Optional[str]:
        """:CHANnel<n>:BWLimit 带宽限制（取值随机型；DHO 侧不校验，交由设备判断）。"""
        n = self._check_ch(ch)
        if val is None:
            return self.query(f":CHANnel{n}:BWLimit?").strip() or None
        self.write(f":CHANnel{n}:BWLimit {val}")
        return None

    def channel_impedance(self, ch: int, val: Optional[str] = None) -> Optional[str]:
        """:CHANnel<n>:IMPedance OMEG(1MΩ)|FIFTy(50Ω)（**仅 MHO**）。"""
        if self.family.chan_impedances is None:
            raise ValueError(f"{self.family.name} 无 :CHANnel<n>:IMPedance 命令（MHO900 才有）")
        n = self._check_ch(ch)
        if val is None:
            return self.query(f":CHANnel{n}:IMPedance?").strip() or None
        if val.upper() not in [v.upper() for v in self.family.chan_impedances]:
            raise ValueError(f"invalid impedance: {val!r}（可选 {self.family.chan_impedances}）")
        self.write(f":CHANnel{n}:IMPedance {val.upper()}")
        return None

    # ---------- 时基 ----------
    def timebase_scale(self, scale: Optional[float] = None) -> Optional[float]:
        if scale is None:
            resp = self.query(":TIMebase:MAIN:SCALe?")
            return float(resp) if resp else None
        self.write(f":TIMebase:MAIN:SCALe {scale}")
        return None

    def timebase_offset(self, offset: Optional[float] = None) -> Optional[float]:
        if offset is None:
            resp = self.query(":TIMebase:MAIN:OFFSet?")
            return float(resp) if resp else None
        self.write(f":TIMebase:MAIN:OFFSet {offset}")
        return None

    # ---------- 触发 ----------
    def trigger_mode(self, mode: Optional[str] = None) -> Optional[str]:
        if mode is None:
            return self.query(":TRIGger:MODE?").strip() or None
        if mode.upper() not in [m.upper() for m in self.family.trigger_types]:
            raise ValueError(f"invalid trigger mode: {mode!r}（可选 {self.family.trigger_types}）")
        self.write(f":TRIGger:MODE {mode.upper()}")
        return None

    def sweep(self, sweep: Optional[str] = None) -> Optional[str]:
        if sweep is None:
            return self.query(":TRIGger:SWEep?").strip() or None
        if sweep.upper() not in [s.upper() for s in self.family.trigger_sweeps]:
            raise ValueError(f"invalid sweep: {sweep!r}（可选 {self.family.trigger_sweeps}）")
        self.write(f":TRIGger:SWEep {sweep.upper()}")
        return None

    def edge_trigger(self, source: Optional[int] = None, slope: Optional[str] = None,
                     level: Optional[float] = None) -> None:
        """边沿触发三要素（只写给出的项）。slope 第三态两家族**都是** `RFALl`。"""
        if source is not None:
            self.write(f":TRIGger:EDGE:SOURce CHANnel{self._check_ch(source)}")
        if slope is not None:
            self.write(f":TRIGger:EDGE:SLOPe {slope}")
        if level is not None:
            self.write(f":TRIGger:EDGE:LEVel {level}")

    def edge_source(self) -> Optional[str]:
        return self.query(":TRIGger:EDGE:SOURce?").strip() or None

    def edge_slope(self) -> Optional[str]:
        return self.query(":TRIGger:EDGE:SLOPe?").strip() or None

    def edge_level(self, level: Optional[float] = None) -> Optional[float]:
        if level is None:
            resp = self.query(":TRIGger:EDGE:LEVel?")
            return float(resp) if resp else None
        self.write(f":TRIGger:EDGE:LEVel {level}")
        return None

    # ---------- 测量 ----------
    def measure_source(self, source: Optional[str] = None) -> Optional[str]:
        if source is None:
            return self.query(":MEASure:SOURce?").strip() or None
        self.write(f":MEASure:SOURce {self._norm_source(source)}")
        return None

    def measure_item(self, item: str, src: Union[int, str] = 1,
                     src2: Optional[Union[int, str]] = None,
                     open_measurement: bool = True) -> float:
        """:MEASure:ITEM? <item>[,<src>[,<src2>]] 单次测量查询。

        item 取家族 `Family.measure_items`；双信源项（延迟/相位）需给 src2 ——
        **两个系列的手册都支持双信源项**（DHO 手册同样记载 RRDelay/RRPHase 等），
        此前 DHO 驱动未暴露，合并后补齐。

        设备对无效测量返回 **9.9E37** 哨兵，本库转成 ValueError（文案含原值）。
        ⚠ 信号超屏时读数被钳制在屏界不可信——形态判断请用 screenshot_png() 看截图。
        """
        fam = self.family
        item_up = item.strip()
        if item_up not in fam.measure_items + fam.measure_items_dual:
            raise ValueError(
                f"未知测量项 {item_up!r}。单信源: {', '.join(fam.measure_items)}；"
                f"双信源: {', '.join(fam.measure_items_dual)}")
        dual = item_up in fam.measure_items_dual
        if dual and src2 is None:
            raise ValueError(f"双信源测量项 {item_up} 需要同时给 src 与 src2（如 RRPHase,CHANnel1,CHANnel2）")
        s1 = self._norm_source(src)
        args = f"{item_up},{s1}" + (f",{self._norm_source(src2)}" if dual else "")
        if open_measurement:
            self.write(f":MEASure:ITEM {args}")
        resp = self.query(f":MEASure:ITEM? {args}").strip()
        try:
            val = float(resp)
        except ValueError as e:
            raise ValueError(f"测量项 {item_up}@{s1} 响应无法解析: {resp!r}") from e
        if val >= INVALID_MEASURE:
            raise ValueError(
                f"测量项 {item_up}@{s1}{'/' + self._norm_source(src2) if dual else ''} "
                f"无有效值（设备返回 {resp}）——检查信号接入/触发/档位")
        return val

    def measure_clear(self) -> None:
        """清除所有已打开的测量项（**命令随家族**：DHO `:MEASure:CLEar` / MHO `:MEASure:DELete`）。"""
        self.write(self.family.measure_clear)

    def _norm_source(self, src: Union[int, str]) -> str:
        """信源规范化：int → CHANnel<n>；字符串原样大写（MATH1/D1 等）。"""
        if isinstance(src, int) or (isinstance(src, str) and src.strip().isdigit()):
            return f"CHANnel{self._check_ch(int(src))}"
        return str(src).strip().upper()

    # ---------- 波形读取 ----------
    @staticmethod
    def _parse_tmc(data: bytes) -> bytes:
        """解析 TMC 块头（`#` + N + N 位 ASCII 长度），返回数据体。"""
        if len(data) < 2 or data[:1] != b"#":
            raise ValueError(f"非法 TMC 头: {data[:12]!r}")
        ndigits = int(data[1:2])
        length = int(data[2 : 2 + ndigits])
        body = data[2 + ndigits :]
        if len(body) < length:
            raise ValueError(f"TMC 数据不完整: 期望 {length} 字节，实得 {len(body)}")
        return body[:length]

    def preamble(self) -> dict:
        """:WAVeform:PREamble? 十个参数（两家族同构，手册 3.28.14/对应节）。

        `<format>,<type>,<points>,<count>,<xincrement>,<xorigin>,<xreference>,
        <yincrement>,<yorigin>,<yreference>`
        """
        resp = self.query(":WAVeform:PREamble?").strip()
        parts = [p.strip() for p in resp.split(",")]
        if len(parts) < 10:
            raise ValueError(f"PREamble 字段数不足（{len(parts)}）: {resp!r}")
        return {
            "format": parts[0], "type": parts[1],
            "points": int(float(parts[2])), "count": int(float(parts[3])),
            "xinc": float(parts[4]), "xorigin": float(parts[5]), "xref": float(parts[6]),
            "yinc": float(parts[7]), "yorigin": float(parts[8]), "yref": float(parts[9]),
        }

    def get_waveform(self, src: Union[int, str] = 1, mode: str = "NORMal",
                     fmt: str = "BYTE", points: Optional[int] = None,
                     chunk_points: int = 100000) -> dict:
        """读取波形并换算为物理量（电压 + 时间轴）。

        mode: NORMal 屏幕波形（家族上限 `wav_normal_max_points`，两系列都是 1000）/
        MAXimum / RAW 内存波形（**RAW 必须 STOP**，本库不做隐式状态变更：非 STOP 直接报错）；
        fmt: BYTE|WORD（低字节在前）|ASCii；points: 读取点数（超上限报 ValueError）。
        chunk_points: 分片读取的每片点数（手册未给单帧上限，分片避免超长 TMC 帧被截断）。
        """
        fam = self.family
        source = self._norm_source(src)
        mode_up, fmt_up = mode.upper(), fmt.upper()
        if mode_up not in [m.upper() for m in fam.wav_modes]:
            raise ValueError(f"不支持的模式 {mode!r}（{'|'.join(fam.wav_modes)}）")
        if fmt_up not in [f.upper() for f in fam.wav_formats]:
            raise ValueError(f"不支持的格式 {fmt!r}（{'|'.join(fam.wav_formats)}）")
        if mode_up == "RAW":
            status = self.trigger_status()
            if status != "STOP":
                raise RuntimeError(
                    f"RAW 模式读内存波形要求示波器处于 STOP 态（当前 {status}）——"
                    f"请先显式 stop()（RAW 读取期间不可操作仪器）")
        if points is not None and mode_up == "NORMAL" and points > fam.wav_normal_max_points:
            raise ValueError(
                f"NORMal 模式最多读 {fam.wav_normal_max_points} 点，"
                f"要读 {points} 点请用 mode='RAW'（需先 STOP）或 mode='MAXimum'")

        self.write(f":WAVeform:SOURce {source}")
        self.write(f":WAVeform:MODE {mode_up}")
        self.write(f":WAVeform:FORMat {fmt_up}")
        if mode_up == "NORMAL":
            total = points or fam.wav_normal_max_points
            self.write(f":WAVeform:POINts {total}")
        else:
            pre = self.preamble()
            total = min(points, pre["points"]) if points else pre["points"]
            self.write(f":WAVeform:POINts {total}")
        body = self._read_data_body(total, fmt_up, chunk_points)

        pre = self.preamble()
        if fmt_up == "ASCII":
            volts = [float(x) for x in body.decode("ascii", "replace").split(",") if x.strip()]
        elif fmt_up == "BYTE":
            volts = [(b - pre["yorigin"] - pre["yref"]) * pre["yinc"] for b in body]
        else:
            # WORD 字节序手册未记载；实测（MHO）低字节在前，两家族同平台故沿用
            volts = [((body[i] | (body[i + 1] << 8)) - pre["yorigin"] - pre["yref"]) * pre["yinc"]
                     for i in range(0, len(body) - 1, 2)]
        times = [pre["xorigin"] + i * pre["xinc"] for i in range(len(volts))]
        return {"t": times, "v": volts, "source": source, "mode": mode_up, "format": fmt_up,
                "points": len(volts), "xinc": pre["xinc"], "xorigin": pre["xorigin"],
                "yinc": pre["yinc"], "yorigin": pre["yorigin"], "yreference": pre["yref"],
                "preamble": pre}

    def _read_data_body(self, total: int, fmt: str, chunk_points: int) -> bytes:
        """分片读 `:WAVeform:DATA?`：二进制片剥 TMC 头，ASCII 片是**纯文本**（无 TMC 头）。"""
        if total <= 0:
            return b""
        per_point = 2 if fmt == "WORD" else 1
        chunks: list[bytes] = []
        start = 1                                  # :WAVeform:STARt/STOP 为 1 起始索引
        while start <= total:
            stop = min(start + chunk_points - 1, total)
            self.write(f":WAVeform:STARt {start}")
            self.write(f":WAVeform:STOP {stop}")
            raw = self.query_raw(":WAVeform:DATA?")
            if fmt == "ASCII":
                text = raw[1 + int(raw[1:2] or b"0") :] if raw[:1] == b"#" else raw
                chunks.append(text.strip() + b",")
            else:
                chunks.append(self._parse_tmc(raw)[: (stop - start + 1) * per_point])
            start = stop + 1
        blob = b"".join(chunks)
        return blob[:-1] if fmt == "ASCII" and blob.endswith(b",") else blob

    # ---------- 截屏 ----------
    def screenshot(self, fmt: str = "PNG") -> bytes:
        """`:DISPlay:DATA? <fmt>` 截屏原始字节（剥 TMC 头）；fmt: BMP|PNG|JPG。"""
        f = fmt.upper()
        if f not in [x.upper() for x in self.family.disp_formats]:
            raise ValueError(f"不支持的截图格式 {fmt!r}（{'|'.join(self.family.disp_formats)}）")
        data = self.query_raw(f":DISPlay:DATA? {f}")
        return self._parse_tmc(data) if data[:1] == b"#" else data

    def screenshot_png(self, save_path: Path) -> Path:
        """截屏存 PNG，返回路径（**该 PNG 可直接读图**，用于判断波形形态/削顶/居中）。"""
        data = self.screenshot("PNG")
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(data)
        return save_path

    # ---------- 快照 ----------
    def snapshot(self) -> dict:
        """只读快照（不改动设备配置）。"""
        chans = {}
        for ch in range(1, self.family.channels + 1):
            try:
                chans[f"ch{ch}"] = {
                    "display": self.channel_display(ch),
                    "coupling": self.channel_coupling(ch),
                    "scale_v_div": self.channel_scale(ch),
                    "offset_v": self.channel_offset(ch),
                    "probe_x": self.channel_probe(ch),
                }
            except Exception as e:  # 单通道查询失败不影响整机快照
                chans[f"ch{ch}"] = {"error": str(e)}
        return {
            "family": self.family.name,
            "idn": self.idn(),
            "version": self.version(),
            "trigger_status": self.trigger_status(),
            "acquire_depth": self.acquire_depth(),
            "acquire_type": self.acquire_type(),
            "sample_rate_hz": self.sample_rate(),
            "timebase_scale_s_div": self.timebase_scale(),
            "timebase_offset_s": self.timebase_offset(),
            "trigger_mode": self.trigger_mode(),
            "trigger_sweep": self.sweep(),
            "edge_source": self.edge_source(),
            "edge_level_v": self.edge_level(),
            "channels": chans,
        }


def find_scope(family: Family, resource: Optional[str] = None,
               hosts: Optional[list[str]] = None, cidr: Optional[str] = None,
               allow_scan: bool = False, timeout_ms: int = 3000) -> str:
    """发现该家族的示波器，返回资源地址（各库 find_dho/find_mho 走这里）。"""
    hit = find_device(family.name, resource=resource, hosts=hosts, allow_scan=allow_scan,
                      cidr=cidr, timeout_ms=timeout_ms)
    return hit.resource
