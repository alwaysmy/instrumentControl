"""Siglent SDG 系列（SDG2000X 基准）函数/任意波形发生器 SCPI 常量。

来源：docs/SDG_Programming-Guide_PG02_C02C_output/（175 页提取版）。
实测基准：SDG2122X 固件 2.01.01.38R4（VXI-11 inst0）。
约定：通道 C1/C2；查询响应带回显头（"C1:BSWV ..."）；
     参数写法为逗号键值对（如 "C1:BSWV WVTP,SINE,FRQ,1000HZ"）。
"""

OUTP_Q = "{ch}:OUTP?"
OUTP_W = "{ch}:OUTP {state}"

BSWV_Q = "{ch}:BSWV?"            # 基础波形参数整体查询（子参数式 WVTP? 不被支持，实测）
BSWV_W = "{ch}:BSWV {params}"    # 例：WVTP,SINE,FRQ,1000HZ,AMP,1.0V,OFST,0V

MDWV_Q = "{ch}:MDWV?"            # 调制参数
SWPWV_Q = "{ch}:SWEEPWV?"        # 扫频参数（部分型号支持）

SYST_ERR = ":SYST:ERR?"
SYST_VERS = ":SYST:VERS?"

# BSWV? 返回的键值串 → 规范解析用键名（保持原样返回亦可）
BSWV_KEYS = (
    "WVTP", "FRQ", "PERI", "AMP", "AMPVRMS", "AMPDBM", "OFST",
    "HLEV", "LLEV", "PHSE", "DLY", "WIDTH", "RISE", "FALL", "SQU",
)
