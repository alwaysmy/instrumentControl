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
MEAS_ADV_CLEAR = ":MEASure:ADVanced:CLEar"
MEAS_ADV_TYPE_Q = ":MEASure:ADVanced:P{n}:TYPE?"
MEAS_ADV_TYPE_W = ":MEASure:ADVanced:P{n}:TYPE {t}"
MEAS_ADV_VAL = ":MEASure:ADVanced:P{n}:VALue?"

WAV_SOUR = ":WAVeform:SOURce"
WAV_PREAMBLE = ":WAVeform:PREamble?"
WAV_MAXPOINT = ":WAVeform:MAXPoint?"
WAV_START = ":WAVeform:STARt"
WAV_POINTS = ":WAVeform:POINt"
WAV_WIDTH = ":WAVeform:WIDTh"
WAV_DATA = "WAV:DATA?"

SCREEN_BMP = "PRIN? BMP"

SYST_ERR = ":SYST:ERR?"
SYST_FACT = ":SYST:FACT"       # 恢复出厂（危险，勿在自动化中调用）

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
