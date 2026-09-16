"""共享内核的**设置语义 / 读数诊断 / 自动定标**离线回归（无需任何仪器）。

来源：2026-09-15 用 MHO984D 调试时的现场教训（E_distance 项目，TRIG_OUT/VOUT/温度 DAC）。
证据与实测原文：`docs/tool_optimization_20260915.md`、`docs/示波器自动定标设计-2026-09-15.md`；
现场使用要点：`D:\\WorkDesigns\\2_WorkProjects\\E_distance\\5_docs\\示波器使用要点（MHO984D）.md`。

做法：把那些**设备行为**写成设备模型 `FakeTrapScope`，于是每条教训都变成可重跑的断言——
不依赖真机，也不会碰在用设备（本机 MHO 常被现场实验占用）。

    python TEST_SCRIPTS/common/verify_rigol_scope_semantics.py

覆盖：
    §1 设置语义三条陷阱：OFF 静默忽略 / 改 scale 等比缩放 offset / 偏置量程钳制
    §2 窗口公式：中心 = −offset、竖窗与时间窗；**未标定家族不猜**（返回 None）
    §3 读数诊断：channel_off / off_screen / near_edge / few_edges 分开报因
    §4 主机侧统计：samples=N 的 mean/min/max/stddev 与无效计数
    §5 单通道自动定标：离屏放大定标 / 平直不猜档 / 通道关报错 / 超量程如实报
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rigol_scope import FAMILIES, RigolScope, snap_1_2_5, snap_up  # noqa: E402
from dho_control import DHO  # noqa: E402
from mho_control import MHO  # noqa: E402

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:58s} {str(detail)[:100]}", flush=True)
    if not ok:
        fails.append(name)


class FakeTrapScope:
    """MHO984D 的三条现场实测行为 + "信号 ↔ 窗口"的物理关系（全部来自实测证据）。

    ① 通道 OFF 时写 SCALe/OFFSet **静默忽略**（不报错、值不变）
       —— 实测：`:CHANnel4:DISPlay OFF; :CHANnel4:SCALe 0.05` → 回读仍是 1.5
    ② 写 SCALe 会**等比缩放 offset**（设备主动改写，保持波形屏幕位置）
       —— 实测：offset −3.5 上写 SCALe 0.85（scale 原 2.0）→ 回读 −1.49 ≈ −3.5×0.85/2
    ③ offset 超量程被**钳制**（本机 ±20 V，与档位无关）—— 实测：写 −50 → 回读 −20
    另：测量可测性由"迹线是否落在竖窗内"决定；**部分出窗时极值被钳到窗沿**，
    这正是文档里"看着合理的假值（0.9216 V vs 真实 ±10 V）"的来源。
    """

    VDIVS = 8.0          # 与 Family.vdivs 一致（本机实测标定）
    HDIVS = 10.0
    OFFSET_LIMIT = 20.0  # 实测 ±20 V

    def __init__(self, signal: dict[int, tuple[float, float]],
                 scale: float = 2.0, offset: float = 0.0,
                 period_s: float = 2e-4, tdiv: float = 5e-5,
                 chan_off: tuple[int, ...] = ()):
        self.sig = signal                      # ch -> (vmin, vmax) 真实值
        self.scale = {c: scale for c in signal}
        self.offset = {c: offset for c in signal}
        self.disp = {c: (c not in chan_off) for c in signal}
        self.probe = {c: 1.0 for c in signal}
        self.coupling = {c: "DC" for c in signal}
        self.period_s = period_s
        self.tdiv = tdiv
        self.tdoff = 0.0
        self.trig_mode, self.sweep = "EDGE", "AUTO"
        self.edge_src, self.edge_slope, self.edge_level = "CHAN1", "POSitive", 0.1
        self.writes: list[str] = []

    # ---- 传输接口 ----
    def query(self, cmd: str) -> str:
        u = cmd.strip()
        U = u.upper()
        if U == "*IDN?":
            return "RIGOL TECHNOLOGIES,MHO984D,SERIAL,00.01.00"
        if U.endswith(":ERROR?") or U.endswith(":ERR?"):
            return '0,"No error"'
        m = re.fullmatch(r":CHANnel(\d):DISPlay\?", u, re.I)
        if m:
            return "1" if self.disp[int(m.group(1))] else "0"
        m = re.fullmatch(r":CHANnel(\d):SCALe\?", u, re.I)
        if m:
            return f"{self.scale[int(m.group(1))]:E}"
        m = re.fullmatch(r":CHANnel(\d):OFFSet\?", u, re.I)
        if m:
            return f"{self.offset[int(m.group(1))]:E}"
        m = re.fullmatch(r":CHANnel(\d):PROBe\?", u, re.I)
        if m:
            return f"{self.probe[int(m.group(1))]:E}"
        m = re.fullmatch(r":CHANnel(\d):COUPling\?", u, re.I)
        if m:
            return self.coupling[int(m.group(1))]
        if U == ":TIMEBASE:MAIN:SCALE?":
            return f"{self.tdiv:E}"
        if U == ":TIMEBASE:MAIN:OFFSET?":
            return f"{self.tdoff:E}"
        if U == ":TRIGGER:MODE?":
            return self.trig_mode
        if U == ":TRIGGER:SWEEP?":
            return self.sweep
        if U == ":TRIGGER:EDGE:SOURCE?":
            return self.edge_src
        if U == ":TRIGGER:EDGE:SLOPE?":
            return self.edge_slope
        if U == ":TRIGGER:EDGE:LEVEL?":
            return f"{self.edge_level:E}"
        m = re.fullmatch(r":MEASure:ITEM\?\s+(\w+),\s*CHANnel(\d)", u, re.I)
        if m:
            return self._measure(m.group(1), int(m.group(2)))
        return "0"

    def write(self, cmd: str) -> None:
        u = cmd.strip()
        self.writes.append(u)
        m = re.fullmatch(r":CHANnel(\d):DISPlay\s+(ON|OFF)", u, re.I)
        if m:
            self.disp[int(m.group(1))] = m.group(2).upper() == "ON"
            return
        m = re.fullmatch(r":CHANnel(\d):SCALe\s+([\d.eE+-]+)", u, re.I)
        if m:                                   # ① OFF 静默忽略；② 等比缩放 offset
            c, v = int(m.group(1)), float(m.group(2))
            if not self.disp[c]:
                return
            self.offset[c] = self.offset[c] * v / self.scale[c]
            self.scale[c] = v
            return
        m = re.fullmatch(r":CHANnel(\d):OFFSet\s+([\d.eE+-]+)", u, re.I)
        if m:                                   # ① OFF 静默忽略；③ 超量程钳制
            c, v = int(m.group(1)), float(m.group(2))
            if not self.disp[c]:
                return
            self.offset[c] = math.copysign(min(abs(v), self.OFFSET_LIMIT), v)
            return
        m = re.fullmatch(r":CHANnel(\d):PROBe\s+([\d.eE+-]+)", u, re.I)
        if m:
            self.probe[int(m.group(1))] = float(m.group(2))
            return
        m = re.fullmatch(r":CHANnel(\d):COUPling\s+(\w+)", u, re.I)
        if m:
            self.coupling[int(m.group(1))] = m.group(2).upper()
            return
        m = re.fullmatch(r":TIMebase:MAIN:SCALe\s+([\d.eE+-]+)", u, re.I)
        if m:
            self.tdiv = float(m.group(1))
            return
        m = re.fullmatch(r":TIMebase:MAIN:OFFSet\s+([\d.eE+-]+)", u, re.I)
        if m:
            self.tdoff = float(m.group(1))
            return
        m = re.fullmatch(r":TRIGger:MODE\s+(\w+)", u, re.I)
        if m:
            self.trig_mode = m.group(1).upper()
            return
        m = re.fullmatch(r":TRIGger:SWEep\s+(\w+)", u, re.I)
        if m:
            self.sweep = m.group(1).upper()
            return
        m = re.fullmatch(r":TRIGger:EDGE:SOURce\s+CHANnel(\d)", u, re.I)
        if m:
            self.edge_src = f"CHAN{int(m.group(1))}"
            return
        m = re.fullmatch(r":TRIGger:EDGE:SLOPe\s+(\w+)", u, re.I)
        if m:
            self.edge_slope = m.group(1)
            return
        m = re.fullmatch(r":TRIGger:EDGE:LEVel\s+([\d.eE+-]+)", u, re.I)
        if m:
            self.edge_level = float(m.group(1))
            return
        # 打开测量项（:MEASure:ITEM VPP,CHANnel1）——设备不返回内容

    def close(self) -> None:
        pass

    # ---- 信号模型 ----
    def _measure(self, item: str, ch: int) -> str:
        vmin, vmax = self.sig[ch]
        if not self.disp[ch]:
            return "9.9000E+37"
        center = -self.offset[ch]
        half = self.VDIVS / 2 * self.scale[ch]
        top, bot = center + half, center - half
        if not (bot <= vmin <= top or bot <= vmax <= top):
            return "9.9000E+37"                  # 完全在窗外：无有效值
        cmin, cmax = max(vmin, bot), min(vmax, top)   # 部分出窗 → 钳到窗沿（假值来源）
        key = item.upper()
        if key == "VMAX":
            return f"{cmax:E}"
        if key == "VMIN":
            return f"{cmin:E}"
        if key == "VPP":
            return f"{cmax - cmin:E}"
        if key == "VAVG":
            return f"{(cmin + cmax) / 2:E}"
        if key == "FREQUENCY":
            span = self.HDIVS * self.tdiv
            if span < 2 * self.period_s:
                return "9.9000E+37"              # 屏内不足 2 个周期 → 读不到
            return f"{1.0 / self.period_s:E}"
        return f"{cmax:E}"


def scope_with(signal: dict[int, tuple[float, float]], **kw) -> MHO:
    """装配一个"已连接"的 MHO（注入陷阱模型，不碰真设备）。"""
    s = MHO(model="MHO")
    s.client = FakeTrapScope(signal, **kw)
    return s


# 现场那台的真实数字：CH3 上 7.4816 V 的准直流信号（vmin/vmax 取实测两条）
DC_748 = {3: (7.4748, 7.4825)}

print("§1 设置语义：三条实测陷阱（OFF 静默忽略 / 等比缩放 offset / 量程钳制）", flush=True)

# ① 只写 scale → offset 被设备等比缩放，工具必须如实报出来
s = scope_with(DC_748, scale=2.0, offset=-3.5)
r = s.configure_channel(3, scale=1.0)
check("① 只写 scale：offset 被等比缩放且如实报告",
      abs(r["actual"]["offset_v"] - (-1.75)) < 1e-6
      and any("等比缩放" in x for x in r["reasons"]),
      f"offset -3.5 → {r['actual']['offset_v']:g}；reasons={len(r['reasons'])} 条")

# ② 写 scale + offset → 下发顺序必须是 scale 先、offset 后
s = scope_with(DC_748, scale=2.0, offset=-3.5)
r = s.configure_channel(3, scale=0.5, offset=-7.48)
order = [w for w in s.client.writes if "SCALe" in w or "OFFSet" in w]
check("② 顺序固定 scale → offset",
      order[:2] == [":CHANnel3:SCALe 0.5", ":CHANnel3:OFFSet -7.48"], order[:2])
check("② 写完后 offset 精确到位（不再被缩放）",
      abs(r["actual"]["offset_v"] - (-7.48)) < 1e-9, f"回读 {r['actual']['offset_v']:g}")

# ③ 偏置超量程 → 钳制 + adjusted/reasons，不混成成功
s = scope_with(DC_748, scale=2.0, offset=0.0)
r = s.configure_channel(3, offset=-50.0)
check("③ 偏置被钳制：adjusted 非空 + 原因含'钳制'",
      r["adjusted"] is not None and any("钳制" in x for x in r["reasons"])
      and abs(r["actual"]["offset_v"] + 20.0) < 1e-9,
      f"要求 -50 → 回读 {r['actual']['offset_v']:g} V")

# ④ 通道 OFF 时写垂直参数 → 自动先开通道（否则写入被静默忽略）
s = scope_with(DC_748, scale=2.0, offset=0.0, chan_off=(3,))
r = s.configure_channel(3, scale=1.0)
check("④ 通道 OFF：自动先开通道且写入生效",
      s.client.disp[3] and abs(r["actual"]["scale_v_div"] - 1.0) < 1e-9
      and any("OFF" in x for x in r["reasons"]),
      f"writes={s.client.writes[:2]}")

# ⑤ display=False 与参数同时给 → 参数先写、显示后关（关早了写入会被忽略）
s = scope_with(DC_748, scale=2.0, offset=0.0)
r = s.configure_channel(3, scale=1.0, offset=-2.0, display=False)
check("⑤ display=False：参数写完后才关通道",
      s.client.writes[-1] == ":CHANnel3:DISPlay OFF"
      and abs(r["actual"]["scale_v_div"] - 1.0) < 1e-9 and r["actual"]["display"] is False,
      f"序列={[w.split()[0] for w in s.client.writes]}")

# ⑥ 耦合/探头回读
s = scope_with(DC_748)
r = s.configure_channel(3, coupling="AC", probe=10.0)
check("⑥ 耦合/探头写后回读", r["actual"]["coupling"].startswith("AC")
      and abs(r["actual"]["probe_x"] - 10.0) < 1e-9, f"{r['actual']['coupling']}, {r['actual']['probe_x']}")

# ⑦ 全 None → 纯回读、零写入
s = scope_with(DC_748)
r = s.configure_channel(3)
check("⑦ 全 None：只回读、不写设备", s.client.writes == [] and r["requested"] == {},
      f"writes={s.client.writes}")

# ⑧ 时基：两者都回读
s = scope_with(DC_748)
r = s.configure_timebase(scale=1e-4)
check("⑧ 时基 setting：scale 写 + 两者回读 + 时间窗给出",
      abs(r["actual"]["scale_s_div"] - 1e-4) < 1e-12 and abs(r["actual"]["offset_s"]) < 1e-12
      and r["window_t"]["span_s"] == 1e-3, f"window_t={r['window_t']}")

# ⑨ 触发：枚举校验 + 回读 + 短格式比较
s = scope_with(DC_748)
r = s.configure_trigger(source=3, level=2.5, slope="POSitive", mode="EDGE", sweep="AUTO")
bad = None
try:
    s.configure_trigger(mode="NOT_A_MODE")
except ValueError as e:
    bad = str(e)[:40]
check("⑨ 触发：合法写入回读一致 + 非法枚举被拒",
      r["actual"]["edge_source"].startswith("CHAN3") and abs(r["actual"]["edge_level_v"] - 2.5) < 1e-9
      and bad is not None, f"mode 拒绝={bad}")

print("\n§2 窗口公式：中心 = −offset；未标定家族不猜", flush=True)
s = scope_with(DC_748, scale=2.0, offset=-3.5)
w = s.vertical_window(3)
check("MHO 竖窗 = [−offset−4s, −offset+4s]（8 格）",
      abs(w["center_v"] - 3.5) < 1e-9 and abs(w["bottom_v"] - (-4.5)) < 1e-9
      and abs(w["top_v"] - 11.5) < 1e-9, f"window=[{w['bottom_v']:g}, {w['top_v']:g}]")
# 文档里的标定用例（tool_optimization §P1-3(d)）：scale 0.9 上沿 7.1 V（信号 7.48 V 读不到）、
# scale 1.0 上沿 7.5 V（读到 7.4825 V）——两条都对上，故"8 格 + 中心=−offset"定量成立
w09 = scope_with(DC_748, scale=0.9, offset=-3.5).vertical_window(3)
w10 = scope_with(DC_748, scale=1.0, offset=-3.5).vertical_window(3)
check("标定证据复现：上沿 7.1 V（读不到）/ 7.5 V（读到）",
      abs(w09["top_v"] - 7.1) < 1e-9 and abs(w10["top_v"] - 7.5) < 1e-9,
      f"scale0.9→{w09['top_v']:g} V, scale1.0→{w10['top_v']:g} V")
s2 = scope_with(DC_748)
s2.client = FakeTrapScope(DC_748)
d = DHO(model="DHO")
d.client = s2.client
check("DHO 未标定格数 → vertical_window() 返回 None（宁可没有，不给错的）",
      d.vertical_window(3) is None and FAMILIES["DHO"].vdivs is None)

print("\n§3 读数诊断：四类原因分开（不再混成一句话）", flush=True)
s = scope_with(DC_748, scale=2.0, offset=0.0, chan_off=(3,))
check("通道 OFF → channel_off",
      s.diagnose_no_reading("VAVG", 3)["suspicious"] == "channel_off")

# 离屏：scale 0.9 / offset −3.5 时窗口 [−7.1−...]. 现场：上沿 7.1 V < 信号 7.48 V → 无值
s = scope_with(DC_748, scale=0.9, offset=-3.5)
d = s.diagnose_no_reading("VAVG", 3)
check("迹线整体在窗外 → off_screen + 给出窗口与建议",
      d["suspicious"] == "off_screen" and "窗口" in d["hint"] and d["window"]["top_v"] < 7.48,
      f"窗口上沿 {d['window']['top_v']:.3g} V < 信号 7.48 V")

# 贴边：窗口刚好包住信号但极值落在 8% 带内 → near_edge（"看着合理的假值"）
s = scope_with({3: (7.2, 7.35)}, scale=0.9, offset=-3.5)   # 窗口 [−7.1, 7.1]... 需调
s = scope_with({3: (6.9, 7.05)}, scale=0.9, offset=-3.5)   # 窗口上沿 7.1 → 极值 7.05 在带内
d = s.diagnose_no_reading("VAVG", 3)
check("极值贴窗口边沿 → near_edge（明确提示可能是假值）",
      d["suspicious"] == "near_edge" and "假值" in d["hint"], f"hint={d['hint'][:60]}...")

# 边沿不足：20 µs/div 看 5 kHz（周期 200 µs，窗口仅 10×20µs=200µs → 恰好 1 个周期）
s = scope_with({3: (0.0, 3.3)}, tdiv=2e-5, period_s=2e-4)
d = s.diagnose_no_reading("FREQuency", 3)
check("时基窗口容不下 2 个周期 → few_edges + 时基建议",
      d["suspicious"] == "few_edges" and "时基" in d["hint"],
      f"时间窗 {d['window_t']['span_s']:g} s（周期 2e-4 s）")
# 放宽到 100 µs/div → 立刻能测（现场 4.9993 kHz）
s = scope_with({3: (0.0, 3.3)}, tdiv=1e-4, period_s=2e-4)
check("放宽时基后频率可测（现场：100 µs/div 立刻读到 4.9993 kHz）",
      abs(s.measure_item("FREQuency", 3) - 5000.0) < 0.1)

print("\n§4 主机侧统计（samples=N）", flush=True)


class Jitter(FakeTrapScope):
    """连读带抖动：第 3 次返回无效值（模拟现场"偶发无有效值"）。"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.calls = 0

    def _measure(self, item: str, ch: int) -> str:
        self.calls += 1
        if self.calls == 3:
            return "9.9000E+37"
        return f"{7.48 + (self.calls - 1) * 1e-4:E}"


s = MHO(model="MHO")
s.client = Jitter(DC_748)
st = s.measure_stats("VAVG", 3, samples=5)
# 抖动序列：第 1/2/4/5 次分别 7.4800/7.4801/7.4803/7.4804，第 3 次无效
check("mean/min/max/stddev 正确 + 无效读数单独计数",
      st["count"] == 4 and st["invalid"] == 1 and abs(st["min"] - 7.4800) < 1e-9
      and abs(st["max"] - 7.4804) < 1e-9 and abs(st["mean"] - 7.4802) < 1e-9
      and st["stddev"] > 0,
      f"{st['count']} 有效 / {st['invalid']} 无效，mean={st['mean']:.5f} "
      f"±{st['stddev']:.2e}，max={st['max']:.4f}")

s = MHO(model="MHO")
s.client = FakeTrapScope({3: (7.4748, 7.4825)}, scale=0.5, offset=-3.5)  # 离屏 → 全无效
try:
    s.measure_stats("VAVG", 3, samples=3)
    check("全无效时抛错", False)
except ValueError as e:
    check("全无效时抛错（带最后一次原因）", "无有效值" in str(e), str(e)[:60])

print("\n§5 单通道自动定标 fit_channel", flush=True)
# 场景 2（设计文档 §6-2）：档位被设成 0.5 V/div → 信号离屏 → 逐档放大到可测再定标
s = scope_with(DC_748, scale=0.5, offset=0.0)
r = s.fit_channel(3)
check("离屏信号：逐档放大到可测并定标，ok=True",
      r["ok"] is True and r["after"]["scale_v_div"] >= 1.0,
      f"0.5 → {r['after']['scale_v_div']:g} V/div（{len(r['trace'])} 次迭代）")
check("定标后不贴边（margin_ok）", r["margin_ok"] is True, f"occupancy={r['occupancy']}")

# 场景 1：平直信号 → 判 flat、保持档位、按均值居中（不猜档位）
s = scope_with({3: (7.48, 7.4801)}, scale=2.0, offset=-3.5)
r = s.fit_channel(3)
check("平直信号：判 flat 且**保持档位**（不猜）",
      r["flat"] is True and abs(r["after"]["scale_v_div"] - 2.0) < 1e-9
      and "平直" in r.get("note", ""), f"scale={r['after']['scale_v_div']:g}（保持 2.0）")

# 场景 5：无信号（全 0，幅度远小于 LSB） → 平直
s = scope_with({3: (0.0, 0.0)}, scale=2.0, offset=0.0)
r = s.fit_channel(3)
check("无信号：仍判 flat、不编造档位", r["flat"] is True, f"scale={r['after']['scale_v_div']:g}")

# 场景 6：通道 OFF → 明确报错（不静默无功而返）
s = scope_with(DC_748, chan_off=(3,))
try:
    s.fit_channel(3)
    check("通道 OFF 时明确报错", False)
except RuntimeError as e:
    check("通道 OFF 时明确报错（提示先开通道）", "OFF" in str(e), str(e)[:60])

# 场景：信号超出最大档（10 V/div × 8 格 = 80 V 窗） → 如实报"超出可测范围"
s = scope_with({3: (-200.0, 200.0)}, scale=0.5, offset=0.0)
r = s.fit_channel(3)
check("超出量程：ok=False + reason='超出可测范围'（不假装成功）",
      r["ok"] is False and r["reason"] == "超出可测范围",
      f"逐档到 {r['trace'][-1]['scale_v_div']:g} V/div 仍不可测")

# 场景 7：偏置需超量程才能居中 → reasons 里出现"钳制"（设计文档 §6-7）
s = scope_with({3: (30.0, 30.01)}, scale=10.0, offset=0.0)   # 中心 30 V > 20 V 量程
r = s.fit_channel(3)
check("偏置超量程无法居中：如实报'钳制'，不静默失败",
      any("钳制" in x for x in r.get("reasons", [])), f"reasons={r.get('reasons')}")

print("\n§6 档位序列工具函数（1-2-5）", flush=True)
check("snap_1_2_5: 1.8→2 / 0.43→0.5 / 7.1→10",
      snap_1_2_5(1.8) == 2 and snap_1_2_5(0.43) == 0.5 and abs(snap_1_2_5(7.1) - 10) < 1e-9)
check("snap_up: 0.9→1.0（不是 2.0）/ 2→5 / 5→10 / 10→None(最大档)",
      snap_up(0.9) == 1.0 and snap_up(2.0) == 5.0 and abs(snap_up(5.0) - 10.0) < 1e-9
      and snap_up(10.0, max_scale=10.0) is None,
      f"0.9→{snap_up(0.9)}, 5→{snap_up(5.0)}")

print(f"\n== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL'} ==")
for f in fails:
    print(f"  - {f}")
sys.exit(1 if fails else 0)
