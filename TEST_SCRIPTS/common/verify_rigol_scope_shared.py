"""共享内核 `rigol_scope` 的**离线**闭环测试：两家族一次跑通，无需任何仪器。

背景：DHO800/900 与 MHO900 已合并到同一内核（命令集 97% 重合，见
`docs/rigol_scope_compare_20260915.md`）。本实验台**只有 MHO**（DHO 不在），
所以 DHO 路径必须靠"假传输回放手册响应"来验证；MHO 另有真机验收
（`TEST_SCRIPTS/mho/verify_mho.py`，45/45）。

用法：
    python TEST_SCRIPTS/common/verify_rigol_scope_shared.py

覆盖：
    §1 传输层：查询/写入/原始读取是否走通、命令拼写是否正确落盘
    §2 家族差异：清测量命令、采集第四态、:ACQuire:BITS、:CHANnel<n>:Impedance 的有无
    §3 波形解析：BYTE/WORD（低字节在前）/ASCII（无 TMC 头）三格式 + 点数上限 + RAW 需 STOP
    §4 测量：无效值哨兵 9.9E37、双信源参数拼装、非法项/缺 src2 的拒绝
    §5 截屏与错误队列、快照结构

**DHO 回到实验台后的真机补验清单**（合并后 DHO 行为有变更，需实机确认）：
    ① `measure_clear()` → 设备接受 `:MEASure:CLEar`（DHO 命令）
    ② `acquire_type("ULTRa")` → 设备接受（MHO 用的是 HRESolution，别抄错）
    ③ `get_waveform(fmt="ASCii")` → **DHO 的 ASCII 是否带 TMC 头**（MHO 实测不带；
       本测试按"不带"处理，若 DHO 带则解析会报错，届时按实测调整 Family 字段）
    ④ `screenshot_png()` → `:DISPlay:DATA? PNG` 回图为 PNG 魔数
    ⑤ 双信源测量（`measure_item("RRPHase", 1, 2)`）→ 手册有记载，实机应有值
    ⑥ RAW 读取：`stop()` 后 `get_waveform(mode="RAW")` 分片读取点数正确
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rigol_scope import FAMILIES, RigolScope, family_of  # noqa: E402
from dho_control import DHO  # noqa: E402
from mho_control import MHO  # noqa: E402

fails: list[str] = []


def _raises(fn) -> bool:
    try:
        fn()
    except (ValueError, RuntimeError):
        return True
    return False


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:52s} {str(detail)[:110]}", flush=True)
    if not ok:
        fails.append(name)


class FakeTransport:
    """假 VISA 会话：按命令前缀回放脚本化响应，记录所有写入。"""

    def __init__(self, *, idn: str, acq_type: str = "NORM", fmt: str = "BYTE",
                 points: int = 1000, data: bytes | None = None,
                 measure: str = "1.2345E-01", status: str = "RUN",
                 ascii_has_tmc: bool = False, tcm_raw: bytes | None = None):
        self.idn = idn
        self.acq_type = acq_type
        self.fmt = fmt
        self.points = points
        self.data = data
        self.measure = measure
        self.status = status
        self.ascii_has_tmc = ascii_has_tmc
        self.tcm_raw = tcm_raw          # 不为 None 时按原字节回放（构造损坏/截断 TMC）
        self.writes: list[str] = []
        self.queries: list[str] = []

    # --- VisaClient 接口 ---
    def query(self, cmd: str) -> str:
        self.queries.append(cmd)
        u = cmd.strip().upper()
        if u == "*IDN?":
            return self.idn
        if ":SYSTem:VERSion?".upper() == u:
            return "3.0"
        if u.endswith(":ERROR?") or u.endswith(":ERR?"):
            return '0,"No error"'
        if ":ACQuire:TYPE?".upper() == u:
            return self.acq_type
        if ":ACQuire:SRATe?".upper() == u:
            return "2.000000E+9"
        if ":ACQuire:MDEPth?".upper() == u:
            return "1.0000E+06"
        if ":TRIGger:STATus?".upper() == u:
            return self.status
        if ":TRIGger:MODE?".upper() == u:
            return "EDGE"
        if ":TRIGger:SWEep?".upper() == u:
            return "AUTO"
        if ":TRIGger:EDGE:SOURce?".upper() == u:
            return "CHAN1"
        if ":TRIGger:EDGE:LEVel?".upper() == u:
            return "1.000000E-01"
        if ":TIMebase:MAIN:SCALe?".upper() == u:
            return "5.000000E-5"
        if ":TIMebase:MAIN:OFFSet?".upper() == u:
            return "0.000000E+0"
        if "MEASure:ITEM?" in cmd:
            return self.measure
        if ":WAVeform:PREamble?" in cmd:
            return "0,0,1000,1,5.000000E-07,0.000000E+00,0.000000E+00,3.051757812E-04,0.000000E+00,0.000000E+00"
        if ":CHANnel" in cmd and cmd.endswith("?"):
            if "DISPlay?" in cmd:
                return "1"
            if "SCALe?" in cmd:
                return "2.000000E+00"
            if "OFFSet?" in cmd:
                return "0.000000E+00"
            if "PROBe?" in cmd:
                return "1.000000E+01"
            if "COUPling?" in cmd:
                return "DC"
        return "0"

    def write(self, cmd: str) -> None:
        self.writes.append(cmd)

    def query_raw(self, cmd: str) -> bytes:
        self.queries.append(cmd)
        if ":DISPlay:DATA?" in cmd:
            png = b"\x89PNG\r\n\x1a\n" + b"x" * 128
            return b"#" + str(len(str(len(png)))).encode() + str(len(png)).encode() + png
        if ":WAVeform:DATA?" in cmd:
            if self.tcm_raw is not None:
                return self.tcm_raw
            if self.fmt.upper() == "ASCII":
                body = b"1.0E-01,2.0E-01,-1.0E-01"
                if self.ascii_has_tmc:
                    return b"#" + str(len(str(len(body)))).encode() + str(len(body)).encode() + body
                return body                                # 实测：ASCII 不带 TMC 头
            if self.data is not None:
                d = self.data
            elif self.fmt.upper() == "WORD":
                d = b"".join(struct.pack("<h", 0x8000 + i) for i in range(10))
            else:
                d = bytes(range(10))
            return b"#" + str(len(str(len(d)))).encode() + str(len(d)).encode() + d
        return b""

    def close(self) -> None:
        pass


def scope_with(family, **kw) -> RigolScope:
    """装配一个"已连接"的对象（注入假传输，不碰真设备）。"""
    cls = DHO if family.name == "DHO" else MHO
    s = cls(model=family.name)
    s.client = FakeTransport(idn=f"RIGOL TECHNOLOGIES,{family.name}000,UPPER,SERIAL", **kw)
    return s


# ---------------------------------------------------------------- §1 传输层
print("§1 传输层：命令拼写与读写路径", flush=True)
for fam in (FAMILIES["DHO"], FAMILIES["MHO"]):
    s = scope_with(fam)
    s2 = scope_with(fam)
    check(f"{fam.name}: idn()", "RIGOL" in s.idn(), s.idn()[:40])
    s.run(); s.stop(); s.single(); s.force_trigger(); s.clear(); s.autoset()
    check(f"{fam.name}: 控制流命令拼写",
          s.client.writes == [":RUN", ":STOP", ":SINGle", ":TFORce", ":CLEar", ":AUToset"],
          s.client.writes)
    check(f"{fam.name}: 版本/错误队列", s.version() == "3.0" and s.system_error() is None)
    check(f"{fam.name}: 通道档位写入", (s.channel_scale(1, 1.0), s.client.writes[-1])[1] == ":CHANnel1:SCALe 1.0")
    check(f"{fam.name}: 采样率/深度", s.sample_rate() == 2e9 and s.acquire_depth() == "1.0000E+06")
    _ = s2.measure_item("VPP", 1)
    check(f"{fam.name}: 单信源测量写入+查询",
          s2.client.writes[0] == ":MEASure:ITEM VPP,CHANnel1"
          and any(":MEASure:ITEM? VPP,CHANnel1" in q for q in s2.client.queries))

# ---------------------------------------------------------------- §2 家族差异
print("\n§2 家族差异（合并后最容易出错的地方）", flush=True)
d, m = scope_with(FAMILIES["DHO"]), scope_with(FAMILIES["MHO"])
d.measure_clear(); m.measure_clear()
check("DHO 清测量用 :MEASure:CLEar", d.client.writes[-1] == ":MEASure:CLEar", d.client.writes[-1])
check("MHO 清测量用 :MEASure:DELete", m.client.writes[-1] == ":MEASure:DELete", m.client.writes[-1])
check("DHO 采集第四态 = ULTRa（接受）", d.acquire_type("ULTRa") is None and d.client.writes[-1] == ":ACQuire:TYPE ULTRa")
check("DHO 拒绝 HRESolution（那是 MHO 的）", _raises(lambda: d.acquire_type("HRESolution")))
check("MHO 采集第四态 = HRESolution（接受）", m.acquire_type("HRESolution") is None and m.client.writes[-1] == ":ACQuire:TYPE HRESolution")
check("MHO 拒绝 ULTRa（那是 DHO 的）", _raises(lambda: m.acquire_type("ULTRa")))
check("DHO 无 :ACQuire:BITS（明确报错）", _raises(lambda: d.acquire_bits()))
check("MHO 有 :ACQuire:BITS", m.acquire_bits(16) is None and m.client.writes[-1] == ":ACQuire:BITS 16")
check("DHO 无 :CHANnel<n>:Impedance（明确报错）", _raises(lambda: d.channel_impedance(1)))
check("MHO 有 :CHANnel<n>:Impedance", m.channel_impedance(1, "FIFTy") is None
      and m.client.writes[-1] == ":CHANnel1:IMPedance FIFTY")
check("边沿第三态两家族一致 = RFALl",
      FAMILIES["DHO"].edge_slopes == FAMILIES["MHO"].edge_slopes == ("POSitive", "NEGative", "RFALl"))
check("family_of 分派", family_of("MHO984D").name == "MHO" and family_of("DHO924S").name == "DHO"
      and family_of(None).name == "DHO")
check("家族差异表：清测量命令互斥",
      FAMILIES["DHO"].measure_clear != FAMILIES["MHO"].measure_clear)

# ---------------------------------------------------------------- §3 波形解析
print("\n§3 波形解析（三格式 + 校验）", flush=True)
for fam in (FAMILIES["DHO"], FAMILIES["MHO"]):
    s = scope_with(fam, fmt="BYTE", data=bytes([0, 1, 128, 255]))
    wf = s.get_waveform(1, fmt="BYTE", points=4)
    check(f"{fam.name}: BYTE 解析（含 TMC 剥离）", wf["points"] == 4, f"{wf['points']} 点 v={[round(x,4) for x in wf['v']]}")
    s = scope_with(fam, fmt="WORD", data=b"".join(struct.pack("<H", v) for v in (0x8000, 0x8001)))
    wf = s.get_waveform(1, fmt="WORD", points=2)
    check(f"{fam.name}: WORD 低字节在前", wf["points"] == 2 and wf["v"][1] > wf["v"][0],
          f"v={[round(x,5) for x in wf['v']]}")
    s = scope_with(fam, fmt="ASCii", ascii_has_tmc=False)
    wf = s.get_waveform(1, fmt="ASCii", points=3)
    check(f"{fam.name}: ASCII 无 TMC 头也解析", wf["points"] == 3, f"v={wf['v']}")
    s = scope_with(fam, fmt="ASCii", ascii_has_tmc=True)
    wf = s.get_waveform(1, fmt="ASCii", points=3)
    check(f"{fam.name}: ASCII 带 TMC 头也兼容", wf["points"] == 3)
    s = scope_with(fam)
    check(f"{fam.name}: NORMal 超 1000 点被拒", _raises(lambda: s.get_waveform(1, points=5000)))
    check(f"{fam.name}: 非法模式被拒", _raises(lambda: s.get_waveform(1, mode="BOGUS")))
    s = scope_with(fam, status="RUN")
    check(f"{fam.name}: RAW 非 STOP 被拒（护栏）", _raises(lambda: s.get_waveform(1, mode="RAW")))
    s = scope_with(fam, status="STOP")
    check(f"{fam.name}: STOP 后 RAW 可用", s.get_waveform(1, mode="RAW", points=4)["points"] == 4)
    s = scope_with(fam, tcm_raw=b"\x01\x02\x03")            # 根本没有 '#' 头
    check(f"{fam.name}: 缺 TMC 头报错", _raises(lambda: s.get_waveform(1, fmt="BYTE", points=4)))
    s = scope_with(fam, tcm_raw=b"#9000000010" + b"\x01")   # 头声明 10 字节、实给 1 字节
    check(f"{fam.name}: TMC 截断报错", _raises(lambda: s.get_waveform(1, fmt="BYTE", points=4)))

# ---------------------------------------------------------------- §4 测量
print("\n§4 测量：哨兵值与双信源", flush=True)
for fam in (FAMILIES["DHO"], FAMILIES["MHO"]):
    s = scope_with(fam, measure="9.9000E+37")
    check(f"{fam.name}: 无效读数 9.9E37 → ValueError", _raises(lambda: s.measure_item("VPP", 1)))
    s = scope_with(fam)
    _ = s.measure_item("RRPHase", 1, 2)
    check(f"{fam.name}: 双信源参数拼装",
          s.client.writes[0] == ":MEASure:ITEM RRPHase,CHANnel1,CHANnel2", s.client.writes[0])
    check(f"{fam.name}: 双信源缺 src2 被拒", _raises(lambda: s.measure_item("RRPHase", 1)))
    check(f"{fam.name}: 未知测量项被拒", _raises(lambda: s.measure_item("NOPE", 1)))
    check(f"{fam.name}: 双信源项两家族都有（手册均记载）",
          "RRPHase" in fam.measure_items_dual)

# ---------------------------------------------------------------- §5 截屏/快照
print("\n§5 截屏、错误队列与快照", flush=True)
for fam in (FAMILIES["DHO"], FAMILIES["MHO"]):
    s = scope_with(fam)
    data = s.screenshot("PNG")
    check(f"{fam.name}: 截屏剥 TMC 且是 PNG", data[:8] == b"\x89PNG\r\n\x1a\n", f"{len(data)} 字节")
    check(f"{fam.name}: 非法截图格式被拒", _raises(lambda: s.screenshot("TIFF")))
    snap = s.snapshot()
    check(f"{fam.name}: 快照结构", snap["family"] == fam.name and set(snap["channels"]) == {"ch1", "ch2", "ch3", "ch4"},
          f"trigger={snap['trigger_status']} timebase={snap['timebase_scale_s_div']}")
    s = scope_with(fam)
    _ = s.drain_errors()
    check(f"{fam.name}: drain_errors 队列干净返回空", s.drain_errors() == [])

print(f"\n== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL: ' + ', '.join(fails[:8])} ==")
sys.exit(1 if fails else 0)


def _raises(fn) -> bool:
    try:
        fn()
    except (ValueError, RuntimeError):
        return True
    return False
