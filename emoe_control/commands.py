"""Emoe R&D EmoeCalibrator 校准器 SCPI 命令常量。

⚠ 状态：编程手册未提供，本文件仅收录 IEEE 488.2/SCPI 标准要求的通用命令，
均标注"待实测确认"。业务命令（输出/量程/设置）严禁猜测——待手册到位后
按手册逐条补充并实测。

已实测确认（2026-08-24，ASRL31 串口）：
    *IDN? -> 'Emoe R&D,EmoeCalibrator,<serial>,<asset>'
"""

# ---- IEEE 488.2 必需命令（SCPI-99 §4.11；存在性待逐条实测确认）----
IDN = "*IDN?"            # 已实测 ✓
CLS = "*CLS"
ESE = "*ESE"
ESR = "*ESR?"
OPC = "*OPC"
RST = "*RST"             # ⚠ 复位类：自动化禁用，需用户显式授权
SRE = "*SRE"
STB = "*STB?"
TST = "*TST?"

# ---- SCPI 标准系统命令（预期实现，待确认）----
SYST_ERR = ":SYST:ERR?"
SYST_VERS = ":SYST:VERS?"

# ---- 业务命令（占位）----
# 待编程手册提供后补充：校准器核心功能（电压/电流输出、量程、极性等）
