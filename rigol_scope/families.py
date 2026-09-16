"""RIGOL 示波器家族差异表（DHO800/900 与 MHO900 的命令集差异）。

一份"事实表"：把两个系列**不同**的地方集中在此，共享内核 `rigol_scope.scope.RigolScope`
按型号取表行事。差异从手册逐条核对而来，出处见 `docs/rigol_scope_compare_20260915.md`。

不放进本文件的东西：命令常量的**拼写**仍留在各库自己的 `commands.py`（那是最靠近手册、
也最容易被审计器扫到的位置）；本文件只描述"哪些行为随家族变"。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 为什么是"自包含"而不是 import 各库的 commands.py：各库要 import 内核（拿 RigolScope），
# 内核若反过来 import 各库就成环。故**差异值**集中在本表（每项都标注手册出处），
# 各库 commands.py 只保留**命令拼写**——拼写才是命令审计器逐条核对手册的东西。
# 审计口径：本文件与 scope.py 一起按"两手册并集"核对（`audit_all_commands.py` 的
# `rigol_scope` 组）：共享命令必须两边都有，差异分支里的专用拼写命中其一即可。


@dataclass(frozen=True)
class Family:
    """一个示波器家族的行为差异集（只放**会随家族变**的字段）。"""

    name: str                      # "DHO" | "MHO"（*IDN? 匹配串）
    label: str                     # 人类可读名
    resolver_kind: str             # common/resolver.py 的 kind
    channels: int                  # 模拟通道数
    measure_clear: str             # 清全部测量项：DHO=:MEASure:CLEar / MHO=:MEASure:DELete
    acq_types: tuple[str, ...]     # :ACQuire:TYPE 合法值（第四态名字不同！）
    acq_depths: tuple[str, ...]
    acq_bits: Optional[tuple[int, ...]]      # :ACQuire:BITS（MHO 有 14/16，DHO 无此命令）
    chan_couplings: tuple[str, ...]
    chan_bwlimits: Optional[tuple[str, ...]]  # 带宽限制取值（DHO 随机型，故为 None 表示不校验）
    chan_impedances: Optional[tuple[str, ...]]  # :CHANnel<n>:IMPedance（仅 MHO）
    chan_units: tuple[str, ...]
    edge_slopes: tuple[str, ...]    # 边沿第三态：**两家族都是 RFALl**（曾误记为 RFail）
    trigger_types: tuple[str, ...]
    trigger_sweeps: tuple[str, ...]
    wav_modes: tuple[str, ...]
    wav_formats: tuple[str, ...]
    wav_normal_max_points: int      # NORMal 模式点数上限（两家族都是 1000）
    disp_formats: tuple[str, ...]
    measure_items: tuple[str, ...]
    measure_items_dual: tuple[str, ...]
    # 屏幕格数与 ADC 位数：**只有实测标定过的才填**，未标定一律 None——
    # 离屏判据/自动定标靠这些常量算窗口（`scope.vertical_window/fit_channel`），
    # 填错会让工具"自信地报错误结论"，比留空更坏（设计文档 §5 明确要求：
    # SDS/DHO 未实测前不要照抄 MHO 的值）。
    vdivs: Optional[int] = None            # 垂直格数；MHO984D 实测 8（见下）
    hdivs: Optional[int] = None            # 水平格数；MHO 反推 10，未单独标定
    adc_bits: Optional[int] = None         # ADC 位数（平直信号噪声底判据用）
    scale_range: Optional[tuple[float, float]] = None   # 垂直档位可设范围（V/div，自动定标的上限）
    ascii_waveform_has_tmc: bool = False   # MHO 实测 ASCII 不带 TMC 头；DHO 未实测，保守取 False
    notes: tuple[str, ...] = field(default_factory=tuple)


DHO = Family(
    name="DHO",
    label="RIGOL DHO800/900 示波器",
    resolver_kind="dho",
    channels=4,
    measure_clear=":MEASure:CLEar",      # 手册：CLEar 6 处、DELete 0 处（与 MHO 互斥）
    acq_types=("NORMal", "PEAK", "AVERages", "ULTRa"),   # 手册 3.3.4 第四态
    acq_depths=("AUTO", "1k", "10k", "100k", "1M", "10M", "25M", "50M"),
    acq_bits=None,                       # 手册无 :ACQuire:BITS（MHO 才有）
    chan_couplings=("AC", "DC", "GND"),  # 手册 3.6.2
    chan_bwlimits=None,                  # 随机型给值 → 不校验，交给设备判断
    chan_impedances=None,                # 手册无 :CHANnel<n>:Impedance（MHO 才有）
    chan_units=("WATT", "AMPere", "VOLTage", "UNKNown"),   # 手册 3.6.12
    edge_slopes=("POSitive", "NEGative", "RFALl"),         # 手册 3.27.8.2（非 RFail）
    # 手册 3.27.1 参数表逐字（17 项）：原先误抄了 MHO 的列表，多出 IIS/FLEXray/M1554
    # （DHO 手册 0 命中；M1554 连 MHO 手册也没有——MHO 是 M1553），2026-09-15 审计更正。
    # 注：CAN/LIN 仅 DHO900 系列支持（手册该节"说明"原文）。
    trigger_types=(
        "EDGE", "PULSe", "SLOPe", "VIDeo", "PATTern", "DURation", "TIMeout", "RUNT",
        "WINDow", "DELay", "SETup", "NEDGe", "RS232", "IIC", "SPI", "CAN", "LIN",
    ),
    trigger_sweeps=("AUTO", "NORMal", "SINGle"),           # 手册 3.27.4
    wav_modes=("NORMal", "MAXimum", "RAW"),                # 手册 3.28.2
    wav_formats=("WORD", "BYTE", "ASCii"),                 # 手册 3.28.3
    wav_normal_max_points=1000,                            # 手册 3.28.4：NORMal 1~1000
    disp_formats=("BMP", "PNG", "JPG"),                    # 手册 3.9.7
    measure_items=(
        "VMAX", "VMIN", "VPP", "VTOP", "VBASe", "VAMP", "VAVG", "VRMS",
        "OVERshoot", "PREShoot", "MARea", "MPARea", "PERiod", "FREQuency",
        "RTIMe", "FTIMe", "PWIDth", "NWIDth", "PDUTy", "NDUTy", "TVMAX",
        "TVMIN", "PSLewrate", "NSLewrate", "VUPPer", "VMID", "VLOWer",
        "VARiance", "PVRMs", "PPULses", "NPULses", "PEDGes", "NEDGes", "ACRMs",
    ),
    # DHO 手册同样记载双信源项（RRDelay/RRPHase 等各 12 处）——合并前 DHO 驱动未暴露，
    # 属**能力缺口**而非仪器缺口，合并后补齐。
    measure_items_dual=("RRDelay", "RFDelay", "FRDelay", "FFDelay",
                        "RRPHase", "RFPHase", "FRPHase", "FFPHase"),
    # 格数/位数**未标定**（DHO 不在本台，不照抄 MHO 的值——照抄会让离屏判据
    # 得出错误的窗口，比"没有该能力"更危险）。DHO 回台后按设计文档 §5 一次实测填上。
    vdivs=None, hdivs=None, adc_bits=None,
    ascii_waveform_has_tmc=False,        # DHO 真机未验（清单见 verify_rigol_scope_shared.py 头部）
    notes=("NORMal 模式点数上限 1000（手册 3.28.4）",
           "无 :ACQuire:BITS / :CHANnel<n>:Impedance（MHO 才有）",
           "波形 ASCII 是否带 TMC 头未实测，暂按无处理",
           "垂直/水平格数与中心约定**未实测**→ vertical_window()/fit_channel() 不适用"),
)

MHO = Family(
    name="MHO",
    label="RIGOL MHO900 系列示波器",
    resolver_kind="mho",
    channels=4,
    measure_clear=":MEASure:DELete",     # 手册 3.17.3：CLEar 0 处、DELete 3 处（与 DHO 互斥）
    acq_types=("NORMal", "PEAK", "AVERages", "HRESolution"),   # 手册 3.3.3 第四态
    acq_depths=("AUTO", "1k", "10k", "100k", "1M", "10M", "25M", "50M",
                "100M", "125M", "200M", "250M", "500M"),
    acq_bits=(14, 16),                   # 手册 3.3.5
    chan_couplings=("AC", "DC", "GND"),
    chan_bwlimits=("OFF", "ON", "20M", "250M"),   # 手册 3.6.1
    chan_impedances=("OMEG", "FIFTy"),   # 手册 3.6.7
    chan_units=("WATT", "AMPere", "VOLTage", "UNKNown"),
    edge_slopes=("POSitive", "NEGative", "RFALl"),   # 两系列一致（曾误记为 RFail）
    trigger_types=(
        "EDGE", "PULSe", "SLOPe", "VIDeo", "PATTern", "DURation", "TIMeout",
        "RUNT", "WINDow", "DELay", "SETup", "NEDGe", "RS232", "IIC", "SPI",
        "CAN", "LIN", "IIS", "FLEXray", "M1553",
    ),
    trigger_sweeps=("AUTO", "NORMal", "SINGle"),
    wav_modes=("NORMal", "MAXimum", "RAW"),
    wav_formats=("WORD", "BYTE", "ASCii"),
    wav_normal_max_points=1000,          # 手册 3.28.4
    disp_formats=("BMP", "PNG", "JPG"),
    measure_items=(
        "VMAX", "VMIN", "VPP", "VTOP", "VBASe", "VAMP", "VAVG", "VRMS",
        "OVERshoot", "PREShoot", "MARea", "MPARea", "PERiod", "FREQuency",
        "RTIMe", "FTIMe", "PWIDth", "NWIDth", "PDUTy", "NDUTy", "TVMAX",
        "TVMIN", "PSLewrate", "NSLewrate", "VUPPer", "VMID", "VLOWer",
        "PVRMs", "PPULses", "NPULses", "PEDGes", "NEDGes", "ACRMs",
    ),
    measure_items_dual=("RRDelay", "RFDelay", "FRDelay", "FFDelay",
        "RRPHase", "RFPHase", "FRPHase", "FFPHase"),
    # 标定证据（2026-09-15 现场实测，`docs/tool_optimization_20260915.md` §P1-3(d)）：
    # 垂直 8 格 + "屏幕中心 = −offset"。scale 0.9/offset −3.5 → 窗口上沿 7.1 V 时
    # 7.4816 V 的信号读 9.9E37；scale 1.0 → 上沿 7.5 V 时读到 7.4825 V。
    # 18 mV 余量下两条都对上，故定量成立。
    vdivs=8,
    hdivs=10,        # 由"20µs/div 测不到 5kHz（窗口≈1 周期）、100µs/div 立刻读到 4.9993kHz"
                     # 反推 ≈10 格；**未单独标定**，仅用于"边沿够不够"的提示措辞（按 10 格估算）
    adc_bits=12,     # MHO984D 12-bit（DEVICE_FACTS.local.md）
    scale_range=(200e-6, 10.0),   # 垂直灵敏度 200 μV/div~10 V/div（用户手册 §1.3 原文）
    ascii_waveform_has_tmc=False,        # 实测：ASCII 直接回文本，无 TMC 头
    notes=("无 *OPT? 支持（查询超时，勿引入）",
           "采样率随通道数下降：1~2ch 4GSa/s、3~4ch 1GSa/s",
           "波形 ASCII 格式不带 TMC 头（二进制才带）",
           "垂直 8 格、中心 = −offset（实测标定，见 tool_optimization_20260915.md）"),
)

FAMILIES: dict[str, Family] = {"DHO": DHO, "MHO": MHO}


def family_of(model: str | None) -> Family:
    """按型号串取家族表：以 'MHO' 开头 → MHO，其余按 DHO。"""
    m = (model or "DHO").strip().upper()
    return MHO if m.startswith("MHO") else DHO
