"""RIGOL DHO 系列数字示波器 SCPI 命令常量。

来源：DHO800/DHO900 编程手册（提取版见 docs/DHO800编程手册_output/），
实测基准机型 DHO924S（固件 KFCVME50114，raw socket 5555 + \n 终止符）。

约定：
    - 命令前导 ':' 必需（如 ':RUN'），大小写不敏感；
    - 布尔写接受 ON|OFF|1|0，查询返回 0|1；
    - 通道源写作 CHANnel<n>，查询返回缩写 CHAN<n>；
    - 波形电压换算(BYTE 格式)：voltage = (raw - YORigin - YREFerence) * YINCrement；
    - 命令失败后查 :SYSTem:ERRor? 取错误队列。
"""

# ---- 控制流（手册 3.1）----
CLEAR = ":CLEar"
RUN = ":RUN"
STOP = ":STOP"
SINGLE = ":SINGle"
TFORCE = ":TFORce"
AUTOSET = ":AUToset"

# ---- 触发子系统（手册 3.27）----
TRIG_MODE = ":TRIGger:MODE"
TRIG_STATUS = ":TRIGger:STATus?"
TRIG_SWEEP = ":TRIGger:SWEep"
TRIG_COUP = ":TRIGger:COUPling"
EDGE_SOUR = ":TRIGger:EDGE:SOURce"
EDGE_SLOP = ":TRIGger:EDGE:SLOPe"
EDGE_LEV = ":TRIGger:EDGE:LEVel"

# ---- 采集子系统（手册 3.3）----
ACQ_MDEP = ":ACQuire:MDEPth"
ACQ_TYPE = ":ACQuire:TYPE"
ACQ_SRAT = ":ACQuire:SRATe?"

# ---- 通道子系统（手册 3.6，<n>=1..4）----
CHAN_DISP = ":CHANnel{n}:DISPlay"
CHAN_COUP = ":CHANnel{n}:COUPling"
CHAN_VERN = ":CHANnel{n}:VERNier"
CHAN_INV = ":CHANnel{n}:INVert"
CHAN_BWL = ":CHANnel{n}:BWLimit"
CHAN_SCALE = ":CHANnel{n}:SCALe"
CHAN_OFFS = ":CHANnel{n}:OFFSet"
CHAN_PROBE = ":CHANnel{n}:PROBe"
CHAN_UNITS = ":CHANnel{n}:UNITs"

# ---- 时基（手册 3.26）----
TB_SCALE = ":TIMebase:MAIN:SCALe"
TB_OFFSET = ":TIMebase:MAIN:OFFSet"

# ---- 测量子系统（手册 3.17）----
MEAS_ITEM = ":MEASure:ITEM"
MEAS_CLEAR = ":MEASure:CLEar"

# ---- 波形读取（手册 3.28）----
WAV_SOUR = ":WAVeform:SOURce"
WAV_MODE = ":WAVeform:MODE"
WAV_FMT = ":WAVeform:FORMat"
WAV_POINTS = ":WAVeform:POINts"
WAV_START = ":WAVeform:STARt"
WAV_STOP = ":WAVeform:STOP"
WAV_DATA = ":WAVeform:DATA?"
WAV_XINC = ":WAVeform:XINCrement?"
WAV_XORG = ":WAVeform:XORigin?"
WAV_YINC = ":WAVeform:YINCrement?"
WAV_YORG = ":WAVeform:YORigin?"
WAV_YREF = ":WAVeform:YREFerence?"

# ---- 系统（手册 3.24）----
SYST_ERR = ":SYSTem:ERRor?"
SYST_VERS = ":SYSTem:VERSion?"
SYST_BEEP = ":SYSTem:BEEPer"

# ================= 复位族：两个命令、两种语义（**故意不暴露为公开 API**）=================
#
# ⚠ 两者都属 AGENTS.md §二「禁止复位类命令」：MCP 通用写口已黑名单拦截，
#    **库内不提供任何公开方法**（既没有 reset() 也没有 factory_reset()），
#    需要时走受控脚本：`TEST_SCRIPTS/common/rigol_scope_reset.py --allow-reset`。
#
# 为什么保留常量（而不是删掉）：① 语义要写清楚，免得下次又把两者搞混；
#    ② 命令审计器要能看到它们有手册出处（3.24.11 / 3.12.2）；③ "万一要用"时不必现查手册。
#
# 语义（**已按手册原文核对；DHO800/900 与 MHO900 两个系列一致**）：
#   :SYSTem:RESet = 「使系统重新上电」——**重启仪器，不是恢复出厂设置**。
#                   手册 DHO 3.24.11 / MHO 3.24.12。旧 dho.py 的 docstring 曾写
#                   "恢复出厂默认"，是错的（2026-09-15 按手册更正并删除该错误方法）。
#   *RST          = 「将仪器恢复至出厂默认状态」——**这才是恢复出厂**。
#                   手册 DHO 3.12.2 / MHO 3.12.2；执行后通道/时基/触发/测量配置全部清零。
#
# 风险（真机经验，用之前先想清楚）：
#   - 重启：设备短暂离线（数十秒），远程会话断开需重连并核对 *IDN?；屏上正在进行的
#     采集/测量全部丢失；**面板前有人会看到仪器突然重启**。
#   - 恢复出厂：现场设定全清零（别人调好的通道/触发电平一起没）——共享实验台上属
#     破坏性操作，除用户显式授权外一律不做。
SYST_RESET = ":SYSTem:RESet"     # 重启（重新上电），**非**恢复出厂
RST = "*RST"                     # 恢复出厂默认（IEEE-488.2 公共命令）

# :MEASure:ITEM? 可用测量项（手册 3.17.2 表）
MEAS_ITEMS = (
    "VMAX", "VMIN", "VPP", "VTOP", "VBASe", "VAMP", "VAVG", "VRMS",
    "OVERshoot", "PREShoot", "MARea", "MPARea", "PERiod", "FREQuency",
    "RTIMe", "FTIMe", "PWIDth", "NWIDth", "PDUTy", "NDUTy", "TVMAX",
    "TVMIN", "PSLewrate", "NSLewrate", "VUPPer", "VMID", "VLOWer",
    "VARiance", "PVRMs", "PPULses", "NPULses", "PEDGes", "NEDGes",
)

# :ACQuire:MDEPth 存储深度可选值（DHO800 上限 25M，DHO900 上限 50M）
ACQ_DEPTHS = ("AUTO", "1k", "10k", "100k", "1M", "10M", "25M", "50M")

# :WAVeform:SOURce 通道源（D0~D15 仅 DHO900 系列）
WAV_SOURCES = (
    tuple(f"CHANnel{i}" for i in range(1, 5))
    + tuple(f"D{i}" for i in range(16))
    + tuple(f"MATH{i}" for i in range(1, 5))
)

# ================= 家族事实指针 =================
# **取值**（采集方式枚举/测量项表/触发类型/点数上限/能力开关有无…）集中在
# `rigol_scope/families.py` 的 Family 表（那里逐项标注了手册出处，避免两处维护）；
# 本文件只保留**命令拼写**——命令审计器按本系列手册逐条核对的就是这些。
# 本系列与另一系列的差异清单见 `docs/rigol_scope_compare_20260915.md`。
