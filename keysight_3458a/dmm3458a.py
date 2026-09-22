"""HP/Keysight 3458A 八位半万用表驱动（**专用实现**，不套 SCPI 假设）。

与 `keysight_3446x.DMM`（34465A，标准 SCPI）的关键差异：

    - 身份用 `ID?`（无 `*IDN?`）、错误用 `ERRSTR?`（无 `SYST:ERR?`）、复位用 `RESET`；
    - 单次读数是 `TARM SGL,1` 触发后直接回值（命令不带问号）；
    - 档位/NPLC 用 `DCV <range>` / `NPLC <n>`，且**没有档位回读命令**——
      驱动只能记录"本会话设过什么"，不能问设备"你现在是几档"（如实报告，不猜）；
    - 高速采样走 `PRESET DIG` + SINT 二进制突发（2 字节大端有符号 × ISCALE）。

三条来自参考实现（EmoeCalibrator）的硬性经验，已固化在下面各方法里：

    1. **换档/换配置后必须丢弃第一次读数**（建立时间 + 自校准，[SICL] L339-341）；
    2. **会话恢复要先 IFC/clear 再有限 drain**，否则 free-run 的表能把你读到 91 s（[SICL] L273-276）；
    3. `RESET` 之后要补 `END ALWAYS` + `INBUF ON`，否则 `TARM SGL` 会占住 GPIB 总线（[VISA] L571-576）。

连接**默认不改设备状态**（`reset_on_open=False`）：MCP 是无状态工具，不该每次
RESET 仪表。要重置另走显式 `reset()`（MCP `ks3458a_reset` 需 confirm=True）。
"""
from __future__ import annotations

import re
import time
from typing import Optional

from . import commands as C
from .transport import (
    DRAIN_MAX_ROUNDS,
    DRAIN_TIMEOUT_MS,
    Transport,
    TransportError,
    make_transport,
)


def _first_float(text: str) -> float:
    """从响应里取第一个数值（`'1.4E-07'` / `'-5.23E-05 VDC'` → float）。

    3458A 的响应可能带单位后缀或前导状态字段，取第一个可解析数字比整体 `float()` 稳
    （与 `keysight_3446x.dmm._num` 同口径）。没有数字就报错，**不返回 0 兜底**。
    """
    match = re.search(r"[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?", text or "")
    if match is None:
        raise TransportError(f"响应里没有可解析的数值: {text!r}")
    return float(match.group().replace("D", "E").replace("d", "e"))


def _safe_float(text) -> Optional[float]:
    """尽力把响应转 float；失败返回 None（状态回读用：单项失败不该毁整次查询）。"""
    if text is None:
        return None
    try:
        return _first_float(str(text))
    except Exception:                                # noqa: BLE001
        return None


def _check_range(dcv_range) -> float:
    """档位必须落在 3458A 的直流电压档位全集内（[SICL] L248）。"""
    value = float(dcv_range)
    for allowed in C.DCV_RANGES:
        if abs(value - allowed) < 1e-9:
            return allowed
    raise ValueError(
        f"不支持的档位 {dcv_range!r}；3458A 直流电压档位只有 {list(C.DCV_RANGES)} V")


def _check_nplc(nplc) -> float:
    """NPLC 必须为正数。**上限不做猜测**：交给设备判（报了错用 `ERRSTR?` 看）。"""
    value = float(nplc)
    if not value > 0:
        raise ValueError(f"NPLC 必须 > 0，收到 {nplc!r}")
    return value


def _stats(values: list[float]) -> dict:
    """均值 / 样本标准差 / 极值（n=1 时标准差记 0.0，与参考实现一致）。"""
    count = len(values)
    mean = sum(values) / count
    if count > 1:
        stddev = (sum((v - mean) ** 2 for v in values) / (count - 1)) ** 0.5
    else:
        stddev = 0.0
    return {"n": count, "mean": mean, "stddev": stddev,
            "min": min(values), "max": max(values)}


def is_error_clear(errtxt: str) -> bool:
    """`ERRSTR?` 响应是否表示"无错误"（形如 `0,"NO ERROR"`）。

    判据只看**错误码部分是否为 0**（不认措辞，措辞因固件而异）。解析不出来时返回
    False——拿不准就当有错报给调用方看原文，不替它下结论。

    ⚠ 3458A 的错误队列语义（是否弹出一条、队列深度、如何清空）**待手册核对**，
    见 `docs/COMMANDS_3458A.md`。
    """
    match = re.match(r"\s*([+-]?\d+)\s*,", errtxt or "")
    return bool(match) and int(match.group(1)) == 0


class DMM3458A:
    """3458A 会话（connect → 配置/读数 → close）。

    用法::

        with DMM3458A("GPIB0::9::INSTR") as d:      # 或 "sicl:gpib0,9"
            print(d.idn())                          # HP3458A
            d.configure_dcv(10.0, 10.0)             # 10V 档 / 10 PLC（换档后丢首读数）
            print(d.read_dcv())

    离线测试/自定义传输：给 `transport=` 一个实现 `transport.Transport` 的对象，
    此时 `resource` 可为 None（**不会**打开任何真实设备）。
    """

    def __init__(self, resource: Optional[str] = None, timeout_s: float = 30.0,
                 dcv_range: float = 10.0, nplc: float = 10.0,
                 reset_on_open: bool = False,
                 transport: Optional[Transport] = None):
        self.resource = resource
        self.timeout_s = float(timeout_s)
        self.dcv_range = _check_range(dcv_range)     # 期望档位（configure 时下发）
        self.nplc = _check_nplc(nplc)
        # MCP 路径必须保持 False：无状态工具不该每次调用都 RESET 仪表
        self.reset_on_open = bool(reset_on_open)
        self._transport = transport
        self._connected = False
        self._range: Optional[float] = None          # 本会话已下发过的档位（None=没设过）
        self._nplc: Optional[float] = None           # 本会话已下发过的 NPLC（None=没设过）

    # ---------- 连接 ----------
    def connect(self, recover: bool = True) -> str:
        """打开会话，返回资源串（与 keysight_3446x / rigol_scope 的 connect 一致）。

        `recover=True`（默认）先做一次**会话恢复**：上次会话可能把表留在 free-run
        （持续吐读数、不理查询），不恢复就会读到错位数据。恢复只发 IFC/clear +
        TARM HOLD/TRIG HOLD + 有限 drain，**不发 RESET、不改档位/NPLC**。

        ⚠ SICL 通路的 IFC 会中断**整条 GPIB 总线**上的活动（同总线的其它设备也受影响，
        本机 GPIB0 上只有这台 3458A）；共享实验台上别人正在采集时要注意——见 README。

        `reset_on_open=True` 时额外 `reset()` + 按构造参数配置档位/NPLC（**破坏性**）。
        """
        if self._transport is None:
            if not self.resource:
                raise ValueError(
                    "resource 为空：需要 GPIB/VISA/SICL 资源串，"
                    "如 'GPIB0::9::INSTR' / 'visa://<host>/GPIB0::9::INSTR' / 'sicl:gpib0,9'")
            self._transport = make_transport(self.resource, timeout_s=self.timeout_s)
        self._transport.open()
        self._connected = True
        if recover:
            self.recover()
        if self.reset_on_open:
            self.reset()
            self.configure_dcv(self.dcv_range, self.nplc)
        else:
            # 没 RESET 时，recover() 会把触发挂起（TRIG HOLD）——而 `TARM SGL,1`
            # 需要一个可用的触发源，否则读数永远不产生。
            # 2026-09-23 本机实测：TRIG? = 4(HOLD) 时 `TARM SGL,1` 20 s 超时；
            # 补发 `TRIG AUTO` 后立刻出数（0.43 s/次 @NPLC=10）。这里按需准备。
            self.prepare_for_read()
        return self.resource

    def prepare_for_read(self) -> None:
        """`TARM SGL` 单次读数配方的**前置准备**（不改档位/NPLC/功能）。

        发 `END ALWAYS` + `INBUF ON`（手册 TARM 章节要求，缺了会占住 GPIB 总线）+
        `TRIG AUTO`（恢复自动触发源）。参考实现走的是 `RESET`——`RESET` 会把触发源
        复位成 AUTO；我们为了不动用户设定不发 `RESET`，所以在这里显式补上。
        """
        transport = self._t()
        transport.write(C.END_ALWAYS)
        transport.write(C.INBUF_ON)
        transport.write(C.TRIG_AUTO)
        time.sleep(0.2)

    def close(self) -> None:
        """关会话。先尽力把触发挂起（`TARM HOLD`），不把表留在"等待触发"的悬空态。"""
        transport = self._transport
        if transport is None:
            return
        try:
            transport.write(C.TARM_HOLD)
        except Exception:                            # noqa: BLE001 —— 收尾尽力而为
            pass
        try:
            transport.close()
        finally:
            self._connected = False

    @property
    def is_open(self) -> bool:
        return self._connected

    def __enter__(self) -> "DMM3458A":
        if not self._connected:
            self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _t(self) -> Transport:
        if self._transport is None or not self._connected:
            raise TransportError("3458A 未连接，请先 connect()")
        return self._transport

    # ---------- 身份 / 状态 ----------
    def idn(self) -> str:
        """`ID?`（3458A **没有** `*IDN?`）。实测返回形如 `HP3458A`。"""
        return self._t().query(C.ID)

    def error_string(self) -> str:
        """`ERRSTR?`（3458A **没有** `SYST:ERR?`）。返回原始响应，不做解读。

        已知形态 `<code>,"<message>"`（无错误为 `0,"NO ERROR"`）；每次查询弹出一条
        （FIFO）。队列深度与清空方式待手册核对——白名单里没有清队列命令。
        需要判断时用 `is_error_clear()`。
        """
        return self._t().query(C.ERRSTR)

    def temperature(self) -> float:
        """`TEMP?` 内部温度读数（数值，单位 **°C**）。

        2026-09-23 本机 GPIB0::9 实测返回 `37.0` / `36.9`（开机数小时后）——数值合理，
        故单位按 °C 采信；精度与是否需要温度选件仍未核对手册。
        """
        return _first_float(self._t().query(C.TEMP))

    def state(self) -> dict:
        """**设备回读**的当前状态（不是"本会话设过什么"的记录）。

        2026-09-23 本机实测：下列查询在 3458A 上都有响应（响应样例见 `commands.py`），
        因此 `ks3458a_status` 报的是设备真实配置。任一查询失败只记 `None`，
        不让整次状态查询失败。
        """
        t = self._t()

        def q(cmd: str):
            try:
                return t.query(cmd)
            except Exception:                        # noqa: BLE001
                return None

        out: dict = {
            "id": q(C.ID),
            "error": q(C.ERRSTR),
            "tarm": q(C.TARM_Q),                     # '4'=HOLD '1'=AUTO
            "trig": q(C.TRIG_Q),                     # '1'=AUTO '4'=HOLD
            "nrdgs": q(C.NRDGS_Q),                   # '1, 1'
            "nplc": _safe_float(q(C.NPLC_Q)),
            "aperture_s": _safe_float(q(C.APER_Q)),
            "function": q(C.FUNC_Q),                 # '1, .1' = DCV + 档位
            "range_v": _safe_float(q(C.RANGE_Q)),
            "azero": q(C.AZERO_Q),
            "mem": q(C.MEM_Q),
            "inbuf": q(C.INBUF_Q),
            "end": q(C.END_Q),
            "oformat": q(C.OFORMAT_Q),
            "mformat": q(C.MFORMAT_Q),
            "iscale": _safe_float(q(C.ISCALE_Q)),
        }
        try:
            out["temperature_c"] = self.temperature()
        except Exception as e:                        # noqa: BLE001
            out["temperature_error"] = f"{type(e).__name__}: {e}"
        out["tracked"] = {"range_v": self._range, "nplc": self._nplc}
        return out

    def query(self, cmd: str) -> str:
        """直接发白名单查询命令（外部不要拿它绕过白名单，见 commands.py）。"""
        return self._t().query(cmd)

    def write(self, cmd: str) -> None:
        """直接发白名单命令（同上）。"""
        self._t().write(cmd)

    @property
    def current_range(self) -> Optional[float]:
        """本会话**已下发过**的档位；None = 本会话没设过。

        3458A 白名单里**没有档位回读命令**（无 `DCV?`/`RANGE?`），所以这不是从设备
        读回来的值，只是"本会话设过什么"的记录——如实报告，别当成实测。
        """
        return self._range

    @property
    def current_nplc(self) -> Optional[float]:
        """本会话**已下发过**的 NPLC；None = 本会话没设过（同 `current_range` 口径）。"""
        return self._nplc

    # ---------- 会话恢复 / 重置 ----------
    def recover(self) -> None:
        """把表从"上次会话留下的现场"救回来：IFC/clear → 有限 drain → 挂起触发。

        现场教训（[SICL] L273-276）：上次会话若把 3458A 留在 free-run，它会持续吐
        读数、不理查询；此时**先 drain 只会一直读到数据**（实测 91 s）。必须先用
        IFC（SICL 通路）/ Device Clear（VISA 通路）打断序列，且 drain 必须有限
        （≤6 轮 ×250 ms；无界 drain 实测 80~91 s）。
        """
        transport = self._t()
        transport.ifc()                  # SICL: IFC；VISA: Device Clear（见 transport 注释）
        time.sleep(0.3)
        transport.drain(DRAIN_MAX_ROUNDS, DRAIN_TIMEOUT_MS)
        transport.write(C.TARM_HOLD)     # 断言：后续不再自动触发
        transport.write(C.TRIG_HOLD)
        time.sleep(0.2)
        transport.drain(DRAIN_MAX_ROUNDS, DRAIN_TIMEOUT_MS)

    def reset(self) -> None:
        """`RESET` + `END ALWAYS` + `INBUF ON`——**回到开机测量配置（破坏性）**。

        会重置档位/NPLC/测量功能/内存/触发等（完整影响范围**待手册核对**，见
        docs/COMMANDS_3458A.md）。调用方必须先取得授权：MCP 的 `ks3458a_reset`
        要求 `confirm=True`，库层不做二次确认。

        `END ALWAYS`（每次读数置 EOI）与 `INBUF ON`（打开输入缓冲）是 `TARM SGL`
        单次读数配方的前置条件——缺了会把 GPIB 总线占住（[VISA] L571-576）。
        """
        transport = self._t()
        transport.write(C.TARM_HOLD)     # 先挂住触发，免得 RESET 与在跑的序列打架
        transport.write(C.TRIG_HOLD)
        transport.write(C.RESET)
        time.sleep(1.0)                  # RESET 后自校准/稳定（参考实现实测值）
        transport.clear()                # 中止 RESET 期间可能残留的序列
        time.sleep(0.3)
        transport.drain(DRAIN_MAX_ROUNDS, DRAIN_TIMEOUT_MS)
        transport.write(C.END_ALWAYS)
        transport.write(C.INBUF_ON)
        time.sleep(0.2)
        transport.drain(DRAIN_MAX_ROUNDS, DRAIN_TIMEOUT_MS)
        self._range = None               # RESET 已把档位/NPLC 复位 → 本会话记录作废
        self._nplc = None

    # ---------- 配置 ----------
    def _discard_first_reading(self) -> None:
        """丢弃换档/换配置后的第一次读数（建立时间 + 自校准，[SICL] L339-341）。

        失败不抛：这一步的目的是把过渡读数从管道里拿走，不是取数。
        """
        try:
            self.read_dcv()
        except Exception:                            # noqa: BLE001
            pass

    def configure_dcv(self, dcv_range: float = 10.0, nplc: float = 10.0) -> None:
        """设直流档位与积分时间（`DCV <range>` / `NPLC <n>`），并丢弃首读数。"""
        value = _check_range(dcv_range)
        transport = self._t()
        transport.write(f"{C.DCV} {C.fmt_num(value)}")
        transport.write(f"{C.NPLC} {C.fmt_num(_check_nplc(nplc))}")
        self.dcv_range = value
        self.nplc = float(nplc)
        self._range = value
        self._nplc = float(nplc)
        time.sleep(0.3)
        self._discard_first_reading()

    def set_nplc(self, nplc: float) -> None:
        """只改积分时间（`NPLC <n>`），不动档位。

        与 `configure_dcv` 不同，这里**不丢弃首读数**（参考实现同样如此，
        [SICL] L353-357）：NPLC 变化不引起换档建立过程。要绝对干净请自己先读一次丢。

        ⚠ **交流功能下 NPLC 的语义未核对**（`SETACV SYNC` 的积分含义与 DCV 不同）。
        """
        value = _check_nplc(nplc)
        self._t().write(f"{C.NPLC} {C.fmt_num(value)}")
        self.nplc = value
        self._nplc = value
        time.sleep(0.3)

    def set_range(self, dcv_range: float) -> None:
        """切换直流档位；**已在该档位则不重发**。换档后丢弃第一次读数。

        10V 档物理上有 20% 超量程（可用到 ±12V，[VISA] L594），但本库按 1.1 倍
        余量选档（保守）；确知信号 ≤12V 又要用 10V 档时直接 `set_range(10.0)`。
        """
        value = _check_range(dcv_range)
        if self._range == value:
            return
        self._t().write(f"{C.DCV} {C.fmt_num(value)}")
        self._range = value
        time.sleep(0.4)
        self._discard_first_reading()

    @staticmethod
    def range_for(volt: float) -> float:
        """给定电压选一个能覆盖它的**最小**档位（留 10% 余量，[VISA] L603-609）。"""
        need = abs(float(volt)) * 1.1
        for allowed in C.DCV_RANGES:
            if need <= allowed:
                return allowed
        return C.DCV_RANGES[-1]

    def configure_acv(self, acv_range: float = 10.0, band_lo: Optional[float] = None,
                      band_hi: Optional[float] = None, sync: bool = False) -> None:
        """设交流档位与转换方式（`ACV` / `SETACV` / `ACBAND`），并丢弃首读数。

        `sync=False` → `SETACV ANA`（模拟转换，默认）；`True` → `SETACV SYNC`（同步采样）。
        `band_lo`/`band_hi` 给定时下发 `ACBAND <lo>,<hi>`（Hz），**必须成对给**。

        ⚠ 这一组命令**未在参考实现与官方样例中出现**（出处 [TASK]），真机首跑前
        请对照手册；`SETACV` 的取值全集、`ACBAND` 的合法带宽、AC 下 NPLC 的语义
        都列在 docs/COMMANDS_3458A.md「待手册核对项」。
        """
        value = _check_range(acv_range)
        if (band_lo is None) != (band_hi is None):
            raise ValueError("ACBAND 需要同时给出下限与上限（Hz），不能只给一个")
        transport = self._t()
        transport.write(f"{C.ACV} {C.fmt_num(value)}")
        transport.write(C.SETACV_SYNC if sync else C.SETACV_ANA)
        if band_lo is not None:
            low, high = float(band_lo), float(band_hi)
            if not high > low:
                raise ValueError(f"ACBAND 上限必须大于下限：{low} Hz, {high} Hz")
            transport.write(f"{C.ACBAND} {C.fmt_num(low)},{C.fmt_num(high)}")
        self.acv_range = value
        self.acv_sync = bool(sync)
        time.sleep(0.3)
        self._discard_first_reading()

    # ---------- 读数 ----------
    def _read_single(self, what: str = "DCV") -> float:
        """`TARM SGL,1` 触发一次读数并回值（3458A 单次读数的标准配方）。

        响应非数值时**报错**（不返回 0 兜底）：常见成因是上次会话的残留/响应错位，
        静默兜底会把错位数据当读数用。
        """
        raw = self._t().query(C.TARM_SGL_1)
        token = raw.split()[-1] if raw.split() else ""
        try:
            return float(token)
        except ValueError as exc:
            raise TransportError(
                f"3458A 返回非法{what}读数: {raw!r}"
                f"（非数值——可能是残留响应/总线错位，先 recover() 或查 ERRSTR?）") from exc

    def read_dcv(self, timeout_s: Optional[float] = None) -> float:
        """单次直流电压读数（V）。`timeout_s` 可覆盖本次读取超时。"""
        if timeout_s is not None:
            self._t().set_timeout(timeout_s)
        try:
            return self._read_single("DCV")
        finally:
            if timeout_s is not None:
                self._t().set_timeout(self.timeout_s)

    def read_acv(self, timeout_s: Optional[float] = None) -> float:
        """单次交流电压读数（V）。配方同 `read_dcv`（`TARM SGL,1`）。

        ⚠ 交流功能下 `TARM SGL,1` 的行为**未实测**（参考实现只有 DCV 路径）。
        """
        if timeout_s is not None:
            self._t().set_timeout(timeout_s)
        try:
            return self._read_single("ACV")
        finally:
            if timeout_s is not None:
                self._t().set_timeout(self.timeout_s)

    def read_avg(self, n: int = 1) -> float:
        """连续读 n 次取平均（降噪）。n≤1 等同单次读数。"""
        count = int(n)
        if count < 1:
            raise ValueError(f"n 必须 ≥1，收到 {n!r}")
        if count == 1:
            return self.read_dcv()
        return sum(self.read_dcv() for _ in range(count)) / count

    def read_stats(self, n: int = 1) -> dict:
        """连续读 n 次，返回 `{n, mean, stddev, min, max}`（样本标准差）。"""
        count = int(n)
        if count < 1:
            raise ValueError(f"n 必须 ≥1，收到 {n!r}")
        return _stats([self.read_dcv() for _ in range(count)])

    # ---------- 高速二进制突发 ----------
    def read_burst(self, n: int, sample_interval_s: Optional[float] = None,
                   dcv_range: Optional[float] = None,
                   aperture_s: Optional[float] = None,
                   timeout_s: Optional[float] = None) -> dict:
        """高速采样：一次触发取 n 个读数（Keysight 官方 100k rdg/s 配方）。

        下发序列（逐条对应 [SAMPLE] L43-69）::

            PRESET DIG → [DCV <range>] → MFORMAT SINT → OFORMAT SINT
            → [APER <s>] → [TIMER <s>] → MEM OFF → NRDGS n → TRIG AUTO
            → ISCALE? → TARM SYN → 读 2n+2 字节

        解析：前 2n 字节按 **2 字节大端有符号整数** 切出 n 个，各自 × ISCALE 得电压。
        末尾还有 2 字节（样例固定读 2n+2），**其含义待手册核对**——本函数只取前 2n 字节。

        返回 `{"values": [...], "summary": {...}}`；`summary` 是统计与本次配方参数，
        全量数组由调用方决定怎么用（MCP 工具落 CSV，不塞进返回体）。

        超时/字节数不足会明确报错（`TransportError`），**不返回截断数据**。
        """
        count = int(n)
        if count < 1:
            raise ValueError(f"n 必须 ≥1，收到 {n!r}")
        if count > C.BURST_MAX_READINGS:
            raise ValueError(
                f"n={count} 超过本库上限 {C.BURST_MAX_READINGS}（commands.BURST_MAX_READINGS）")
        if dcv_range is not None:
            dcv_range = _check_range(dcv_range)
        transport = self._t()
        transport.write(C.PRESET_DIG)
        if dcv_range is not None:
            transport.write(f"{C.DCV} {C.fmt_num(dcv_range)}")
            self._range = dcv_range
        transport.write(C.MFORMAT_SINT)
        transport.write(C.OFORMAT_SINT)
        if aperture_s is not None:
            transport.write(f"{C.APER} {C.fmt_num(aperture_s)}")
        if sample_interval_s is not None:
            transport.write(f"{C.TIMER} {C.fmt_num(sample_interval_s)}")
        transport.write(C.MEM_OFF)
        transport.write(f"{C.NRDGS} {count}")
        transport.write(C.TRIG_AUTO)
        iscale = _first_float(transport.query(C.ISCALE_Q))
        transport.write(C.TARM_SYN)
        raw = transport.read_bytes(2 * count + 2, timeout_s=timeout_s)
        # 传输层已保证字节数；这里再挡一道——截断数据会解析出错位的"合理值"，
        # 比直接报错危险得多（宁可失败，不可静默给错数）
        if len(raw) < 2 * count + 2:
            raise TransportError(
                f"二进制突发回读不足：期望 {2 * count + 2} 字节，实得 {len(raw)} 字节"
                f"（n={count}；超时或设备未按 SINT 配方输出）")
        values = [int.from_bytes(raw[i:i + 2], "big", signed=True) * iscale
                  for i in range(0, 2 * count, 2)]
        summary = _stats(values)
        summary.update({
            "iscale_v_per_lsb": iscale,
            "bytes_read": len(raw),
            "bytes_expected": 2 * count + 2,
            "dcv_range": dcv_range if dcv_range is not None else self._range,
            "sample_interval_s": sample_interval_s,
            "aperture_s": aperture_s,
        })
        return {"values": values, "summary": summary}
