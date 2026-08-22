"""DH1766A 三路可编程直流电源驱动（完整版）。

北京大华 DH1766A-1，USB TMC / LAN 接口，SCPI 协议。
命令来源：DH1766A系列电源用户手册V2.1.pdf 第四章 远程控制与指令集（4.2.1~4.2.10）。
*IDN? 典型响应：BJDH,DH1766A-1,0,V0.1.4.3

安全模式（safe_mode=True，接入负载时使用）：
    - 目标通道输出 ON 时，拒绝修改电压/电流设定、OVP/OCP、输出模式（TRAC/SERI/PARA）；
    - 输出开关本身（set_output / set_output_all）不拦截，属显式指令。
"""
from __future__ import annotations

import time
from typing import Optional, Union

from common.visa_client import VisaClient

Channel = Union[int, str]  # 1|2|3 或 "CH1"|"CH2"|"CH3"

CH_ALIASES = {"CH1": 1, "CH2": 2, "CH3": 3}

# 手册 4.1：指令间隔 >= 100ms；通道切换 >= 300ms；串并联继电器 >= 500ms
CMD_DELAY_S = 0.1
CHANNEL_SWITCH_DELAY_S = 0.3
RELAY_DELAY_S = 0.5


class DH1766:
    """DH1766A 驱动，基于通用 VisaClient。"""

    def __init__(self, client: VisaClient, safe_mode: bool = False):
        self.client = client
        self.safe_mode = safe_mode

    # ================= 系统指令集 4.2.1 =================
    def idn(self) -> str:
        """*IDN? 设备标识串。"""
        return self.client.query("*IDN?")

    def clear(self) -> None:
        """*CLS 清除错误/事件寄存器。"""
        self.client.write("*CLS")

    def version(self) -> str:
        """SYST:VERS? 软件版本号。"""
        return self.client.query("SYST:VERS?")

    def beep(self) -> None:
        """SYST:BEEP 蜂鸣器测试（响一声）。"""
        self.client.write("SYST:BEEP")

    def local(self) -> None:
        """SYST:LOC 本地模式（面板可操作）。"""
        self.client.write("SYST:LOC")

    def remote(self) -> None:
        """SYST:REM 远程模式。"""
        self.client.write("SYST:REM")

    def rwlock(self) -> None:
        """SYST:RWL 远程锁定（面板 Lock 键不可切回本地）。"""
        self.client.write("SYST:RWL")

    def rlstate(self) -> Optional[str]:
        """SYST:COMM:RLST:STAT? 工作模式 LOC/REM/RWL。

        注：本机固件 V0.1.4.3 实测返回空串（手册按 V0.1.2.8 编写），
        返回空时给出 None 而非报错。
        """
        resp = self.client.query("SYST:COMM:RLST:STAT?")
        return resp or None

    # ================= 状态指令集 4.2.2 =================
    def stat_pres(self) -> None:
        """STAT:PRES 恢复事件使能寄存器为开机值。"""
        self.client.write("STAT:PRES")

    def stat_ques_enable(self, value: Optional[int] = None):
        """STAT:QUES:ENAB 查询事件使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query("STAT:QUES:ENAB?"))
        self.client.write(f"STAT:QUES:ENAB {value}")

    def stat_ques_event(self) -> int:
        """STAT:QUES? 查询事件寄存器（读取后清零）。"""
        return int(self.client.query("STAT:QUES?"))

    def stat_ques_cond(self) -> int:
        """STAT:QUES:COND? 查询条件寄存器。"""
        return int(self.client.query("STAT:QUES:COND?"))

    def stat_oper_enable(self, value: Optional[int] = None):
        """STAT:OPER:ENAB 操作事件使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query("STAT:OPER:ENAB?"))
        self.client.write(f"STAT:OPER:ENAB {value}")

    def stat_oper_event(self) -> int:
        """STAT:OPER? 操作事件寄存器（读取后清零）。"""
        return int(self.client.query("STAT:OPER?"))

    def stat_oper_cond(self) -> int:
        """STAT:OPER:COND? 操作条件寄存器。"""
        return int(self.client.query("STAT:OPER:COND?"))

    def stat_inst_isum(self, ch: int, kind: str = "cond") -> int:
        """STAT:QUES:INST:ISUM<n>:COND?/EVENt? 通道状态汇总寄存器。"""
        if ch not in (1, 2, 3) or kind not in ("cond", "event"):
            raise ValueError(f"invalid args: ch={ch} kind={kind}")
        node = "COND" if kind == "cond" else "EVEN"
        return int(self.client.query(f"STAT:QUES:INST:ISUM{ch}:{node}?"))

    # ================= 输出通道设定 4.2.3 =================
    def select_channel(self, ch: Channel) -> None:
        """INST:NSEL <1|2|3> 切换当前操作通道（含 >=300ms 间隔）。"""
        n = CH_ALIASES[ch] if isinstance(ch, str) else int(ch)
        if n not in (1, 2, 3):
            raise ValueError(f"invalid channel: {ch!r}")
        self.client.write(f"INST:NSEL {n}")
        time.sleep(CHANNEL_SWITCH_DELAY_S)

    def current_channel(self) -> str:
        """INST? 当前通道（CH1/CH2/CH3）。"""
        return self.client.query("INST?")

    def couple_trig(self, channels: Optional[list[Channel]] = None) -> list[str]:
        """INST:COUP:TRIG 组合通道（读写）。

        channels=None 时查询；传 [CH1,CH2,CH3] 设置，NONE 清除。
        """
        if channels is None:
            resp = self.client.query("INST:COUP:TRIG?")
            return [p.strip() for p in resp.split(",")] if resp else ["NONE"]
        # 手册例：INST:COUP:TRIG CH1,CH2,CH3，统一转 CH 文本；NONE 为清除
        if len(channels) == 1 and str(channels[0]).upper() == "NONE":
            self.client.write("INST:COUP:TRIG NONE")
            time.sleep(CMD_DELAY_S)
            return
        names = [
            c if (isinstance(c, str) and c.upper() in CH_ALIASES) else f"CH{int(c)}"
            for c in channels
        ]
        self.client.write(f"INST:COUP:TRIG {','.join(names)}")
        time.sleep(CMD_DELAY_S)

    # ================= 电压指令集 4.2.4 =================
    def set_voltage(self, ch: Channel, value: float) -> None:
        """VOLT <value> 设定单通道电压（V）。safe_mode 下输出 ON 时拒绝。"""
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"VOLT {value}")
        time.sleep(CMD_DELAY_S)

    def get_voltage(self, ch: Channel, arg: str = "") -> float:
        """VOLT? 查询单通道电压设定值（V），arg 可带 MAX/MIN。"""
        self.select_channel(ch)
        resp = self.client.query(f"VOLT? {arg}".strip())
        return float(resp)

    def voltage_mode(self, mode: Optional[str] = None) -> Optional[str]:
        """VOLT:MODE FIX|LIST（读写）。

        注：本机固件 V0.1.4.3 查询返回空串（手册按 V0.1.2.8 编写），返回 None。
        """
        if mode is None:
            resp = self.client.query("VOLT:MODE?")
            return resp or None
        self.client.write(f"VOLT:MODE {mode}")
        time.sleep(CMD_DELAY_S)

    def set_ovp(self, ch: Channel, value: float) -> None:
        """VOLT:PROT <value> 设定过压保护值（V）。safe_mode 下输出 ON 时拒绝。"""
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"VOLT:PROT {value}")
        time.sleep(CMD_DELAY_S)

    def get_ovp(self, ch: Channel, arg: str = "") -> float:
        """VOLT:PROT? 查询过压保护值（V），arg 可带 MAX/MIN。"""
        self.select_channel(ch)
        resp = self.client.query(f"VOLT:PROT? {arg}".strip())
        return float(resp)

    # ================= 触发指令集 4.2.5 =================
    def init_immediate(self, state: Optional[str] = None) -> None:
        """INIT[:IMM] ON|OFF 初始化列表状态。"""
        if state is None:
            return
        self.client.write(f"INIT {state}")
        time.sleep(CMD_DELAY_S)

    def init_delay(self, value: Optional[float] = None) -> Optional[float]:
        """INIT:DEL 触发延时（s），读写；0 关闭。

        注：本机固件 V0.1.4.3 查询返回空串（手册按 V0.1.2.8 编写），返回 None。
        """
        if value is None:
            resp = self.client.query("INIT:DEL?")
            return float(resp) if resp else None
        self.client.write(f"INIT:DEL {value}")
        time.sleep(CMD_DELAY_S)

    def init_source(self, source: Optional[str] = None) -> Optional[str]:
        """INIT:SOUR BUS|IMM|EXT 触发源（读写）。"""
        if source is None:
            resp = self.client.query("INIT:SOUR?")
            return resp or None
        self.client.write(f"INIT:SOUR {source}")
        time.sleep(CMD_DELAY_S)

    def trigger(self) -> None:
        """*TRG 触发列表运行（FIX 模式下无动作）。"""
        self.client.write("*TRG")

    # ================= 电流指令集 4.2.6 =================
    def set_current(self, ch: Channel, value: float) -> None:
        """CURR <value> 设定单通道电流（A）。safe_mode 下输出 ON 时拒绝。"""
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"CURR {value}")
        time.sleep(CMD_DELAY_S)

    def get_current(self, ch: Channel, arg: str = "") -> float:
        """CURR? 查询单通道电流设定值（A），arg 可带 MAX/MIN。"""
        self.select_channel(ch)
        resp = self.client.query(f"CURR? {arg}".strip())
        return float(resp)

    def current_mode(self, mode: Optional[str] = None) -> Optional[str]:
        """CURR:MODE FIX|LIST（读写）。

        注：本机固件 V0.1.4.3 查询返回空串（手册按 V0.1.2.8 编写），返回 None。
        """
        if mode is None:
            resp = self.client.query("CURR:MODE?")
            return resp or None
        self.client.write(f"CURR:MODE {mode}")
        time.sleep(CMD_DELAY_S)

    def set_ocp(self, ch: Channel, value: float) -> None:
        """CURR:PROT <value> 设定过流保护值（A）。safe_mode 下输出 ON 时拒绝。"""
        self._guard_set(ch)
        self.select_channel(ch)
        self.client.write(f"CURR:PROT {value}")
        time.sleep(CMD_DELAY_S)

    def get_ocp(self, ch: Channel, arg: str = "") -> float:
        """CURR:PROT? 查询过流保护值（A），arg 可带 MAX/MIN。"""
        self.select_channel(ch)
        resp = self.client.query(f"CURR:PROT? {arg}".strip())
        return float(resp)

    # ================= 输出指令集 4.2.7 =================
    def set_output(self, ch: Channel, state: bool) -> None:
        """OUTP ON|OFF 单通道输出开关。"""
        self.select_channel(ch)
        self.client.write(f"OUTP {'ON' if state else 'OFF'}")
        time.sleep(CMD_DELAY_S)

    def get_output_state(self) -> list[bool]:
        """APPL:OUTP? 三路输出状态 [CH1, CH2, CH3]。"""
        raw = self.client.query("APPL:OUTP?")
        return [p.strip() in ("1", "ON") for p in raw.split(",")]

    def set_output_all(self, states: list[bool]) -> None:
        """APPL:OUT s1,s2,s3 三路同时开关。"""
        if len(states) != 3:
            raise ValueError("states must have exactly 3 elements")
        args = ",".join("1" if s else "0" for s in states)
        self.client.write(f"APPL:OUT {args}")
        time.sleep(CMD_DELAY_S)

    def _set_mode_cmd(self, node: str, on: bool) -> None:
        """OUTP:TRAC/SERI/PARA 模式切换（继电器动作 >=500ms）。"""
        self._guard_all_outputs_off()
        self.client.write(f"OUTP:{node} {'ON' if on else 'OFF'}")
        time.sleep(RELAY_DELAY_S)

    def _get_mode_cmd(self, node: str) -> bool:
        resp = self.client.query(f"OUTP:{node}?")
        return resp.strip() in ("1", "ON")

    def track_mode(self, on: Optional[bool] = None) -> Optional[bool]:
        """OUTP:TRAC 跟踪模式（读写）。safe_mode 下输出 ON 时拒绝写。"""
        if on is None:
            return self._get_mode_cmd("TRAC")
        self._set_mode_cmd("TRAC", on)
        return None

    def series_mode(self, on: Optional[bool] = None) -> Optional[bool]:
        """OUTP:SERI 串联模式（读写）。safe_mode 下输出 ON 时拒绝写。"""
        if on is None:
            return self._get_mode_cmd("SERI")
        self._set_mode_cmd("SERI", on)
        return None

    def parallel_mode(self, on: Optional[bool] = None) -> Optional[bool]:
        """OUTP:PARA 并联模式（读写）。safe_mode 下输出 ON 时拒绝写。"""
        if on is None:
            return self._get_mode_cmd("PARA")
        self._set_mode_cmd("PARA", on)
        return None

    def output_timer(self, value: Optional[int] = None) -> int:
        """OUTP:TIM:DATA 输出定时器（秒，读写；0=关闭）。"""
        if value is None:
            return int(float(self.client.query("OUTP:TIM:DATA?")))
        self.client.write(f"OUTP:TIM:DATA {value}")
        time.sleep(CMD_DELAY_S)

    # ================= 测量指令集 4.2.8 =================
    def measure_voltage_all(self) -> list[float]:
        """MEAS:VOLT:ALL? 回读三路输出电压（V）。"""
        raw = self.client.query("MEAS:VOLT:ALL?")
        return [float(x) for x in raw.split(",")]

    def measure_current_all(self) -> list[float]:
        """MEAS:CURR:ALL? 回读三路输出电流（A）。"""
        raw = self.client.query("MEAS:CURR:ALL?")
        return [float(x) for x in raw.split(",")]

    def measure_power_all(self) -> list[float]:
        """MEAS:POW:ALL? 回读三路输出功率（W）。"""
        raw = self.client.query("MEAS:POW:ALL?")
        return [float(x) for x in raw.split(",")]

    def measure_voltage(self, ch: Channel) -> float:
        """MEAS:VOLT? 回读单通道电压（V）。"""
        self.select_channel(ch)
        return float(self.client.query("MEAS:VOLT?"))

    def measure_current(self, ch: Channel) -> float:
        """MEAS:CURR? 回读单通道电流（A）。"""
        self.select_channel(ch)
        return float(self.client.query("MEAS:CURR?"))

    def measure_power(self, ch: Channel) -> float:
        """MEAS:POW? 回读单通道功率（W）。"""
        self.select_channel(ch)
        return float(self.client.query("MEAS:POW?"))

    # ================= 复合控制命令 4.2.9 =================
    def apply_voltage(self, values: Optional[list[float]] = None) -> list[float]:
        """APPL:VOLT 三路电压设定（读写，读写均一次完成）。"""
        if values is None:
            raw = self.client.query("APPL:VOLT?")
            return [float(x) for x in raw.split(",")]
        if len(values) != 3:
            raise ValueError("values must have exactly 3 elements")
        self.client.write(f"APPL:VOLT {values[0]},{values[1]},{values[2]}")
        time.sleep(CMD_DELAY_S)

    def apply_current(self, values: Optional[list[float]] = None) -> list[float]:
        """APPL:CURR 三路电流设定（读写）。"""
        if values is None:
            raw = self.client.query("APPL:CURR?")
            return [float(x) for x in raw.split(",")]
        if len(values) != 3:
            raise ValueError("values must have exactly 3 elements")
        self.client.write(f"APPL:CURR {values[0]},{values[1]},{values[2]}")
        time.sleep(CMD_DELAY_S)

    # ================= IEEE-488 子系统 4.2.10 =================
    def ese(self, value: Optional[int] = None) -> int:
        """*ESE 标准事件使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query("*ESE?"))
        self.client.write(f"*ESE {value}")
        time.sleep(CMD_DELAY_S)

    def esr(self) -> int:
        """*ESR? 标准事件寄存器（读取后清零）。"""
        return int(self.client.query("*ESR?"))

    def opc(self, query: bool = False):
        """*OPC 操作完成标志；query=True 时 *OPC? 返回 1。"""
        if query:
            return int(self.client.query("*OPC?"))
        self.client.write("*OPC")
        time.sleep(CMD_DELAY_S)

    def psc(self, value: Optional[int] = None) -> int:
        """*PSC 上电使能寄存器清零策略（读写）。"""
        if value is None:
            return int(self.client.query("*PSC?"))
        self.client.write(f"*PSC {value}")
        time.sleep(CMD_DELAY_S)

    def rst(self) -> None:
        """*RST 复位所有参数到出厂状态（会覆盖全部设定，使用前务必备份）。

        实测：*RST 触发设备软复位（约 2-3s 就绪），复位后立即查询会收到
        开机横幅（如 'V0.1.4.3'），故写入后等待 3s。
        """
        self.client.write("*RST")
        time.sleep(3.0)

    def sre(self, value: Optional[int] = None) -> int:
        """*SRE 状态字节使能寄存器（读写）。"""
        if value is None:
            return int(self.client.query("*SRE?"))
        self.client.write(f"*SRE {value}")
        time.sleep(CMD_DELAY_S)

    def stb(self) -> int:
        """*STB? 状态字节寄存器（读取后清零）。"""
        return int(self.client.query("*STB?"))

    # ================= 安全保护 =================
    def _guard_set(self, ch: Channel) -> None:
        """safe_mode 下，目标通道输出 ON 时拒绝修改设定。"""
        if not self.safe_mode:
            return
        states = self.get_output_state()
        n = CH_ALIASES[ch] if isinstance(ch, str) else int(ch)
        if states[n - 1]:
            raise RuntimeError(
                f"safe_mode: CH{n} 输出开启中，拒绝修改设定；请先 set_output({n}, False)"
            )

    def _guard_all_outputs_off(self) -> None:
        """safe_mode 下，任一通道输出 ON 时拒绝模式切换（继电器联动）。"""
        if not self.safe_mode:
            return
        states = self.get_output_state()
        if any(states):
            raise RuntimeError("safe_mode: 有通道输出开启中，拒绝切换输出模式")

    # ================= 便捷快照 =================
    def snapshot(self) -> dict:
        """读取全部常用状态（只读，不改动设备）。"""
        return {
            "idn": self.idn(),
            "version": self.version(),
            "measure_voltage_v": self.measure_voltage_all(),
            "measure_current_a": self.measure_current_all(),
            "measure_power_w": self.measure_power_all(),
            "set_voltage_v": self.get_voltage_set(),
            "set_current_a": self.get_current_set(),
            "ovp_v": [self.get_ovp(i) for i in (1, 2, 3)],
            "ocp_a": [self.get_ocp(i) for i in (1, 2, 3)],
            "output_on": self.get_output_state(),
            "track_mode": self.track_mode(),
            "series_mode": self.series_mode(),
            "parallel_mode": self.parallel_mode(),
            "output_timer_s": self.output_timer(),
            "couple_trig": self.couple_trig(),
        }

    # 兼容旧名：三路复合读取
    def get_voltage_set(self) -> list[float]:
        return self.apply_voltage()

    def get_current_set(self) -> list[float]:
        return self.apply_current()
