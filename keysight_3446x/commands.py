"""Keysight Truevolt 系列（34461A/34465A/34470A 基准）六位半万用表 SCPI 常量。

来源：docs/Truevolt_Series_Operating_and_Service_Guide_output/（583 页提取版，
SCPI Programming Reference 章节）。实测基准：34465A 固件 A.03.02（VXI-11 inst0）。
约定：标准 Keysight SCPI；错误码 +0,"No error"；测量返回 ASCII 科学计数。
"""

IDN = "*IDN?"
OPT = "*OPT?"

SYST_ERR = ":SYST:ERR?"
CONF_Q = ":CONF?"                       # 当前功能/量程/分辨率

# 单次测量（自动触发，读后即弃）
MEAS_VOLT_DC = ":MEAS:VOLT:DC?"
MEAS_VOLT_AC = ":MEAS:VOLT:AC?"
MEAS_CURR_DC = ":MEAS:CURR:DC?"
MEAS_CURR_AC = ":MEAS:CURR:AC?"
MEAS_RES = ":MEAS:RES?"
MEAS_FRES = ":MEAS:FRES?"
MEAS_CONT = ":MEAS:CONT?"
MEAS_CAP = ":MEAS:CAP?"
MEAS_DIOD = ":MEAS:DIOD?"
MEAS_FREQ = ":MEAS:FREQ?"
READ = ":READ?"                          # 按当前 CONF 功能测量

# 配置类
CONF_VOLT_DC = ":CONF:VOLT:DC"
CONF_VOLT_AC = ":CONF:VOLT:AC"
CONF_RES = ":CONF:RES"
CONF_FREQ = ":CONF:FREQ"

SENS_VOLT_NPLC = ":SENS:VOLT:DC:NPLC"    # 积分时间 0.02~100 PLC
SENS_VOLT_APER = ":SENS:VOLT:DC:APER"    # 孔径时间 s
SENS_COUNT = ":SENS:COUN"                # 采样数（READ? 返回个数）
TRIG_SOURCE = ":TRIG:SOUR"               # IMMediate|BUS|EXT|TIMer

DATA_LAST = ":DATA:LAST?"                # 最近一次读数（不触发新测量）
STAT_PRES = ":STAT:PRES"
