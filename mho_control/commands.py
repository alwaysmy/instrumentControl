"""RIGOL MHO900 系列数字示波器 SCPI 命令常量。

来源：`docs/MHO900编程手册_output/MHO900编程手册.md`（MHO900 系列编程手册提取版，
405 页/406 条命令头）；实测基准机型 **MHO984D**（固件 00.01.00，VXI-11 inst0）。

与同门 DHO800/900 库（`dho_control`）**不可互抄**——命令集不同，实测差异：
    - MHO 清除测量项是 `:MEASure:DELete`，DHO 是 `:MEASure:CLEar`；
    - MHO 边沿类型第三态是 `RFALl`，DHO 是 `RFail`；
    - MHO 有 `:SYSTem:LOCKed`（屏幕/键盘锁定，属安全红线禁止命令）；
    - MHO 无 `*OPT?` 支持（实测超时，勿引入）。

约定（与 dho_control 一致）：
    - 命令前导 ':' 必需，大小写不敏感；
    - 布尔写接受 ON|OFF|1|0，查询返回 0|1；
    - 通道源写作 CHANnel<n>，查询返回缩写 CHAN<n>；
    - 波形电压换算：voltage = (raw - YORigin - YREFerence) * YINCrement；
    - 命令失败后查 :SYSTem:ERRor? 取错误队列。
"""

# ---- 控制流（手册 3.1）----
CLEAR = ":CLEar"
RUN = ":RUN"
STOP = ":STOP"
SINGLE = ":SINGle"
TFORCE = ":TFORce"

# ---- 波形自动设置（手册 3.2）----
AUTOSET = ":AUToset"

# ---- 采集子系统（手册 3.3）----
ACQ_MDEP = ":ACQuire:MDEPth"
ACQ_TYPE = ":ACQuire:TYPE"
ACQ_BITS = ":ACQuire:BITS"
ACQ_SRAT = ":ACQuire:SRATe?"

# ---- 通道子系统（手册 3.6，<n>=1..4）----
CHAN_DISP = ":CHANnel{n}:DISPlay"
CHAN_COUP = ":CHANnel{n}:COUPling"
CHAN_SCALE = ":CHANnel{n}:SCALe"
CHAN_OFFS = ":CHANnel{n}:OFFSet"
CHAN_PROBE = ":CHANnel{n}:PROBe"
CHAN_BWL = ":CHANnel{n}:BWLimit"
CHAN_IMP = ":CHANnel{n}:IMPedance"
CHAN_UNITS = ":CHANnel{n}:UNITs"
CHAN_INV = ":CHANnel{n}:INVert"
CHAN_VERN = ":CHANnel{n}:VERNier"

# ---- 显示屏（手册 3.9）----
DISP_CLEAR = ":DISPlay:CLEar"
DISP_DATA = ":DISPlay:DATA?"      # [<type>]，<type> ∈ {BMP|PNG|JPG}，TMC 头+位图流

# ---- 测量子系统（手册 3.17）----
MEAS_SOUR = ":MEASure:SOURce"
MEAS_ITEM = ":MEASure:ITEM"       # 写 = 打开测量项；"?" = 查询当前值
MEAS_DELETE = ":MEASure:DELete"   # 清除所有已打开的测量项

# ---- 时基（手册 3.26.4/3.26.5）----
TB_SCALE = ":TIMebase:MAIN:SCALe"
TB_OFFSET = ":TIMebase:MAIN:OFFSet"

# ---- 触发子系统（手册 3.27）----
TRIG_MODE = ":TRIGger:MODE"
TRIG_STATUS = ":TRIGger:STATus?"
TRIG_SWEEP = ":TRIGger:SWEep"
TRIG_COUP = ":TRIGger:COUPling"
EDGE_SOUR = ":TRIGger:EDGE:SOURce"
EDGE_SLOP = ":TRIGger:EDGE:SLOPe"
EDGE_LEV = ":TRIGger:EDGE:LEVel"

# ---- 波形读取（手册 3.28）----
WAV_SOUR = ":WAVeform:SOURce"
WAV_MODE = ":WAVeform:MODE"
WAV_FMT = ":WAVeform:FORMat"
WAV_POINTS = ":WAVeform:POINts"
WAV_START = ":WAVeform:STARt"     # 1 起始（第 1 点）
WAV_STOP = ":WAVeform:STOP"
WAV_DATA = ":WAVeform:DATA?"
WAV_PREAMBLE = ":WAVeform:PREamble?"   # 10 个参数，逗号分隔（ASCII，非二进制块）
WAV_XINC = ":WAVeform:XINCrement?"
WAV_XORG = ":WAVeform:XORigin?"
WAV_YINC = ":WAVeform:YINCrement?"
WAV_YORG = ":WAVeform:YORigin?"
WAV_YREF = ":WAVeform:YREFerence?"

# ---- 系统（手册 3.24）----
SYST_ERR = ":SYSTem:ERRor?"
SYST_VERS = ":SYSTem:VERSion?"
SYST_BEEP = ":SYSTem:BEEPer"

# :MEASure:ITEM 单信源测量项（手册 3.17.2 参数表逐字）
MEAS_ITEMS_SINGLE = (
    "VMAX", "VMIN", "VPP", "VTOP", "VBASe", "VAMP", "VAVG", "VRMS",
    "OVERshoot", "PREShoot", "MARea", "MPARea", "PERiod", "FREQuency",
    "RTIMe", "FTIMe", "PWIDth", "NWIDth", "PDUTy", "NDUTy", "TVMAX",
    "TVMIN", "PSLewrate", "NSLewrate", "VUPPer", "VMID", "VLOWer",
    "PVRMs", "PPULses", "NPULses", "PEDGes", "NEDGes", "ACRMs",
)

# :MEASure:ITEM 双信源测量项（手册 3.17.2 同表；延迟 Delay / 相位 PHase 四组合）
MEAS_ITEMS_DUAL = (
    "RRDelay", "RFDelay", "FRDelay", "FFDelay",
    "RRPHase", "RFPHase", "FRPHase", "FFPHase",
)

MEAS_ITEMS = MEAS_ITEMS_SINGLE + MEAS_ITEMS_DUAL

# :ACQuire:MDEPth 可选值（手册 3.3.2 参数表；本机实测上限受机型/选件限制）
ACQ_DEPTHS = (
    "AUTO", "1k", "10k", "100k", "1M", "10M", "25M", "50M", "100M",
    "125M", "200M", "250M", "500M",
)

# :ACQuire:TYPE 采集方式（手册 3.3.3）
ACQ_TYPES = ("NORMal", "PEAK", "AVERages", "HRESolution")

# :ACQuire:BITS 位组长度（手册 3.3.5）
ACQ_BITS = (14, 16)

# :CHANnel<n>:BWLimit 带宽限制（手册 3.6.1）
CHAN_BWLIMITS = ("OFF", "ON", "20M", "250M")

# :CHANnel<n>:COUPling 耦合（手册 3.6.2）
CHAN_COUPLINGS = ("AC", "DC", "GND")

# :CHANnel<n>:IMPedance 输入阻抗（手册 3.6.7）
CHAN_IMPEDANCES = ("OMEG", "FIFTy")

# :CHANnel<n>:UNITs 单位（手册 3.6.12）
CHAN_UNITS = ("WATT", "AMPere", "VOLTage", "UNKNown")

# :TRIGger:MODE 触发类型（手册 3.27.1）
TRIG_TYPES = (
    "EDGE", "PULSe", "SLOPe", "VIDeo", "PATTern", "DURation", "TIMeout",
    "RUNT", "WINDow", "DELay", "SETup", "NEDGe", "RS232", "IIC", "SPI",
    "CAN", "LIN", "IIS", "FLEXray", "M1553",
)

# :TRIGger:SWEep 触发方式（手册 3.27.4）
TRIG_SWEEPS = ("AUTO", "NORMal", "SINGle")

# :TRIGger:COUPling 触发耦合（手册 3.27.2）
TRIG_COUPLINGS = ("AC", "DC", "LFReject", "HFReject")

# :TRIGger:EDGE:SLOPe 边沿类型（手册 3.27.8.2；注意第三态是 RFALl，与 DHO 的 RFail 不同）
EDGE_SLOPES = ("POSitive", "NEGative", "RFALl")

# :TRIGger:STATus? 触发状态返回集（手册 3.27.3）
TRIG_STATES = ("TD", "WAIT", "RUN", "AUTO", "STOP")

# :WAVeform:MODE 读取模式（手册 3.28.2；RAW 必须在 STOP 态读且读取期间不可操作仪器）
WAV_MODES = ("NORMal", "MAXimum", "RAW")

# :WAVeform:FORMat 数据格式（手册 3.28.3）
WAV_FORMATS = ("WORD", "BYTE", "ASCii")

# :WAVeform:POINts 上限（手册 3.28.4）：NORMal 模式固定 1~1000；RAW/MAXimum 随深度/屏点数
WAV_NORMAL_MAX_POINTS = 1000

# :WAVeform:SOURce 通道源（手册 3.28.1；D0~D15 需插入逻辑分析探头）
WAV_SOURCES = (
    tuple(f"CHANnel{i}" for i in range(1, 5))
    + tuple(f"MATH{i}" for i in range(1, 5))
    + tuple(f"D{i}" for i in range(16))
)

# :DISPlay:DATA? 位图格式（手册 3.9.8）
DISP_FORMATS = ("BMP", "PNG", "JPG")

# ================= 家族事实指针 =================
# **取值**（采集方式枚举/测量项表/触发类型/点数上限/能力开关有无…）集中在
# `rigol_scope/families.py` 的 Family 表（那里逐项标注了手册出处，避免两处维护）；
# 本文件只保留**命令拼写**——命令审计器按本系列手册逐条核对的就是这些。
# 本系列与另一系列的差异清单见 `docs/rigol_scope_compare_20260915.md`。
