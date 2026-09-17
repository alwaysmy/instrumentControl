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

import math
import sys
import time
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.discovery import find_device, identify, list_resources, scan  # noqa: F401,E402
from common.visa_client import VisaClient  # noqa: E402

from .families import Family, family_of  # noqa: E402

# RIGOL 对无效测量统一返回该哨兵值（实测 MHO984D：无有效读数即 9.9000E+37）
INVALID_MEASURE = 9.9e37

# 需要"屏内 ≥2 个边沿"才有值的测量项（时间/边沿类）——现场证据：20 µs/div 看 5 kHz
# 读不到频率，放宽到 100 µs/div 立刻读到 4.9993 kHz：**是窗口不够，不是精度问题**。
EDGE_DEPENDENT_ITEMS = frozenset({
    "FREQuency", "PERiod", "PEDGes", "NEDGes", "PPULses", "NPULses",
    "PDUTy", "NDUTy", "PWIDth", "NWIDth", "RTIMe", "FTIMe",
    "PSLewrate", "NSLewrate",
})


def snap_1_2_5(value: float) -> float:
    """把目标值吸附到 {1,2,5}×10ⁿ（示波器垂直/水平档位的标准序列）。

    设备自身也会吸附，但先在主机侧吸附能让"目标档位"可解释（设计文档 §2 S3）。
    """
    if value <= 0 or not math.isfinite(value):
        return value
    base = 10.0 ** math.floor(math.log10(value))
    for m in (1, 2, 5):
        if value <= m * base * (1 + 1e-9):
            return m * base
    return 10 * base


def snap_down(value: float, min_scale: Optional[float] = None) -> Optional[float]:
    """档位序列 {1,2,5}×10ⁿ 里的**下一小档**（缩小一档）；到底返回 None。

    与 `snap_up` 对称（1 → 0.5、5 → 2、0.2 → 0.1）。给 min_scale 时低于它即返回 None。
    """
    if value is None or value <= 0 or not math.isfinite(value):
        return None
    base = 10.0 ** math.floor(math.log10(value) + 1e-12)
    for m in (5, 2, 1):
        cand = m * base
        if cand < value * (1 - 1e-9):
            if min_scale is not None and cand < min_scale * (1 - 1e-9):
                return None
            return cand
    nxt = 5.0 * base / 10.0          # 1×10ⁿ 的下一档是 5×10ⁿ⁻¹
    if min_scale is not None and nxt < min_scale * (1 - 1e-9):
        return None
    return nxt


def snap_up(value: float, max_scale: Optional[float] = None) -> Optional[float]:
    """档位序列 {1,2,5}×10ⁿ 里的**下一档**（放大一档）；已在最大档返回 None。

    例：0.9 → 1.0（不是 2.0）、2 → 5、5 → 10、0.5 → 1。给 max_scale 时超过它即返回 None
    （自动定标的"超出可测范围"判据用它，而不是靠迭代次数耗尽）。
    """
    if value is None or value <= 0 or not math.isfinite(value):
        return None
    base = 10.0 ** math.floor(math.log10(value) + 1e-12)
    for m in (1, 2, 5):
        cand = m * base
        if cand > value * (1 + 1e-9):
            if max_scale is not None and cand > max_scale * (1 + 1e-9):
                return None
            return cand
    nxt = 10.0 * base
    if max_scale is not None and nxt > max_scale * (1 + 1e-9):
        return None
    return nxt


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
    def align_session(self, max_drain: int = 4) -> bool:
        """确认响应流**对齐**；错位则排干，仍不对齐抛错（附恢复建议）。

        背景（2026-09-17 实测，`docs/visa_concurrency_20260917.md`）：同一台设备多个会话
        并发、或**超时未读**之后，仪器侧响应流会变成"稳定滞后一条"——问 `:SCALe?` 回偏置、
        问 `:PROBe?` 回耦合。此后**每个新会话**都读到错位数据，症状是各种"莫名其妙"的
        解析错误（例如把 `NORM` 当数字转 float）。判据用最可靠的 `*IDN?`：它必须回 IDN 串。

        排干做法：写一条 `*IDN?`、把可读到的响应**读到超时为止**（读得比写得多才能把
        多出来的那条吃掉），重复几轮。排不干就抛错——让调用方去换协议/重置仪器 LAN，
        而不是拿着一串错位数据继续算。
        """
        if self.client is None:
            raise RuntimeError("未连接设备，请先 connect()")
        last = ""
        for i in range(max(1, max_drain)):
            try:
                resp = self.client.query("*IDN?").strip()
            except Exception as e:                  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
                continue
            if "RIGOL" in resp.upper():
                return True
            last = resp[:60]
            # 不对齐：排干（读空一次，把多出来的响应吃掉）
            try:
                while True:
                    if not self.client.inst.read_raw():
                        break
            except Exception:
                pass
            time.sleep(0.15)
        raise RuntimeError(
            "仪器响应流**错位**（*IDN? 回 " + repr(last) + "）且排干无效——"
            "常见原因是同一台设备被多个会话并发访问（含超时未读的残留响应）。"
            "处置：换协议（VXI-11 ↔ raw socket）或重置该仪器 LAN/重启后重试；"
            "细节见 docs/visa_concurrency_20260917.md")

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

    def _float(self, resp: str, cmd: str) -> float:
        """把响应转 float；**转不动就是响应错位**，报可执行的错而不是裸 ValueError。

        为什么单列（2026-09-17 实测）：仪器响应流错位时，问数值项会拿到上一条查询的
        答案（如 `:ACQuire:SRATe?` 回 `NORM`），裸 `float()` 只会给出
        "could not convert string to float: 'NORM'" —— 看不出是并发污染。
        这里统一成"响应错位 + 处置建议"，见 `docs/visa_concurrency_20260917.md`。
        """
        try:
            return float(resp)
        except (TypeError, ValueError) as e:
            raise RuntimeError(
                f"响应错位：{cmd} 回 {resp!r}（不像该命令的答案）——仪器响应流可能被"
                "并发会话/超时未读污染，数据不可信。处置：换协议（VXI-11 ↔ raw）或重置"
                "该仪器 LAN/重启；细节见 docs/visa_concurrency_20260917.md") from e

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
        return self._float(self.query(":ACQuire:SRATe?"), ":ACQuire:SRATe?")

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
            return self._float(resp, ":CHANnel<n>:SCALe?") if resp else None
        self.write(f":CHANnel{n}:SCALe {scale}")
        return None

    def channel_offset(self, ch: int, offset: Optional[float] = None) -> Optional[float]:
        n = self._check_ch(ch)
        if offset is None:
            resp = self.query(f":CHANnel{n}:OFFSet?")
            return self._float(resp, ":CHANnel<n>:OFFSet?") if resp else None
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
            return self._float(resp, ":CHANnel<n>:PROBe?") if resp else None
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

    # ---------- 垂直窗口 / 设置语义 ----------
    # 本节把 2026-09-15 现场踩到的设备行为固化成代码语义（证据与实测原文见
    # `docs/tool_optimization_20260915.md` §P1-3，设计判据见
    # `docs/示波器自动定标设计-2026-09-15.md`）：
    #   ① 屏幕中心电压 = **−offset**（不是 +offset）；
    #   ② 改 SCALe 会**等比缩放 offset**（设备主动改写以保持波形屏幕位置）→ 必须先 scale 后 offset；
    #   ③ 通道 OFF 时写 SCALe/OFFSet 被**静默忽略**（无错误码）→ 要写垂直参数先开通道；
    #   ④ offset 有量程上限（本机实测 ±20 V）→ 写后回读比对，钳制时如实上报。
    # 这些坑的共同形态是"看起来成功、其实没生效"，所以本节的方法一律**回读验证**、
    # 并把"设备没照做"翻译成 adjusted + reasons，而不是混成 ok。

    def _chan_state(self, n: int) -> dict:
        """单通道垂直状态一次性回读（display/scale/offset/coupling/probe）。"""
        return {"display": self.channel_display(n),
                "scale_v_div": self.channel_scale(n),
                "offset_v": self.channel_offset(n),
                "coupling": self.channel_coupling(n),
                "probe_x": self.channel_probe(n)}

    def vertical_window(self, ch: int) -> Optional[dict]:
        """当前档位下的屏幕竖窗（**中心 = −offset**）。

        格数取 `Family.vdivs`；**未实测标定的家族返回 None**（宁可没有该能力，
        也不猜——填错格数会让离屏判据得出自信的错误结论）。
        """
        if self.family.vdivs is None:
            return None
        n = self._check_ch(ch)
        scale, offset = self.channel_scale(n), self.channel_offset(n)
        if scale is None or offset is None:
            return None
        half = self.family.vdivs / 2.0 * scale
        return {"ch": n, "scale_v_div": scale, "offset_v": offset,
                "center_v": -offset, "bottom_v": -offset - half, "top_v": -offset + half,
                "height_v": self.family.vdivs * scale, "vdivs": self.family.vdivs}

    def horizontal_window(self) -> Optional[dict]:
        """屏内时间窗（水平格数未标定的家族返回 None）——"边沿够不够"判据用。"""
        if self.family.hdivs is None:
            return None
        tdiv = self.timebase_scale()
        if tdiv is None:
            return None
        return {"t_div_s": tdiv, "span_s": self.family.hdivs * tdiv,
                "hdivs": self.family.hdivs,
                "note": f"按 {self.family.hdivs} 格估算（未单独标定）"}

    @staticmethod
    def _explain(key: str, want_v: float, got: float, reasons: list) -> None:
        """给"设备没照做"配一句原因（钳制 / 吸附 / 未生效）。"""
        if key == "offset":
            if abs(got) < abs(want_v) - 1e-9:
                reasons.append(
                    f"偏置被设备钳制：要求 {want_v:g} V，回读 {got:g} V"
                    "（偏置量程**随档位变**——MHO984D 实测：0.05 V/div→±1 V、"
                    "0.1~0.2→±10 V、0.5~2→±20 V、5~10→±100 V；要更大偏置得先抬档位）")
            else:
                reasons.append(f"偏置未生效：要求 {want_v:g} V，回读 {got:g} V")
        elif key == "scale":
            if abs(got - snap_1_2_5(want_v)) < 1e-9:
                reasons.append(f"档位被设备吸附到 {got:g} V/div（合法序列 {{1,2,5}}×10ⁿ）")
            else:
                reasons.append(f"档位未生效：要求 {want_v:g} V/div，回读 {got:g} V/div")
        else:
            reasons.append(f"{key} 未生效：要求 {want_v:g}，回读 {got:g}")

    def configure_channel(self, ch: int, scale: Optional[float] = None,
                          offset: Optional[float] = None, coupling: Optional[str] = None,
                          probe: Optional[float] = None, display: Optional[bool] = None,
                          tol: float = 0.02) -> dict:
        """设置通道垂直参数并**回读验证**（返回 requested/before/actual/adjusted/reasons/window）。

        执行顺序按设备行为固定：需要写垂直参数而通道为 OFF → **先开启**（否则写入被
        静默忽略）；垂直参数固定 **scale → offset**（反序必错，见类内说明②）；`display`
        在参数写完之后再应用。`adjusted` 非空即"设备没照做"，附原因。
        """
        n = self._check_ch(ch)
        want = {k: v for k, v in (("scale", scale), ("offset", offset),
                                  ("coupling", coupling), ("probe", probe),
                                  ("display", display)) if v is not None}
        before = self._chan_state(n)
        if not want:
            return {"ch": n, "requested": {}, "before": before, "actual": before,
                    "adjusted": None, "reasons": [], "window": self.vertical_window(n)}
        reasons: list[str] = []
        vertical = scale is not None or offset is not None
        if vertical and not before["display"] and display is not False:
            self.channel_display(n, True)   # ① 否则后续 SCALe/OFFSet 写入被静默忽略
            reasons.append("通道原为 OFF，已先开启"
                           "（OFF 状态下 SCALe/OFFSet 写入会被设备静默忽略）")
        if coupling is not None:
            self.channel_coupling(n, coupling)
        if probe is not None:
            self.channel_probe(n, probe)
        if scale is not None:
            self.channel_scale(n, scale)    # ② 必须先 scale：设备会按新档位等比缩放旧 offset
        if offset is not None:
            self.channel_offset(n, offset)
        if display is not None:
            self.channel_display(n, bool(display))

        actual = self._chan_state(n)
        adjusted: dict = {}
        # ③ 回读比对（设备会量化/吸附/钳制，容差比较）
        for key, got, want_v in (("scale", actual["scale_v_div"], scale),
                                 ("offset", actual["offset_v"], offset),
                                 ("probe", actual["probe_x"], probe)):
            if want_v is None or got is None:
                continue
            if abs(float(got) - float(want_v)) > max(tol, abs(float(want_v)) * 0.02):
                adjusted[key] = {"requested": want_v, "actual": got}
                self._explain(key, float(want_v), float(got), reasons)
        if coupling is not None and actual["coupling"]:
            if not str(actual["coupling"]).upper().startswith(str(coupling).upper()[:3]):
                reasons.append(f"耦合未生效：要求 {coupling}，回读 {actual['coupling']}")
        if display is not None and actual["display"] != bool(display):
            reasons.append(f"显示开关未生效：要求 {bool(display)}，回读 {actual['display']}")
        if (scale is not None and offset is None
                and before["offset_v"] is not None and actual["offset_v"] is not None
                and abs(actual["offset_v"] - before["offset_v"]) > tol):
            reasons.append(
                f"偏置被设备等比缩放：{before['offset_v']:g} → {actual['offset_v']:g} V"
                "（改 SCALe 会按新档位缩放 offset 以保持波形屏幕位置，属设备行为；"
                "要固定偏置请在写档位后**显式再写 offset**）")
        return {"ch": n, "requested": want, "before": before, "actual": actual,
                "adjusted": adjusted or None, "reasons": reasons,
                "window": self.vertical_window(n)}

    def configure_timebase(self, scale: Optional[float] = None,
                           offset: Optional[float] = None) -> dict:
        """设置水平时基并回读（**两个都回读**——只回读被写的那一个等于没回读）。"""
        before = {"scale_s_div": self.timebase_scale(), "offset_s": self.timebase_offset()}
        if scale is not None:
            self.timebase_scale(scale)
        if offset is not None:
            self.timebase_offset(offset)
        actual = {"scale_s_div": self.timebase_scale(), "offset_s": self.timebase_offset()}
        adjusted, reasons = {}, []
        for key, want_v in (("scale_s_div", scale), ("offset_s", offset)):
            got = actual[key]
            if want_v is None or got is None:
                continue
            if abs(got - float(want_v)) > max(1e-12, abs(float(want_v)) * 0.02):
                adjusted[key] = {"requested": want_v, "actual": got}
                reasons.append(f"{key} 未精确生效：要求 {want_v:g}，回读 {got:g}")
        return {"requested": {k: v for k, v in (("scale_s_div", scale),
                                               ("offset_s", offset)) if v is not None},
                "before": before, "actual": actual,
                "adjusted": adjusted or None, "reasons": reasons,
                "window_t": self.horizontal_window()}

    @staticmethod
    def _same_mnemonic(a: Optional[str], b: str) -> bool:
        """SCPI 短/长形式对比（设备回短格式：NORM 对 NORMal、CHAN1 对 CHANnel1）。"""
        if not a:
            return False
        x, y = a.strip().upper(), b.strip().upper()
        return x.startswith(y[:4]) or y.startswith(x[:4]) or x[:4] == y[:4]

    def configure_trigger(self, source: Optional[int] = None, slope: Optional[str] = None,
                          level: Optional[float] = None, mode: Optional[str] = None,
                          sweep: Optional[str] = None) -> dict:
        """设置触发（源/斜率/电平/模式/扫描）并回读；枚举非法值直接拒绝（对照手册）。"""
        if mode is not None and mode.upper() not in [m.upper() for m in self.family.trigger_types]:
            raise ValueError(f"invalid trigger mode: {mode!r}（可选 {self.family.trigger_types}）")
        if sweep is not None and sweep.upper() not in [s.upper() for s in self.family.trigger_sweeps]:
            raise ValueError(f"invalid sweep: {sweep!r}（可选 {self.family.trigger_sweeps}）")
        if slope is not None and slope.upper() not in [s.upper() for s in self.family.edge_slopes]:
            raise ValueError(f"invalid slope: {slope!r}（可选 {self.family.edge_slopes}）")
        src_name = f"CHANnel{self._check_ch(source)}" if source is not None else None
        before = {"mode": self.trigger_mode(), "sweep": self.sweep(),
                  "edge_source": self.edge_source(), "edge_slope": self.edge_slope(),
                  "edge_level_v": self.edge_level()}
        if mode is not None:
            self.trigger_mode(mode)
        if sweep is not None:
            self.sweep(sweep)
        self.edge_trigger(source=source, slope=slope, level=level)
        actual = {"mode": self.trigger_mode(), "sweep": self.sweep(),
                  "edge_source": self.edge_source(), "edge_slope": self.edge_slope(),
                  "edge_level_v": self.edge_level()}
        adjusted, reasons = {}, []
        if mode is not None and not self._same_mnemonic(actual["mode"], mode):
            adjusted["mode"] = {"requested": mode, "actual": actual["mode"]}
            reasons.append(f"触发模式未生效：要求 {mode}，回读 {actual['mode']}")
        if sweep is not None and not self._same_mnemonic(actual["sweep"], sweep):
            adjusted["sweep"] = {"requested": sweep, "actual": actual["sweep"]}
            reasons.append(f"触发扫描未生效：要求 {sweep}，回读 {actual['sweep']}")
        if source is not None and not self._same_mnemonic(actual["edge_source"], src_name):
            adjusted["source"] = {"requested": src_name, "actual": actual["edge_source"]}
            reasons.append(f"触发源未生效：要求 {src_name}，回读 {actual['edge_source']}")
        if slope is not None and not self._same_mnemonic(actual["edge_slope"], slope):
            adjusted["slope"] = {"requested": slope, "actual": actual["edge_slope"]}
            reasons.append(f"触发斜率未生效：要求 {slope}，回读 {actual['edge_slope']}")
        if (level is not None and actual["edge_level_v"] is not None
                and abs(actual["edge_level_v"] - float(level)) > max(0.02, abs(float(level)) * 0.02)):
            adjusted["level"] = {"requested": level, "actual": actual["edge_level_v"]}
            win = self.vertical_window(source) if source is not None else None
            extra = (f"；该通道窗口 [{win['bottom_v']:.3g}, {win['top_v']:.3g}] V"
                     if win else "")
            reasons.append(f"触发电平未生效：要求 {level:g} V，回读 {actual['edge_level_v']:g} V{extra}")
        return {"requested": {k: v for k, v in (("source", src_name), ("slope", slope),
                                               ("level", level), ("mode", mode),
                                               ("sweep", sweep)) if v is not None},
                "before": before, "actual": actual,
                "adjusted": adjusted or None, "reasons": reasons}

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

    # ---------- 读数可信度 / 自动定标 ----------
    # 现场教训（tool_optimization §P1-4 / §P2-5）：单次读数抖动大、且"无有效值"
    # 把三种完全不同的原因混成一句话，误导排查方向。这里把它们分开。

    def measure_stats(self, item: str, src: Union[int, str] = 1,
                      src2: Optional[Union[int, str]] = None, samples: int = 5,
                      interval_s: float = 0.05) -> dict:
        """主机侧连读 N 次给统计量（无设备侧统计命令时的通用做法）。

        无效读数（9.9E37）单独计数、不混进统计；全无效时抛 ValueError（带最后一次原因）。
        现场依据：同一状态连读三次 7.4747/7.4749/7.4749 V —— 结论要用均值，不是单次读数。
        """
        n = int(samples)
        if not 1 <= n <= 200:
            raise ValueError(f"samples 需在 1~200（给 {samples}）")
        if n == 1:
            return {"item": item, "source": self._norm_source(src), "samples": 1,
                    "count": 1, "invalid": 0,
                    "mean": self.measure_item(item, src, src2),
                    "min": None, "max": None, "stddev": None, "values": None}
        vals: list[float] = []
        invalid, last_err = 0, None
        for i in range(n):
            try:
                vals.append(self.measure_item(item, src, src2, open_measurement=(i == 0)))
            except ValueError as e:
                invalid += 1
                last_err = str(e)[:120]
            if i != n - 1:
                time.sleep(max(0.0, interval_s))
        if not vals:
            raise ValueError(f"{item} 连续 {n} 次均无有效值（invalid={invalid}）：{last_err}")
        mean = sum(vals) / len(vals)
        var = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) if len(vals) > 1 else 0.0
        return {"item": item, "source": self._norm_source(src), "samples": n,
                "count": len(vals), "invalid": invalid, "mean": mean,
                "min": min(vals), "max": max(vals), "stddev": math.sqrt(var),
                "values": vals[:12], "values_truncated": len(vals) > 12,
                "probe_x": self.channel_probe(int(src)) if str(src).strip().isdigit() else None}

    def rails(self, ch: int, band: float = 0.08) -> dict:
        """读**顶轨/底轨**（VTOP/VBASe）并分别判断是否贴窗口边沿（削顶）。

        现场依据（tool_optimization §P1-4 / §2.7）：部分削顶时测量值可能是"看着合理的
        假值"，而**顶轨与底轨要分开看**——只顶上削 vs 只底下削，处理方式不同
        （顶贴：偏置调更负或放大 scale；底贴：偏置调更大或放大 scale）。
        `band` 是"贴边判定带"（占窗口高度的比例，默认 8%）。
        返回 {vtop, vbase, vmax, vmin, vpp, top_touching, bottom_touching,
              edges_touching, window, hints}；无窗口标定的家族不给贴边判定（None）。
        """
        n = self._check_ch(ch)
        out: dict = {"ch": n, "window": self.vertical_window(n),
                     "top_touching": None, "bottom_touching": None,
                     "edges_touching": [], "hints": []}
        for key, it in (("vtop", "VTOP"), ("vbase", "VBASe"),
                        ("vmax", "VMAX"), ("vmin", "VMIN")):
            try:
                out[key] = self.measure_item(it, n)
            except ValueError:
                out[key] = None
        if out["vtop"] is not None and out["vbase"] is not None:
            out["vpp"] = out["vtop"] - out["vbase"]
        elif out["vmax"] is not None or out["vmin"] is not None:
            # 电平类测量（VTOP/VBASe）需要可辨识的顶端/底端——对"带噪声的直流"设备
            # 会给 9.9E37（2026-09-16 实机：CH3 的 3.29 V 直流，VTOP/VBASe 恒无值，
            # 而 VMAX/VMIN 稳得很）。贴边判定已按 VMAX/VMIN 做，这里如实说明。
            out["note_vtop"] = ("VTOP/VBASe 无有效值（电平类测量需顶端/底端可辨识），"
                                "贴边判定已用极值 VMAX/VMIN")
        w = out["window"]
        if not w:
            out["note"] = "该家族未标定垂直格数/中心约定 → 不做贴边判定（不猜）"
            return out
        half_band = band * w["height_v"]
        top_val = out["vmax"] if out["vmax"] is not None else out["vtop"]
        bot_val = out["vmin"] if out["vmin"] is not None else out["vbase"]
        # 单端**极值完全不可测** = 该端已在窗外（2026-09-16 实机行为：把窗口上沿压进
        # 信号里时 VMAX 直接回 9.9E37 而不是给"钳制假值"，同时 VMIN 仍有效）——
        # 这比"贴边"更强：不是"可能被削"，而是"这一端已经看不到"。
        top_out = out["vmax"] is None and (out["vmin"] is not None or out["vbase"] is not None)
        bot_out = out["vmin"] is None and (out["vmax"] is not None or out["vtop"] is not None)
        if top_out or (top_val is not None and top_val >= w["top_v"] - half_band):
            out["top_touching"] = True
            out["edges_touching"].append("top")
            if top_out:
                out["top_out_of_window"] = True
            got = (f"顶端极值不可测（VMAX 回 9.9E37）→ **顶端已在窗外**"
                   if top_out else f"VMAX {top_val:.4g} V 贴住上沿 {w['top_v']:.4g} V")
            out["hints"].append(
                f"**顶轨出窗/贴边**（{got}）：把 offset 调**更负**（中心 −offset 上移）"
                f"或放大 scale（当前 {w['scale_v_div']:g} V/div）")
        else:
            out["top_touching"] = False
        if bot_out or (bot_val is not None and bot_val <= w["bottom_v"] + half_band):
            out["bottom_touching"] = True
            out["edges_touching"].append("bottom")
            if bot_out:
                out["bottom_out_of_window"] = True
            got = (f"底端极值不可测（VMIN 回 9.9E37）→ **底端已在窗外**"
                   if bot_out else f"VMIN {bot_val:.4g} V 贴住下沿 {w['bottom_v']:.4g} V")
            out["hints"].append(
                f"**底轨出窗/贴边**（{got}）：把 offset 调**更大**（中心 −offset 下移）"
                f"或放大 scale（当前 {w['scale_v_div']:g} V/div）")
        else:
            out["bottom_touching"] = False
        if out["top_touching"] is False and out["bottom_touching"] is False                 and out["vmax"] is None and out["vmin"] is None and out["vtop"] is None                 and out["vbase"] is None:
            # 实机（2026-09-16 CH3）：把窗口上沿压进信号里后，**极值与轨值全回 9.9E37**
            # （而 VAVG 仍给 2.4855 V 的"看着合理的假值"，真实 3.29 V）——这种状态必须
            # 明确报"无法判定"，不能给出空的 edges 让人以为"没问题"。
            out["top_touching"] = out["bottom_touching"] = None
            out["unreadable"] = True
            out["hints"].append(
                "极值与顶/底轨**全部不可测**（9.9E37）：迹线很可能已整体出窗或被削顶，"
                "无法分端判定——先放大 scale 让窗口变宽（或调 offset）再看；"
                "⚠ 此时 VAVG 等读数可能是**看着合理的假值**，不要采信")
            if w:
                out["hint_window"] = (f"当前窗口 [{w['bottom_v']:.4g}, {w['top_v']:.4g}] V，"
                                      f"中心 −offset = {w['center_v']:.4g} V")
        return out

    def measure_retry(self, item: str, src: Union[int, str] = 1,
                      src2: Optional[Union[int, str]] = None,
                      tries: int = 3, delay: float = 0.25) -> float:
        """测量重试——**现场实测**：偶发返回 9.9E37 而面板其实有值，重读即正常
        （`docs/tool_optimization_20260915.md` §2.9；2026-09-16 复现：恢复设定后
        第一次读 VAVG 就是 9.9E37，紧接着再读有效）。全部失败才抛最后一次的异常。
        """
        last: Optional[Exception] = None
        for i in range(max(1, tries)):
            try:
                return self.measure_item(item, src, src2)
            except ValueError as e:
                last = e
                if i != tries - 1:
                    time.sleep(delay)
        raise last  # type: ignore[misc]

    def diagnose_no_reading(self, item: str, src: Union[int, str] = 1) -> dict:
        """无有效值（9.9E37）时的**原因分类**——不把三种原因混成一句话。

        suspicious 取值：channel_off（通道显示关）/ off_screen（迹线在窗口外）/
        near_edge（极值贴窗口边沿 → 可能是"看着合理的假值"，必须换档）/
        few_edges（屏内不足 2 个周期，时间/边沿类测量）/ no_signal。
        返回里带 window（由 scale/offset/格数算出）与 evidence（逐条原始响应）；
        `near_edge` 时另给 **`edges_touching`（["top"]/["bottom"]/两者）与 `hints`**——
        顶轨/底轨分开提示，因为处理方向相反。
        ⚠ 诊断会临时打开 VMAX/VMIN/VTOP/VBASe 测量项（与 mho_measure_item 的行为一致）。
        """
        n: Optional[int] = None
        s = self._norm_source(src)
        if s.upper().startswith("CHAN"):
            digits = "".join(ch for ch in s if ch.isdigit())
            n = int(digits) if digits else None
        evidence: dict = {"item": item, "source": s}
        window = self.vertical_window(n) if n else None
        if n is not None and not self.channel_display(n):
            return {"suspicious": "channel_off", "channel": n, "window": window,
                    "hint": f"CH{n} 显示为 OFF——通道未开启时没有波形可测",
                    "evidence": evidence}
        vmax = vmin = None
        if n is not None:
            for key, it in (("vmax", "VMAX"), ("vmin", "VMIN")):
                try:
                    val = self.measure_item(it, n)
                except ValueError as e:
                    evidence[key + "_error"] = str(e)[:100]
                    val = None
                evidence[key] = val
                if key == "vmax":
                    vmax = val
                else:
                    vmin = val
        # 两端都不可测 → 离屏（先判，避免被下面的"单端出窗"抢走）
        if window and vmax is None and vmin is None:
            return {"suspicious": "off_screen", "channel": n, "window": window,
                    "hint": (f"极值与 {item} 均无有效值：迹线很可能在屏幕外。当前窗口 "
                             f"[{window['bottom_v']:.3g}, {window['top_v']:.3g}] V"
                             f"（中心 −offset = {window['center_v']:.3g} V）——"
                             "放大 scale 让窗口变宽，或调 offset 把信号移进窗"),
                    "evidence": evidence}
        if window and (vmax is not None or vmin is not None):
            band = 0.08 * window["height_v"]
            # 单端极值不可测 = 该端已在窗外（实机行为，见 rails() 同款说明）
            top_touch = (vmax is None) or (vmax >= window["top_v"] - band)
            bot_touch = (vmin is None) or (vmin <= window["bottom_v"] + band)
            if top_touch or bot_touch:
                which = ("顶轨与底轨**两端**" if (top_touch and bot_touch)
                         else ("**顶轨**（上沿）" if top_touch else "**底轨**（下沿）"))
                hints: list[str] = []
                if top_touch:
                    # 单端极值不可测 = 该端已在窗外（实机行为，别拿 None 去格式化）
                    got = ("顶端极值不可测（VMAX 回 9.9E37）→ 顶端已在窗外"
                           if vmax is None else
                           f"VMAX {vmax:.4g} V 贴/出窗口上沿 {window['top_v']:.4g} V")
                    hints.append(f"顶端：{got} → "
                                 "offset 调**更负**（中心 −offset 上移）或放大 scale")
                if bot_touch:
                    got = ("底端极值不可测（VMIN 回 9.9E37）→ 底端已在窗外"
                           if vmin is None else
                           f"VMIN {vmin:.4g} V 贴/出窗口下沿 {window['bottom_v']:.4g} V")
                    hints.append(f"底端：{got} → "
                                 "offset 调**更大**（中心 −offset 下移）或放大 scale")
                # 顶/底轨读数一并放进证据（顶轨=VTOP、底轨=VBASe；削顶时它们才是"被切掉的那一端"）
                for key, it in (("vtop", "VTOP"), ("vbase", "VBASe")):
                    try:
                        evidence[key] = self.measure_item(it, n)
                    except ValueError as e:
                        evidence[key + "_error"] = str(e)[:80]
                return {"suspicious": "near_edge", "channel": n, "window": window,
                        "edges_touching": [e for e, t in (("top", top_touch),
                                                          ("bottom", bot_touch)) if t],
                        "edge_hints": hints,
                        "hint": (f"{which}极值贴到窗口边沿（±8% 带内）：**部分削顶时测量值可能是"
                                 f"\"看着合理的假值\"**，必须换档重测（当前窗口 "
                                 f"[{window['bottom_v']:.3g}, {window['top_v']:.3g}] V）"),
                        "evidence": evidence}
        if item in EDGE_DEPENDENT_ITEMS:
            hw = self.horizontal_window()
            need = (f"（时间窗 {hw['span_s']:.3g} s/屏，{hw['note']}）" if hw else "")
            return {"suspicious": "few_edges", "channel": n, "window": window,
                    "window_t": hw,
                    "hint": f"{item} 需要屏内 ≥2 个边沿{need}——放宽时基（增大 s/div）再测；"
                            "现场实例：20 µs/div 看 5 kHz 读不到，100 µs/div 立刻读到 4.9993 kHz",
                    "evidence": evidence}
        return {"suspicious": "no_signal" if vmax is None else "unexplained",
                "channel": n, "window": window,
                "hint": "通道已开、读数无效：确认信号接在该通道、触发在跑（截图看形态最直观）",
                "evidence": evidence}

    def _probe_warning(self, n: int) -> list[str]:
        """探头比是隐性口径（幅度类读数差 10×，频率不受影响）——非 1X 时提示。"""
        x = self.channel_probe(n)
        if x and abs(x - 1.0) > 1e-9:
            return [f"CH{n} 探头比 {x:g}X：幅度/触发电平类读数为**探头端**电压，"
                    "频率不受影响"]
        return []

    def fit_channel(self, ch: int, occupancy: float = 0.7, margin: float = 0.08,
                    max_iter: int = 12) -> dict:
        """单通道垂直自动定标/居中——**只动该通道的 scale/offset**（不是全局 AUToset）。

        判据（设计文档 §1）：① 可测（非 9.9E37）② 不贴边（margin 带）③ 占屏率 ∈ [0.4, 0.9]。
        算法（同文档 §2）：通道必须已开 → 不可测/贴边则沿 1-2-5 逐档放大 →
        `scale = span/(occupancy×格数)`、`offset = −中心` → **先 scale 后 offset** 写回 →
        重测验证。平直信号判"平直"并**保持档位**（不猜）；偏置超量程/未收敛如实报，不假装成功。
        """
        n = self._check_ch(ch)
        fam = self.family
        if fam.vdivs is None:
            raise ValueError(f"{fam.label} 的垂直格数与中心约定未实测标定，不能自动定标"
                             "（设计文档 §5：不要照抄别家族的值）")
        if not self.channel_display(n):
            raise RuntimeError(
                f"CH{n} 显示为 OFF：通道关闭时档位/偏置写入会被静默忽略，"
                f"请先开启（configure_channel(ch={n}, display=True)）再定标")
        vdivs = fam.vdivs
        before = self._chan_state(n)
        trace: list[dict] = []
        vmax = vmin = None
        converged = False
        for i in range(max(1, int(max_iter))):
            scale_now = self.channel_scale(n)
            err = None
            try:
                vmax = self.measure_retry("VMAX", n)
                vmin = self.measure_retry("VMIN", n)
            except ValueError as e:
                err = str(e)[:100]
            win = self.vertical_window(n)
            trace.append({"iter": i + 1, "scale_v_div": scale_now, "vmax": vmax,
                          "vmin": vmin, "error": err})
            if err is None and win:
                band = margin * win["height_v"]
                if vmax < win["top_v"] - band and vmin > win["bottom_v"] + band:
                    converged = True
                    break
            nxt = snap_up(scale_now, fam.scale_range[1] if fam.scale_range else None)
            if nxt is None:
                return {"ch": n, "ok": False, "reason": "超出可测范围",
                        "note": "逐档放大到最大档仍不可测——信号超出量程或没有信号；"
                                "物理上无法从被削掉的波形里恢复真实幅度",
                        "before": before, "after": self._chan_state(n),
                        "reasons": [], "adjusted": None, "measurements": None,
                        "occupancy": None, "margin_ok": None,
                        "trace": trace, "warnings": self._probe_warning(n)}
            # 保持**窗口中心不变**地变宽：只写 SCALe 时设备会等比缩放 offset
            # （保持波形屏幕位置），那会让窗口随档位一起"漂走"、永远追不上信号——
            # 2026-09-16 实机踩到：中心 1 V、信号 3.3 V，一路抬到 10 V/div 反而跑到
            # 中心 100 V，最后误报"超出可测范围"。故抬档后把偏置写回原值。
            off_keep = self.channel_offset(n)
            self.channel_scale(n, nxt)
            if off_keep is not None:
                self.channel_offset(n, off_keep)
        if not converged:
            return {"ch": n, "ok": False, "reason": f"未收敛（迭代上限 {max_iter}）",
                    "before": before, "after": self._chan_state(n), "reasons": [],
                    "adjusted": None, "measurements": None, "occupancy": None,
                    "margin_ok": None, "trace": trace,
                    "warnings": self._probe_warning(n)}
        win = self.vertical_window(n)
        lsb = (win["height_v"] / float(2 ** fam.adc_bits)) if (win and fam.adc_bits) else 0.0
        span = float(vmax) - float(vmin)
        flat = span < max(3.0 * lsb, 1e-12)
        note = None
        if flat:
            target_scale = win["scale_v_div"]        # 平直：保持档位，不猜
            note = ("平直/无信号：保持当前档位、按均值居中（**不猜档位**——猜了就是假精度；"
                    "需要更细量程请显式设 scale）")
        else:
            target_scale = snap_1_2_5(span / (float(occupancy) * vdivs))
        offset_target = -(float(vmax) + float(vmin)) / 2.0
        applied = self.configure_channel(n, scale=target_scale, offset=offset_target)
        # 偏置量程**随档位变**（2026-09-16 实机实测：0.05 V/div 只允许 ±1 V）——
        # 目标偏置放不下时把档位**逐档抬高**（窗口与偏置量程同时变大），闭环探测，
        # 不写死阶梯表（换句话说：以设备回读为准，而不是以我们的假设为准）。
        raised = 0
        while ((applied.get("adjusted") or {}).get("offset")) and raised < 6:
            cur = applied["actual"]["scale_v_div"]
            nxt = snap_up(cur, fam.scale_range[1] if fam.scale_range else None)
            if nxt is None or nxt <= cur:
                break
            print(f"[fit_channel] 偏置被钳制（{offset_target:g} V 放不下 {cur:g} V/div）"
                  f"→ 抬档到 {nxt:g} V/div 重试", file=sys.stderr)
            applied = self.configure_channel(n, scale=nxt, offset=offset_target)
            raised += 1
        applied["scale_raised_for_offset_limit"] = raised
        if (applied.get("adjusted") or {}).get("offset"):
            got = applied["adjusted"]["offset"]["actual"]
            applied["offset_limit_v"] = abs(got)
            applied["reasons"].append(
                f"偏置量程不足：该档位只能设到 {got:g} V，"
                "已抬档仍放不下目标偏置——请改用更大的 scale 或接受偏移的窗口")
        time.sleep(0.2)                              # 等设备重算测量
        out: dict = {"ch": n, "flat": flat, "before": before,
                     "requested": applied["requested"], "after": applied["actual"],
                     "adjusted": applied["adjusted"], "reasons": applied["reasons"],
                     "scale_raised_for_offset_limit": applied.get("scale_raised_for_offset_limit"),
                     "offset_limit_v": applied.get("offset_limit_v"),
                     "window": self.vertical_window(n), "trace": trace,
                     "warnings": self._probe_warning(n)}
        if note:
            out["note"] = note
        occ = margin_ok = None
        try:
            vmax2 = self.measure_retry("VMAX", n)
            vmin2 = self.measure_retry("VMIN", n)
            w2 = self.vertical_window(n)
            out["measured"] = {"vmax": vmax2, "vmin": vmin2, "vpp": vmax2 - vmin2}
            if w2 and w2["height_v"]:
                occ = (vmax2 - vmin2) / w2["height_v"]
                band = margin * w2["height_v"]
                margin_ok = bool(vmax2 < w2["top_v"] - band and vmin2 > w2["bottom_v"] + band)
            out["occupancy"] = occ
            out["margin_ok"] = margin_ok
            out["ok"] = bool(margin_ok and (flat or (occ is not None and 0.4 <= occ <= 0.9)))
        except ValueError as e:
            out["ok"] = False
            out["verify_error"] = str(e)[:140]
        if not out["ok"] and "reason" not in out:
            detail = (f"占屏率 {occ:.3g}" if occ is not None else "无有效读数")
            if out.get("scale_raised_for_offset_limit"):
                detail += (f"；因偏置量程已抬档 {out['scale_raised_for_offset_limit']} 次"
                           f"（当前档位上限 ±{(out.get('offset_limit_v') or 0):g} V）")
            out["reason"] = (f"定标后仍未达标（{detail}；目标 [0.4,0.9]）——偏置量程限制了"
                             "可居中范围，或信号本身占不满屏（平直/小纹波）")
        return out

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
        """`:DISPlay:DATA? <fmt>` 截屏原始字节（剥 TMC 头）；fmt: BMP|PNG|JPG。

        ⚠ 用 `query_block()` **把大块读完**（而不是单次 read_raw）：整屏 PNG 约 97 KB，
        在 **raw socket** 上会按 TCP 分段到达，单次读只拿到几字节
        （2026-09-17 实测：`TMC 数据不完整: 期望 97471 字节，实得 6`）；
        VXI-11 因有消息分帧才一直没暴露这个问题。
        """
        f = fmt.upper()
        if f not in [x.upper() for x in self.family.disp_formats]:
            raise ValueError(f"不支持的截图格式 {fmt!r}（{'|'.join(self.family.disp_formats)}）")
        data = self._c().query_block(f":DISPlay:DATA? {f}")
        return data

    def screenshot_png(self, save_path: Path) -> Path:
        """截屏存 PNG，返回路径（**该 PNG 可直接读图**，用于判断波形形态/削顶/居中）。"""
        data = self.screenshot("PNG")
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(data)
        return save_path

    # ---------- 快照 ----------
    def snapshot(self) -> dict:
        """只读快照（不改动设备配置）。

        每通道在档位/偏置之外**附算** `center_v = −offset` 与 `window_v`
        （中心 = −offset 是实测标定的设备约定，见 `configure_channel` 类内说明）；
        格数未标定的家族（DHO）不附算——宁可没有，不给错的。
        """
        chans = {}
        for ch in range(1, self.family.channels + 1):
            try:
                c = {
                    "display": self.channel_display(ch),
                    "coupling": self.channel_coupling(ch),
                    "scale_v_div": self.channel_scale(ch),
                    "offset_v": self.channel_offset(ch),
                    "probe_x": self.channel_probe(ch),
                }
                if self.family.vdivs and c["scale_v_div"] is not None and c["offset_v"] is not None:
                    half = self.family.vdivs / 2.0 * c["scale_v_div"]
                    c["center_v"] = -c["offset_v"]
                    c["window_v"] = [round(-c["offset_v"] - half, 9),
                                     round(-c["offset_v"] + half, 9)]
                if c["probe_x"] not in (None, 1.0) and c["probe_x"] is not None:
                    c["probe_note"] = f"探头比 {c['probe_x']:g}X（幅度类读数为探头端电压）"
                chans[f"ch{ch}"] = c
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
            "timebase_window_t": self.horizontal_window(),
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
