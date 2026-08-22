"""DH1766 SCPI 命令常量与协议说明。

命令语法来源：DH1766 系列用户手册 第四章《远程控制与指令集》。
SCPI-99 合规说明：
    - IEEE 488.2 通用命令：*CLS/*ESE/*ESR?/*IDN?/*OPC/*PSC/*RST/*SRE/*STB?
      （手册 4.2.10 未列 *TST?/*WAI，实测固件 V0.1.4.3 不支持）
    - 布尔参数/响应按 SCPI-99 §7.3：写接受 ON|OFF|1|0，查询返回 0|1
    - 查询无副作用原则：本设备 STATus:*?/ESR?/STB? 事件寄存器读取即清零
      属 IEEE 488.2 事件寄存器标准行为（手册明示"读取后清零"）
    - 通道用 CH1|CH2|CH3 文本参数（INST）或 1|2|3 数字参数（INST:NSEL），
      为设备自定义（非标准数字后缀），按手册实现
    - APPLy:* 复合控制为设备扩展命令（SCPI-99 无此子系统），按手册实现
"""
from __future__ import annotations

# ---- IEEE 488.2 通用命令 ----
CLS = "*CLS"
ESE = "*ESE"
ESR = "*ESR?"
IDN = "*IDN?"
OPC = "*OPC"
PSC = "*PSC"
RST = "*RST"
SRE = "*SRE"
STB = "*STB?"
TRG = "*TRG"

# ---- 系统指令集（手册 4.2.1）----
SYST_ERR = "SYST:ERR?"
SYST_VERS = "SYST:VERS?"
SYST_BEEP = "SYST:BEEP"
SYST_LOC = "SYST:LOC"
SYST_REM = "SYST:REM"
SYST_RWL = "SYST:RWL"
SYST_RLST = "SYST:COMM:RLST:STAT?"

# ---- 状态指令集（手册 4.2.2）----
STAT_PRES = "STAT:PRES"
STAT_QUES_ENAB = "STAT:QUES:ENAB"
STAT_QUES = "STAT:QUES?"
STAT_QUES_COND = "STAT:QUES:COND?"
STAT_OPER_ENAB = "STAT:OPER:ENAB"
STAT_OPER = "STAT:OPER?"
STAT_OPER_COND = "STAT:OPER:COND?"
STAT_INST_ISUM = "STAT:QUES:INST:ISUM{n}:{node}?"  # node=COND|EVEN

# ---- 通道设定（手册 4.2.3）----
INST_SEL = "INST"
INST_NSEL = "INST:NSEL"
INST_COUP_TRIG = "INST:COUP:TRIG"

# ---- 电压（手册 4.2.4）----
VOLT = "VOLT"
VOLT_MODE = "VOLT:MODE"
VOLT_PROT = "VOLT:PROT"

# ---- 触发（手册 4.2.5）----
INIT = "INIT"
INIT_DEL = "INIT:DEL"
INIT_SOUR = "INIT:SOUR"

# ---- 电流（手册 4.2.6）----
CURR = "CURR"
CURR_MODE = "CURR:MODE"
CURR_PROT = "CURR:PROT"

# ---- 输出（手册 4.2.7）----
OUTP = "OUTP"
OUTP_TRAC = "OUTP:TRAC"
OUTP_SERI = "OUTP:SERI"
OUTP_PARA = "OUTP:PARA"
OUTP_TIM = "OUTP:TIM:DATA"

# ---- 测量（手册 4.2.8）----
MEAS_VOLT = "MEAS:VOLT"
MEAS_CURR = "MEAS:CURR"
MEAS_POW = "MEAS:POW"

# ---- 复合控制（手册 4.2.9，设备扩展）----
APPL_VOLT = "APPL:VOLT"
APPL_CURR = "APPL:CURR"
APPL_OUTP = "APPL:OUTP"

# 错误码速查（手册 4.2.1 错误表）
ERROR_CODES = {
    -101: "Invalid character",
    -103: "Invalid separator",
    -108: "Parameter not allowed",
    -109: "Missing parameter",
    -113: "Undefined header",
    -131: "Invalid suffix",
    -138: "Suffix not allowed",
    -151: "Invalid string data",
    -170: "Expression error",
    -200: "Execution error",
    -201: "Invalid",
    -222: "Data out of range",
    -224: "Illegal parameter value",
    -310: "System error",
    -330: "Self test failed",
    -360: "Communication error",
    -800: "Operation complete",
}
