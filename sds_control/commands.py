"""Siglent SDS 系列（SDS800X HD 基准）示波器 SCPI 命令常量与说明。

来源：docs/SDS800XHD_Series_ProgrammingGuide_CN11G_output/（495 页提取版）。
实测基准：SDS824X HD 固件 2.8.12.1.1.6.5（VXI-11 inst0）。

约定：
    - 通道写作 C1..C4（数字通道 D0..D15）；查询响应带命令头回显（如 "C1:VDIV 5.00E+00V"）；
    - 耦合查询用 C<n>:COUPLING?（响应头 C1:CPL），CPLE? 不被支持（实测）；
    - 波形电压 = raw/code*vdiv - offset；时间 = -(tdiv*10/2) + i*interval + delay；
      PREamble 二进制块偏移见 sds.py PREAMBLE_OFFSETS；
    - SCPI 字符串须以 \n 结尾（Socket 与 VISA 同理，VisaClient 已配 write_termination）。
"""

RUN = ":RUN"
STOP = ":STOP"
AUTOSET = ":AUTOSET"

# 采集子系统：实测 SDS824X HD 对全拼 ":ACQuire:MDEPth?" 不响应（超时），必须用短形式
ACQ_MDEP = "ACQ:MDEP?"
ACQ_TYPE = "ACQ:TYPE?"
ACQ_SRAT = "ACQ:SRAT?"

CHAN_DISP = "C{n}:TRA?"
CHAN_VDIV = "C{n}:VDIV?"
CHAN_VDIV_W = "C{n}:VDIV {val}V"
CHAN_OFST = "C{n}:OFST?"
CHAN_OFST_W = "C{n}:OFST {val}V"
CHAN_ATTN = "C{n}:ATTN?"
CHAN_COUPLING = "C{n}:COUPLING?"

TB_SCALE = "TDIV?"
TRIG_DELAY = "TRDL?"
TRIG_MODE = "TRIG:MODE?"
TRIG_STATUS = ":TRIGger:STATus?"   # 手册 3.27.3（Stop/TD/Wait/TRiggered...）
TRIG_EDGE_SOUR = "TRIG:EDGE:SOUR?" # 手册 :TRIGger:EDGE:SOURce（短形式）
TRIG_EDGE_SOUR_W = "TRIG:EDGE:SOUR {src}"
TRIG_EDGE_LEV = "TRIG:EDGE:LEV?"
TRIG_EDGE_LEV_W = "TRIG:EDGE:LEV {val}V"
TRIG_EDGE_SLOP = "TRIG:EDGE:SLOP?"

MEAS_ALL = "MEAS?"                 # 打开的测量项统计值
MEAS_MODE = ":MEASure:MODE"       # SIMPle/ADVanced（回读短格式 SIMP/ADV）
MEAS_ADV_CLEAR = ":MEASure:ADVanced:CLEar"
MEAS_ADV_SLOT = ":MEASure:ADVanced:P{n}"          # P 槽独立开关，n∈[1,12]
MEAS_ADV_TYPE_Q = ":MEASure:ADVanced:P{n}:TYPE?"
MEAS_ADV_TYPE_W = ":MEASure:ADVanced:P{n}:TYPE {t}"
MEAS_ADV_SOUR1 = ":MEASure:ADVanced:P{n}:SOURce1"  # 信源A
MEAS_ADV_SOUR2 = ":MEASure:ADVanced:P{n}:SOURce2"  # 信源B（双通道测量用）
MEAS_ADV_VAL = ":MEASure:ADVanced:P{n}:VALue?"

# ADVanced 单通道专用类型（手册表 5-1 有、SIMPle:ITEM 表无；2026-09-09 核对）。
# DTIMe1-4 需配合 THReshold1/2 使用。
MEAS_ADV_SINGLES = (
    "RISE10T90", "FALL90T10",
    "PSLOPE", "NSLOPE",
    "TSR", "TSF", "THR", "THF",
    "DTIMe1", "DTIMe2", "DTIMe3", "DTIMe4",
)

# 双通道测量类型（手册表 5-1）。PHA 已实测（2026-09-08：A=C2/B=C1 得 94.664°，
# 交换后 265.218°，和 359.882≈360，符号约定= B 相对 A 的相位）；其余仅手册出处。
MEAS_DUAL_TYPES = (
    "PHA", "SKEW",
    "FRR", "FRF", "FFR", "FFF",
    "LRR", "LRF", "LFR", "LFF",
)

# ---- 测量扩展（手册 3.17，p.172-185；2026-09-09 补全）----
MEAS_THR_SOUR = ":MEASure:THReshold:SOURce"     # 测量阈值源
MEAS_THR_TYPE = ":MEASure:THReshold:TYPE"       # PERCent|ABSolute
MEAS_THR_ABS = ":MEASure:THReshold:ABSolute"    # high,mid,low (NR3)
MEAS_THR_PERC = ":MEASure:THReshold:PERCent"    # high,mid,low (整型)
MEAS_GATE = ":MEASure:GATE"                     # ON|OFF 测量门限
MEAS_GATE_GA = ":MEASure:GATE:GA"               # 门限A位置 (NR3)
MEAS_GATE_GB = ":MEASure:GATE:GB"               # 门限B位置 (NR3)
MEAS_RDISP = ":MEASure:RDISplay"                # EMBedded|FLOating
MEAS_STAT = ":MEASure:ADVanced:STATistics"      # ON|OFF 统计开关
MEAS_STAT_AIM = ":MEASure:ADVanced:STATistics:AIMLimit"    # AIM 次数
MEAS_STAT_HIST = ":MEASure:ADVanced:STATistics:HISTOGram"  # ON|OFF
MEAS_STAT_MAX = ":MEASure:ADVanced:STATistics:MAXCount"    # [0,1024]
MEAS_STAT_RESET = ":MEASure:ADVanced:STATistics:RESet"     # 写
MEAS_ADV_STAT_Q = ":MEASure:ADVanced:P{n}:STATistics?"     # <type> 统计查询
MEAS_ADV_HIST_Q = ":MEASure:ADVanced:P{n}:SHIStory?"       # [n] 历史
MEAS_ADV_LINE = ":MEASure:ADVanced:LINenumber"             # [1,12]
MEAS_ADV_STYLE = ":MEASure:ADVanced:STYLe"                 # M1|M2
MEAS_ASTRATEGY = ":MEASure:ASTRategy"                      # AUTO|MANual
MEAS_ASTRA_BASE = ":MEASure:ASTRategy:BASE"                # HISTogram|MAX
MEAS_ASTRA_TOP = ":MEASure:ASTRategy:TOP"                  # HISTogram|MAX
MEAS_DTIME = ":MEASure:DTIMe{n}"                           # n∈[1,4]
MEAS_DTIME_NODES = ("EDGE1", "EDGE2", "SLOPe1", "SLOPe2",
                    "THReshold1", "THReshold2")

# P<n>:STATistics? 的查询类型
MEAS_STAT_TYPES = ("ALL", "CURRent", "MEAN", "MAXimum", "MINimum",
                   "STDev", "COUNt")

WAV_SOUR = ":WAVeform:SOURce"
WAV_PREAMBLE = ":WAVeform:PREamble?"
WAV_MAXPOINT = ":WAVeform:MAXPoint?"
WAV_START = ":WAVeform:STARt"
WAV_POINTS = ":WAVeform:POINt"
WAV_WIDTH = ":WAVeform:WIDTh"
WAV_DATA = "WAV:DATA?"

SCREEN_BMP = "PRIN? BMP"

SYST_ERR = ":SYST:ERR?"
# 注：恢复出厂请用面板操作。曾误列 ":SYST:FACT"（无手册出处，已删除）。

# :WAVeform:PREamble? 参数块字段偏移（手册 6.3 节官方实例）
PREAMBLE_OFFSETS = {
    "width": (0x20, "h"),
    "order": (0x22, "h"),
    "data_bytes": (0x3C, "i"),
    "point_num": (0x74, "i"),
    "fp": (0x84, "i"),
    "sp": (0x88, "i"),
    "vdiv": (0x9C, "f"),
    "offset": (0xA0, "f"),
    "code": (0xA4, "f"),
    "adc_bit": (0xAC, "h"),
    "interval": (0xB0, "f"),
    "delay": (0xB4, "d"),
    "tdiv": (0x144, "h"),
    "probe": (0x148, "f"),
}

# tdiv 字段为枚举索引（手册实例列表，100p~1k/div 共 40 档）
TDIV_ENUM = (
    [200e-12, 500e-12]
    + [x * 1e-9 for x in (1, 2, 5, 10, 20, 50, 100, 200, 500)]
    + [x * 1e-6 for x in (1, 2, 5, 10, 20, 50, 100, 200, 500)]
    + [x * 1e-3 for x in (1, 2, 5, 10, 20, 50, 100, 200, 500)]
    + [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
)
