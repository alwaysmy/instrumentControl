"""DH1766A 三路可编程直流电源驱动（dh1766_control 库）。

北京大华 DH1766A-1 / DH1766 系列，USB TMC / LAN 接口，SCPI 协议。
命令来源：DH1766 系列用户手册 第四章《远程控制与指令集》（4.2.1~4.2.10）。
*IDN? 典型响应：BJDH,DH1766A-1,0,V0.1.4.3

SCPI-99 合规要点（详见 commands.py 头部）：
    - 命令用短格式（手册示例），大小写不敏感；
    - 布尔写接受 ON|OFF|1|0，查询返回 0|1（SCPI-99 §7.3）；
    - 设值后应查询验证实际值（设备可舍入参数，SCPI-99 §7.2）；
    - 命令失败时查 SYST:ERR? 错误队列获取具体原因。

安全模式（safe_mode=True，接入负载时使用）：
    - 目标通道输出 ON 时，拒绝修改电压/电流设定、OVP/OCP、输出模式（TRAC/SERI/PARA）；
    - 输出开关本身（set_output / set_output_all）不拦截，属显式指令。
"""
from __future__ import annotations

import time
from typing import Optional, Union

from . import commands as C
from .visa import VisaClient

Channel = Union[int, str]  # 1|2|3 或 "CH1"|"CH2"|"CH3"

CH_ALIASES = {"CH1": 1, "CH2": 2, "CH3": 3}

# 手册 4.1：指令间隔 >= 100ms；通道切换 >= 300ms；串并联继电器 >= 500ms
CMD_DELAY_S = 0.1
CHANNEL_SWITCH_DELAY_S = 0.3
RELAY_DELAY_S = 0.5


def _ch_num(ch: Channel) -> int:
    """通道规范化：'CH1'|1 → 1；非法值抛 ValueError。"""
    try:
        n = CH_ALIASES[ch.upper()] if isinstance(ch, str) else int(ch)
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError(f"invalid channel: {ch!r}")
    if n not in (1, 2, 3):
        raise ValueError(f"invalid channel: {ch!r}")
    return n


class DH1766:
    """DH1766A 驱动，基于 VisaClient。"""

    def __init__(self, client: VisaClient, safe_mode: bool = False):
        self.client = client
        self.safe_mode = safe_mode

    # ================= 系统指令集 4.2.1 =================
    def idn(self) -> str:
        """*IDN? 设备标识串（IEEE 488.2 四字段：厂商,型号,序列号,版本）。"""
        return self.client.query(C.IDN)

    def clear(self) -> None:
        """*CLS 清除错误/事件寄存器。"""
        self.client.write(C.CLS)

    def version(self) -> str:
        """SYST:VERS? 软件版本号（实测返回如 'V0.1.4.3'）。"""
        return self.client.query(C.SYST_VERS)

    def system_error(self) -> Optional[str]:
        """SYST:ERR? 读取错误队列（FIFO），空队列返回 None。

        IEEE 488.2 错误处理：命令失败后调用本方法取错误码与描述。
        """
        resp = self.client.query(C.SYST_ERR)
        return resp or None

    def beep(self) -> None:
        """SYST:BEEP 蜂鸣器测试（响一声）。"""
        self.client.write(C.SYST_BEEP)

    def local(self) -> None:
        """SYST:LOC 本地模式（面板可操作）。含 >=100ms 指令间隔（手册 4.1）。"""
        self.client.write(C.SYST_LOC)
        time.sleep(CMD_DELAY_S)

    def remote(self) -> None:
        """SYST:REM 远程模式（外控）。含 >=100ms 指令间隔。"""
        self.client.write(C.SYST_REM)
        time.sleep(CMD_DELAY_S)

    def rwlock(self) -> None:
        """SYST:RWL 远程锁定（面板 Lock 键不可切回本地，需 SYST:LOC 恢复）。含 >=100ms 指令间隔。"""
        self.client.write(C.SYST_RWL)
        time.sleep(CMD_DELAY_S)

    def rlstate(self) -> Optional[str]:
        """SYST:COMM:RLST? 工作模式 LOC / REM / RWL。

        2026-09-13 实测（固件 V0.1.4.3）：
        - 手册写的 `SYST:COMM:RLST:STAT?`（带 :STAT）在本机**无响应**（超时），
          不是"返回空串"（此前文档记录有误）；正确形式是 `SYST:COMM:RLST?`；
        - **任何远程会话都会把设备置为 REM**：多次新建会话后第一条命令查询
          均返回 'REM'（即用户观察到的"一连就进远程模式"）；
        - 发 `SYST:LOC` 后立即返回 'LOC'，可把面板控制权还给现场。
        """
        resp = self.client.query(C.SYST_RLST)
        return resp or None

    # ================= 状态指令集 4.2.2 =================
    def stat_pres(self) -> None:
        """STAT:PRES 恢复事件使能寄存器为开机值。"""
        self.client.write(C.STAT_PRES)

    def stat_ques_enable(self, value: Optional[int] = None) -> Optional[int]:
        """STAT:QUES:ENAB 查询事件使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query(C.STAT_QUES_ENAB + "?"))
        self.client.write(f"{C.STAT_QUES_ENAB} {value}")
        return None

    def stat_ques_event(self) -> int:
        """STAT:QUES? 查询事件寄存器（读取后清零，IEEE 488.2 事件寄存器行为）。"""
        return int(self.client.query(C.STAT_QUES))

    def stat_ques_cond(self) -> int:
        """STAT:QUES:COND? 查询条件寄存器（读不清零）。"""
        return int(self.client.query(C.STAT_QUES_COND))

    def stat_oper_enable(self, value: Optional[int] = None) -> Optional[int]:
        """STAT:OPER:ENAB 操作事件使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query(C.STAT_OPER_ENAB + "?"))
        self.client.write(f"{C.STAT_OPER_ENAB} {value}")
        return None

    def stat_oper_event(self) -> int:
        """STAT:OPER? 操作事件寄存器（读取后清零）。"""
        return int(self.client.query(C.STAT_OPER))

    def stat_oper_cond(self) -> int:
        """STAT:OPER:COND? 操作条件寄存器。"""
        return int(self.client.query(C.STAT_OPER_COND))

    def stat_inst_isum(self, ch: int, kind: str = "cond") -> int:
        """STAT:QUES:INST:ISUM<n>:COND?/EVENt? 通道状态汇总寄存器。"""
        if ch not in (1, 2, 3) or kind not in ("cond", "event"):
            raise ValueError(f"invalid args: ch={ch} kind={kind}")
        node = "COND" if kind == "cond" else "EVEN"
        return int(self.client.query(C.STAT_INST_ISUM.format(n=ch, node=node)))

    # ================= 通道设定（手册 4.2.3）=================
    def select_channel(self, ch: Channel) -> None:
        """INST:NSEL <1|2|3> 切换当前操作通道（含 >=300ms 间隔）。"""
        n = _ch_num(ch)
        self.client.write(f"{C.INST_NSEL} {n}")
        time.sleep(CHANNEL_SWITCH_DELAY_S)

    def current_channel(self) -> str:
        """INST? 当前通道（CH1/CH2/CH3）。"""
        return self.client.query(C.INST_SEL + "?")

    def couple_trig(self, channels: Optional[list[Channel]] = None) -> Optional[list[str]]:
        """INST:COUP:TRIG 组合通道（读写）。

        channels=None 时查询返回 list[str]；传设置值后写命令并返回 None。
        手册例：INST:COUP:TRIG CH1,CH2,CH3；["NONE"] 清除。
        """
        if channels is None:
            resp = self.client.query(C.INST_COUP_TRIG + "?")
            return [p.strip() for p in resp.split(",")] if resp else ["NONE"]
        if len(channels) == 1 and str(channels[0]).upper() == "NONE":
            self.client.write(f"{C.INST_COUP_TRIG} NONE")
            time.sleep(CMD_DELAY_S)
            return None
        names = [
            c if (isinstance(c, str) and c.upper() in CH_ALIASES) else f"CH{_ch_num(c)}"
            for c in channels
        ]
        self.client.write(f"{C.INST_COUP_TRIG} {','.join(names)}")
        time.sleep(CMD_DELAY_S)
        return None

    # ================= 电压指令集 4.2.4 =================
    def set_voltage(self, ch: Channel, value: float) -> None:
        """VOLT <value> 设定单通道电压（V）。safe_mode 下输出 ON 时拒绝。

        注：SCPI-99 §7.2 设备可舍入参数，设值后请用 get_voltage 验证实际值。
        """
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"{C.VOLT} {value}")
        time.sleep(CMD_DELAY_S)

    def get_voltage(self, ch: Channel, arg: str = "") -> float:
        """VOLT? 查询单通道电压设定值（V），arg 可带 MAX/MIN/DEF。"""
        self.select_channel(ch)
        resp = self.client.query(f"{C.VOLT}? {arg}".strip())
        return float(resp)

    def voltage_mode(self, mode: Optional[str] = None) -> Optional[str]:
        """VOLT:MODE FIX|LIST（读写）。

        注：本机固件 V0.1.4.3 查询返回空串（手册按 V0.1.2.8 编写），返回 None。
        """
        if mode is None:
            resp = self.client.query(C.VOLT_MODE + "?")
            return resp or None
        self.client.write(f"{C.VOLT_MODE} {mode}")
        time.sleep(CMD_DELAY_S)

    def set_ovp(self, ch: Channel, value: float) -> None:
        """VOLT:PROT <value> 设定过压保护值（V）。safe_mode 下输出 ON 时拒绝。"""
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"{C.VOLT_PROT} {value}")
        time.sleep(CMD_DELAY_S)

    def get_ovp(self, ch: Channel, arg: str = "") -> float:
        """VOLT:PROT? 查询过压保护值（V），arg 可带 MAX/MIN。"""
        self.select_channel(ch)
        resp = self.client.query(f"{C.VOLT_PROT}? {arg}".strip())
        return float(resp)

    # ================= 触发指令集 4.2.5 =================
    def init_immediate(self, state: Optional[str] = None) -> None:
        """INIT[:IMM] ON|OFF 初始化列表状态（设备扩展：参数 ON|OFF）。"""
        if state is None:
            return
        self.client.write(f"{C.INIT} {state}")
        time.sleep(CMD_DELAY_S)

    def init_delay(self, value: Optional[float] = None) -> Optional[float]:
        """INIT:DEL 触发延时（s），读写；0 关闭。

        注：本机固件 V0.1.4.3 查询返回空串（手册按 V0.1.2.8 编写），返回 None。
        """
        if value is None:
            resp = self.client.query(C.INIT_DEL + "?")
            return float(resp) if resp else None
        self.client.write(f"{C.INIT_DEL} {value}")
        time.sleep(CMD_DELAY_S)

    def init_source(self, source: Optional[str] = None) -> Optional[str]:
        """INIT:SOUR BUS|IMM|EXT 触发源（读写）。查询本机固件返回空。"""
        if source is None:
            resp = self.client.query(C.INIT_SOUR + "?")
            return resp or None
        self.client.write(f"{C.INIT_SOUR} {source}")
        time.sleep(CMD_DELAY_S)

    def trigger(self) -> None:
        """*TRG 触发列表运行（FIX 模式下无动作）。"""
        self.client.write(C.TRG)

    # ================= 电流指令集 4.2.6 =================
    def set_current(self, ch: Channel, value: float) -> None:
        """CURR <value> 设定单通道电流（A）。safe_mode 下输出 ON 时拒绝。"""
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"{C.CURR} {value}")
        time.sleep(CMD_DELAY_S)

    def get_current(self, ch: Channel, arg: str = "") -> float:
        """CURR? 查询单通道电流设定值（A），arg 可带 MAX/MIN。"""
        self.select_channel(ch)
        resp = self.client.query(f"{C.CURR}? {arg}".strip())
        return float(resp)

    def current_mode(self, mode: Optional[str] = None) -> Optional[str]:
        """CURR:MODE FIX|LIST（读写）。查询本机固件返回空。"""
        if mode is None:
            resp = self.client.query(C.CURR_MODE + "?")
            return resp or None
        self.client.write(f"{C.CURR_MODE} {mode}")
        time.sleep(CMD_DELAY_S)

    def set_ocp(self, ch: Channel, value: float) -> None:
        """CURR:PROT <value> 设定过流保护值（A）。safe_mode 下输出 ON 时拒绝。"""
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"{C.CURR_PROT} {value}")
        time.sleep(CMD_DELAY_S)

    def get_ocp(self, ch: Channel, arg: str = "") -> float:
        """CURR:PROT? 查询过流保护值（A），arg 可带 MAX/MIN。"""
        self.select_channel(ch)
        resp = self.client.query(f"{C.CURR_PROT}? {arg}".strip())
        return float(resp)

    # ================= 输出指令集 4.2.7 =================
    def _check_mode(self, expect_mode: str) -> str:
        """工作模式校验（防拓扑误判）：声明值与实际不符时抛错并回传当前模式。

        只校验不设置——输出开关类操作必须先声明当前模式，避免在 TRAC（CH2 跟随
        CH1 输出负压）/SERI/PARA（通道合并）等非预期拓扑下误操作。
        """
        actual = self.output_mode()
        claimed = str(expect_mode).strip().upper()
        if claimed != actual:
            raise RuntimeError(
                f"工作模式校验失败：声明 {claimed}，实际 {actual}。"
                f"请先 psu_mode()/output_mode() 确认当前模式（当前为 {actual}）后重试"
            )
        return actual

    def set_output(self, ch: Channel, state: bool, expect_mode: str) -> None:
        """OUTP ON|OFF 单通道输出开关（布尔，SCPI-99 §7.3）。

        expect_mode（必填）：调用方声明的当前工作模式（NORM/TRAC/SERI/PARA），
        仅校验不设置；与实际不符立即拒绝并回传当前模式（防拓扑误判）。
        """
        self._check_mode(expect_mode)
        self.select_channel(ch)
        self.client.write(f"{C.OUTP} {'ON' if state else 'OFF'}")
        time.sleep(CMD_DELAY_S)

    def get_output_state(self) -> list[bool]:
        """APPL:OUTP? 三路输出状态 [CH1, CH2, CH3]（响应 1|0）。"""
        raw = self.client.query(C.APPL_OUTP + "?")
        return [p.strip() in ("1", "ON") for p in raw.split(",")]

    def set_output_all(self, states: list[bool], expect_mode: str) -> None:
        """三路同时开关。

        expect_mode（必填）：声明的当前工作模式，仅校验不设置（同 set_output）。
        固件实测（V0.1.4.3）：`APPL:OUT ...` 报 -113（命令头不存在），
        `APPL:OUTP ...` 报 -200（查询专用，不可写）——本机无三路联动开关命令。
        此处按单通道 `set_output` 循环实现（含通道切换间隔），写后回读比对。
        """
        if len(states) != 3:
            raise ValueError("states must have exactly 3 elements")
        self._check_mode(expect_mode)
        for i, s in enumerate(states):
            self.set_output(i + 1, bool(s), expect_mode)
        got = self.get_output_state()
        if [bool(x) for x in got] != [bool(x) for x in states]:
            raise RuntimeError(f"三路开关回读不一致：期望 {states}，实得 {got}")

    _MODE_CMDS = {"TRAC": "OUTP:TRAC", "SERI": "OUTP:SERI", "PARA": "OUTP:PARA"}
    OUTPUT_MODES = ("NORM", "TRAC", "SERI", "PARA")

    def _set_mode_cmd(self, mode: str, on: bool) -> None:
        """OUTP:TRAC/SERI/PARA 模式切换（继电器动作 >=500ms）。

        硬件安全：继电器联动改变输出拓扑，切换前必须输出全关——无条件强制，
        不依赖 safe_mode（带载切换有硬件风险；此前仅 safe_mode 下拦截）。
        """
        if mode not in self._MODE_CMDS:
            raise ValueError(f"invalid mode: {mode!r}")
        if any(self.get_output_state()):
            raise RuntimeError("切换输出模式前必须先关闭全部输出（继电器联动拓扑变化）")
        self.client.write(f"{self._MODE_CMDS[mode]} {'ON' if on else 'OFF'}")
        time.sleep(RELAY_DELAY_S)

    def _get_mode_cmd(self, mode: str) -> bool:
        resp = self.client.query(self._MODE_CMDS[mode] + "?")
        return resp.strip() in ("1", "ON")

    def track_mode(self, on: Optional[bool] = None) -> Optional[bool]:
        """OUTP:TRAC 跟踪模式（读写）。输出 ON 时拒绝写（无条件，继电器安全）。"""
        if on is None:
            return self._get_mode_cmd("TRAC")
        self._set_mode_cmd("TRAC", on)
        return None

    def series_mode(self, on: Optional[bool] = None) -> Optional[bool]:
        """OUTP:SERI 串联模式（读写）。输出 ON 时拒绝写（无条件，继电器安全）。"""
        if on is None:
            return self._get_mode_cmd("SERI")
        self._set_mode_cmd("SERI", on)
        return None

    def parallel_mode(self, on: Optional[bool] = None) -> Optional[bool]:
        """OUTP:PARA 并联模式（读写）。输出 ON 时拒绝写（无条件，继电器安全）。"""
        if on is None:
            return self._get_mode_cmd("PARA")
        self._set_mode_cmd("PARA", on)
        return None

    def output_mode(self) -> str:
        """当前输出模式：NORM（正常，三路独立）/TRAC（跟踪）/SERI（串联）/PARA（并联）。

        由三路模式开关回读推导。固件互斥（实测 2026-09-08：开一路自动清零
        其余，无错误）；若回读出现多路同开则抛错（状态异常）。
        """
        states = {m: self._get_mode_cmd(m) for m in ("TRAC", "SERI", "PARA")}
        on = [m for m, v in states.items() if v]
        if len(on) > 1:
            raise RuntimeError(f"输出模式状态异常（多路同时开）：{states}")
        return on[0] if on else "NORM"

    def set_output_mode(self, mode: str) -> None:
        """设置输出模式（NORM/TRAC/SERI/PARA），写后回读比对。

        NORM = 三路模式开关全关（三路独立输出）。其余模式开对应开关，
        固件自动清除其余两路。继电器联动：输出必须全关（无条件强制）。
        """
        m = mode.strip().upper()
        if m not in self.OUTPUT_MODES:
            raise ValueError(f"invalid mode: {mode!r}（可选 {self.OUTPUT_MODES}）")
        if m == "NORM":
            for k in ("TRAC", "SERI", "PARA"):
                if self._get_mode_cmd(k):
                    self._set_mode_cmd(k, False)
        else:
            self._set_mode_cmd(m, True)
        got = self.output_mode()
        if got != m:
            raise RuntimeError(f"输出模式设置未生效：期望 {m}，实得 {got}")

    def output_timer(self, value: Optional[int] = None) -> Optional[int]:
        """OUTP:TIM:DATA 输出定时器（秒，读写；0=关闭）。

        注：本机固件 V0.1.4.3 写 0 被静默忽略（无法经 SCPI 关闭定时器，见 EXPERIENCE.md）。
        """
        if value is None:
            return int(float(self.client.query(C.OUTP_TIM + "?")))
        self.client.write(f"{C.OUTP_TIM} {value}")
        time.sleep(CMD_DELAY_S)
        return None

    # ================= 测量指令集 4.2.8 =================
    def measure_voltage_all(self) -> list[float]:
        """MEAS:VOLT:ALL? 回读三路输出电压（V）。"""
        raw = self.client.query(C.MEAS_VOLT + ":ALL?")
        return [float(x) for x in raw.split(",")]

    def measure_current_all(self) -> list[float]:
        """MEAS:CURR:ALL? 回读三路输出电流（A）。"""
        raw = self.client.query(C.MEAS_CURR + ":ALL?")
        return [float(x) for x in raw.split(",")]

    def measure_power_all(self) -> list[float]:
        """MEAS:POW:ALL? 回读三路输出功率（W）。"""
        raw = self.client.query(C.MEAS_POW + ":ALL?")
        return [float(x) for x in raw.split(",")]

    def measure_voltage(self, ch: Channel) -> float:
        """MEAS:VOLT? 回读单通道电压（V）。"""
        self.select_channel(ch)
        return float(self.client.query(C.MEAS_VOLT + "?"))

    def measure_current(self, ch: Channel) -> float:
        """MEAS:CURR? 回读单通道电流（A）。"""
        self.select_channel(ch)
        return float(self.client.query(C.MEAS_CURR + "?"))

    def measure_power(self, ch: Channel) -> float:
        """MEAS:POW? 回读单通道功率（W）。"""
        self.select_channel(ch)
        return float(self.client.query(C.MEAS_POW + "?"))

    def measure_voltage_dict(self) -> dict[str, float]:
        """MEAS:VOLT:ALL? 按通道名返回 {"CH1": v, "CH2": v, "CH3": v}。

        语义提示：CH1/CH2 有正常/串联/并联/跟踪四种输出模式（手册 §3.8）；
        跟踪模式下 CH2 跟随 CH1 输出同等值的负电压（如 CH1 设 12V 则 CH2
        为 -12V，范围可到 -32V）。断电验证时 CH1/CH2 都要归零才算真断电。
        """
        vals = self.measure_voltage_all()
        return {f"CH{i + 1}": vals[i] for i in range(len(vals))}

    def measure_current_dict(self) -> dict[str, float]:
        """MEAS:CURR:ALL? 按通道名返回 {"CH1": a, "CH2": a, "CH3": a}。"""
        vals = self.measure_current_all()
        return {f"CH{i + 1}": vals[i] for i in range(len(vals))}

    def power_cycle(self, ch: Channel, expect_mode: str,
                    off_delay_s: float = 1.0, on_delay_s: float = 1.0,
                    cycles: int = 1) -> dict:
        """上下电循环：关断→延迟→开启→延迟，重复 cycles 次。

        expect_mode（必填）：声明的当前工作模式，仅校验不设置（同 set_output）。
        off_delay_s：关断后延迟（默认 1s）——需保证下电放电时调大（如 6s，
        实测电容残留需 ≥6s 放完）；on_delay_s：开启后延迟（默认 1s）；
        cycles：循环次数（默认 1）。
        延迟由主机 sleep 控制，不精准（用于保证放电/上电时序，非精密时序）。
        返回 {"cycles", "records": [每次循环的实测延迟与电压], "after"}。
        """
        n = int(cycles)
        if n < 1:
            raise ValueError(f"cycles 必须 ≥1，收到 {cycles!r}")
        self._check_mode(expect_mode)
        records = []
        for i in range(1, n + 1):
            self.set_output(ch, False, expect_mode)
            t0 = time.monotonic()
            time.sleep(off_delay_s)
            off_actual = time.monotonic() - t0
            self.set_output(ch, True, expect_mode)
            t1 = time.monotonic()
            time.sleep(on_delay_s)
            on_actual = time.monotonic() - t1
            records.append({
                "cycle": i,
                "off_delay_s": round(off_actual, 3),
                "on_delay_s": round(on_actual, 3),
                "voltage_v": self.measure_voltage_all(),
            })
        return {
            "cycles": n,
            "off_delay_s": off_delay_s,
            "on_delay_s": on_delay_s,
            "records": records,
            "after": self.measure_voltage_dict(),
        }

    def pre_power_check(self) -> dict:
        """上电（开输出）前安全检查：一次查全关键状态并给出风险提示。

        检查项（手册 §3.8 输出模式 / §4.2.2 状态寄存器 / §4.2.8 测量）：
        - 输出模式（TRAC/SERI/PARA 改变拓扑，误判风险；CH2 负压是 TRAC 跟随）；
        - 三路输出状态（是否已带电，防重复上电）；
        - 设定电压/电流 vs OVP/OCP 保护值（保护值须大于设定值，否则一开就保护）；
        - 状态寄存器 QUES 条件位（OT/OVP/OCP 等实时告警）；
        - 通道耦合（非 NONE 时设定会联动）。

        返回 {"safe": bool, "warnings": [...], "state": {...}}。
        safe=False 时 warnings 逐条说明风险，上电前应逐项确认。
        """
        state = {
            "output_mode": self.output_mode(),
            "output_on": self.get_output_state(),
            "set_voltage_v": self.apply_voltage(),
            "set_current_a": self.apply_current(),
            "ovp_v": [self.get_ovp(i) for i in (1, 2, 3)],
            "ocp_a": [self.get_ocp(i) for i in (1, 2, 3)],
            "measure_voltage_v": self.measure_voltage_all(),
            "measure_current_a": self.measure_current_all(),
            "couple_trig": self.couple_trig(),
            "ques_cond": self.stat_ques_cond(),
            "oper_cond": self.stat_oper_cond(),
        }
        warnings: list[str] = []

        if state["output_mode"] != "NORM":
            warnings.append(
                f"输出模式为 {state['output_mode']}（非 NORM）：拓扑已改变，"
                f"{'CH2 跟随 CH1 输出负电压' if state['output_mode'] == 'TRAC' else '通道间已联动'}"
            )
        if any(state["output_on"]):
            on = [f"CH{i+1}" for i, v in enumerate(state["output_on"]) if v]
            warnings.append(f"已有通道带电（{'/'.join(on)}）——重复上电前请确认负载状态")

        for i, (vset, ovp) in enumerate(zip(state["set_voltage_v"], state["ovp_v"]), 1):
            if ovp <= vset:
                warnings.append(
                    f"CH{i} OVP({ovp:.3f}V) ≤ 设定电压({vset:.3f}V)：一开输出即触发过压保护"
                )
        for i, (iset, ocp) in enumerate(zip(state["set_current_a"], state["ocp_a"]), 1):
            if ocp <= iset:
                warnings.append(
                    f"CH{i} OCP({ocp:.3f}A) ≤ 设定电流({iset:.3f}A)：一开输出即触发过流保护"
                )
        if state["ques_cond"]:
            warnings.append(f"QUES 条件寄存器非零（0x{state['ques_cond']:X}）：存在实时告警")
        if state["couple_trig"] and state["couple_trig"] != ["NONE"]:
            warnings.append(f"通道耦合已启用（{state['couple_trig']}）：设定会联动")

        return {"safe": not warnings, "warnings": warnings, "state": state}

    # ================= 复合控制命令 4.2.9（设备扩展） =================
    def apply_voltage(self, values: Optional[list[float]] = None) -> Optional[list[float]]:
        """APPL:VOLT 三路电压设定（读写，一次完成，无通道切换延时）。

        设置后按 SCPI-99 §7.2 回读并返回设备实际设定值；仅写时无需回读可忽略返回值。
        """
        if values is None:
            raw = self.client.query(C.APPL_VOLT + "?")
            return [float(x) for x in raw.split(",")]
        if len(values) != 3:
            raise ValueError("values must have exactly 3 elements")
        self.client.write(f"{C.APPL_VOLT} {values[0]},{values[1]},{values[2]}")
        time.sleep(CMD_DELAY_S)
        return self.apply_voltage()

    def apply_current(self, values: Optional[list[float]] = None) -> Optional[list[float]]:
        """APPL:CURR 三路电流设定（读写）。设置后回读返回实际设定值。"""
        if values is None:
            raw = self.client.query(C.APPL_CURR + "?")
            return [float(x) for x in raw.split(",")]
        if len(values) != 3:
            raise ValueError("values must have exactly 3 elements")
        self.client.write(f"{C.APPL_CURR} {values[0]},{values[1]},{values[2]}")
        time.sleep(CMD_DELAY_S)
        return self.apply_current()

    # ================= IEEE-488 子系统 4.2.10 =================
    def ese(self, value: Optional[int] = None) -> Optional[int]:
        """*ESE 标准事件使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query(C.ESE + "?"))
        self.client.write(f"{C.ESE} {value}")
        time.sleep(CMD_DELAY_S)
        return None

    def esr(self) -> int:
        """*ESR? 标准事件寄存器（读取后清零）。"""
        return int(self.client.query(C.ESR))

    def opc(self, query: bool = False) -> Optional[int]:
        """*OPC 操作完成标志；query=True 时 *OPC? 返回 1。"""
        if query:
            return int(self.client.query(C.OPC + "?"))
        self.client.write(C.OPC)
        time.sleep(CMD_DELAY_S)
        return None

    def psc(self, value: Optional[int] = None) -> Optional[int]:
        """*PSC 上电使能寄存器清零策略（读写）。

        注：本机固件 V0.1.4.3 写 1 后查询仍返回 0（固件行为）。
        """
        if value is None:
            return int(self.client.query(C.PSC + "?"))
        self.client.write(f"{C.PSC} {value}")
        time.sleep(CMD_DELAY_S)
        return None

    def rst(self) -> None:
        """*RST 复位所有参数到出厂状态（会覆盖全部设定，使用前务必备份）。

        ⚠ 必须经用户明确允许后执行：实测复位会触发设备软复位（约 3s 就绪，
        期间查询返回开机横幅 'V0.1.4.3'），且恢复出厂设定（32V/32V/6V、
        3A/3A/3A、TIM=1s）与蜂鸣器状态；SCPI 无 BEEP 开关命令可事后核对。
        自动化脚本默认禁止执行 *RST（见测试脚本 --allow-rst 参数）。
        """
        self.client.write(C.RST)
        time.sleep(3.0)

    def sre(self, value: Optional[int] = None) -> Optional[int]:
        """*SRE 状态字节使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query(C.SRE + "?"))
        self.client.write(f"{C.SRE} {value}")
        time.sleep(CMD_DELAY_S)
        return None

    def stb(self) -> int:
        """*STB? 状态字节寄存器（读取后清零）。"""
        return int(self.client.query(C.STB))

    # ================= 安全保护 =================
    def _guard_set(self, ch: Channel) -> None:
        """safe_mode 下，目标通道输出 ON 时拒绝修改设定。"""
        if not self.safe_mode:
            return
        states = self.get_output_state()
        n = _ch_num(ch)
        if states[n - 1]:
            raise RuntimeError(
                f"safe_mode: CH{n} 输出开启中，拒绝修改设定；"
                f"请先 set_output({n}, False, expect_mode=<当前模式>)"
            )

    def measure_stable(
        self, samples: int = 3, settle_s: float = 2.0, interval_s: float = 1.0
    ) -> dict:
        """输出开启后的稳定读取：先等 settle_s，再连续采样 samples 次。

        实测背景（2026-08-17）：CH1 开启后存在上电过渡态——0.5s 时读得
        9.351V/0.198A，等待 2s+ 后稳定为 11.99V/0.353A（三次读数一致）。
        规范：上电后延迟 >=2s 再读数，或多次读取确认一致。

        返回 {"voltage_v": 末次, "current_a": 末次, "samples": [...]}
        """
        time.sleep(settle_s)
        vs: list[list[float]] = []
        cs: list[list[float]] = []
        for i in range(samples):
            vs.append(self.measure_voltage_all())
            cs.append(self.measure_current_all())
            if i < samples - 1:
                time.sleep(interval_s)
        return {
            "voltage_v": vs[-1],
            "current_a": cs[-1],
            "samples": [{"voltage_v": v, "current_a": c} for v, c in zip(vs, cs)],
        }

    # ================= 便捷快照 =================
    def snapshot(self) -> dict:
        """读取全部常用状态（只读，不改动设备）。"""
        return {
            "idn": self.idn(),
            "version": self.version(),
            "measure_voltage_v": self.measure_voltage_all(),
            "measure_current_a": self.measure_current_all(),
            "measure_power_w": self.measure_power_all(),
            "set_voltage_v": self.apply_voltage(),
            "set_current_a": self.apply_current(),
            "ovp_v": [self.get_ovp(i) for i in (1, 2, 3)],
            "ocp_a": [self.get_ocp(i) for i in (1, 2, 3)],
            "output_on": self.get_output_state(),
            "output_mode": self.output_mode(),
            "track_mode": self.track_mode(),
            "series_mode": self.series_mode(),
            "parallel_mode": self.parallel_mode(),
            "output_timer_s": self.output_timer(),
            "couple_trig": self.couple_trig(),
        }
