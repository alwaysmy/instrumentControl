"""审计器闭环自测（**纯离线**，不需要任何仪器）：提取、归一化、匹配三层 + 全仓基线。

用法：
    python TEST_SCRIPTS/common/verify_audit_extractor.py

为什么需要它：`audit_all_commands.py` 是"命令零猜测"的守门人，但它自己此前既漏检
（只认以 `:`/`*` 开头的字面量 → `C{n}:VDIV?`、`TDIV?`、`{ch}:OUTP?` 全在盲区）又误报
（逐段截前 4 字符 + 单段根命令不入索引 → 稳定误报 30 条）。重构后必须有回归，
否则下次改坏没人知道——本脚本就是那份回归，且**完全离线**，无仪器也能跑。

三层覆盖：
    §1 提取层：只取字符串字面量、排除 docstring、f-string 还原、通道前缀、英文词停用表；
    §2 归一化层：段键（SCPI 短形式）+ 通道选择器剥离 + 段内长短形式兼容；
    §3 全仓基线：跑真实六套库 + 脚本，MISS 集合必须**恰好**等于冻结基线
       （多一条 = 有人加了无出处的命令；少一条 = 手册/索引变了，都该有人看一眼）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "TEST_SCRIPTS" / "common"))

import audit_all_commands as A  # noqa: E402

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:52s} {detail[:110]}", flush=True)
    if not ok:
        fails.append(name)


def cands(src: str) -> set[str]:
    """从一小段源码里取出候选命令串集合（用 extract_cmds，去行号）。"""
    return {c for c, _ln, _i in A.extract_cmds(src)}


# ---------------------------------------------------------------- §1 提取层
print("§1 提取层（AST：只取字面量、跳过 docstring、f-string 还原）", flush=True)

SAMPLE = '''
"""模块 docstring：这里写 :WAVeform:FAKE? 不该被当成命令。"""
CMD = ":MEASure:MODE SIMPle"          # 带前导冒号
CHAN = "C{n}:VDIV?"                   # 通道前缀 + 占位符
FMT = 'PRIN? BMP'                     # 单段查询
TDIV = "TDIV?"                        # 单段查询（无冒号）
IDN = "*IDN?"
MSG = "OK?"                           # 英文词停用表：不该抽
NOTE = "注意事项：通道 1 为参考"        # 中文含全角冒号：不该抽
TPL = f":MEASure:ADVanced:P{n}:TYPE {t}"   # f-string 被插值切断，需还原
OUT = f"{ch}:OUTP?"                   # 选择器为 f-string 占位
ESCAPED = "line1\\n:SYSTem:ERRor?"    # 转义序列不该破坏提取


def f():
    """函数 docstring：:SYSTem:FAKE2? 不该被当成命令。"""
    return ":CHANnel1:DISPlay ON"
'''
got = cands(SAMPLE)


def has(*wanted: str) -> bool:
    return all(any(w in g for g in got) for w in wanted)


check("抽出带前导冒号的命令", ":MEASure:MODE SIMPle" in got or any("MEASure:MODE" in g for g in got))
check("抽出通道前缀命令 C{n}:VDIV?", any(g.startswith("C{n}:VDIV") for g in got))
check("抽出单段查询 PRIN? / TDIV?", "PRIN?" in got and "TDIV?" in got,
      f"含 PRIN?={'PRIN?' in got} TDIV?={'TDIV?' in got}")
check("抽出 *IDN?", "*IDN?" in got)
check("抽出函数体内命令 :CHANnel1:DISPlay", any("CHANnel1:DISPlay" in g for g in got))
check("抽出转义串里的命令", any("SYSTem:ERRor" in g for g in got))
check("f-string 还原为整条命令", any("P{n}:TYPE" in g for g in got), f"got={sorted(got)[:6]}")
check("跳过模块 docstring", not any("FAKE?" in g for g in got))
check("跳过函数 docstring", not any("FAKE2?" in g for g in got))
check("英文词 OK? 不入候选", "OK?" not in got)
check("中文全角冒号不入候选", not any("注意事项" in g for g in got))

PH = '''
A = "{ch}:OUTP?"                 # 首段是占位符选择器 → 剥掉后对上 :OUTPut
B = f"{base}:{v}?"               # f-string 拼命令名 → 动态，不可静态核
C = f"CONF:{key}"                # 同上
D = ":STATus:QUES:INST:ISUM{n}:{node}?"   # 模板常量：完整命令，照常核对
E = "{n}:{v}?"                   # 全是占位符 → 归一为空，整条丢弃
'''
ph = A.extract_cmds(PH)
names = {(c, i) for c, _l, i in ph}
check("占位选择器命令可抽出", any(c == "{ch}:OUTP?" for c, _i in names))
check("f-string 命令标记为动态",
      all(i for c, i in names if c.startswith("{base}") or c.startswith("CONF:")),
      f"标记={sorted({(c, i) for c, i in names if c.startswith('CONF:')})}")
check("模板常量不标记动态",
      all(not i for c, i in names if c.startswith(':STATus') or c.startswith('STATus')))
check("动态判定 is_dynamic({base}:{v}?)", A.is_dynamic("{base}:{v}?"))
check("动态判定 CONF:{key}", A.is_dynamic("CONF:{key}"))
check("纯占位命令归一为空（丢弃）", A.norm_head("{n}:{v}?") == (),
      f"-> {A.norm_head('{n}:{v}?')}")
check("带索引后缀的段保留主干", A.norm_head(":STATus:QUES:INST:ISUM{n}:{node}?")
      == ("STAT", "QUES", "INST", "ISUM"), f"-> {A.norm_head(':STATus:QUES:INST:ISUM{n}:{node}?')}")

# ---------------------------------------------------------------- §2 归一化层
print("\n§2 归一化层（段键 = SCPI 短形式；剥通道选择器）", flush=True)
cases_norm = [
    (":MEASure:MODE SIMPle", ("MEAS", "MODE")),
    ("C{n}:VDIV?", ("VDIV",)),
    ("{ch}:OUTP?", ("OUTP",)),
    ("*IDN?", ("*IDN",)),
    ("CHANnel<n>:SCALe", ("SCAL",)),          # 选择器前缀剥掉
    (":WAVeform:DATA?", ("WAV", "DATA")),
    (":ACQuire:MDEPth 1M", ("ACQ", "MDEP")),
    ("P<n>:SHIStory?", ("SHIS",)),            # SDS P 槽选择器
]
for cmd, want in cases_norm:
    check(f"归一 {cmd!r}", A.norm_head(cmd) == want, f"-> {A.norm_head(cmd)}（期望 {want}）")

print("\n§2b 段内长短形式兼容（_seg_match）", flush=True)
for a, b, want in [("COUPLING", "COUP", True), ("MEAS", "MEASure", True),
                   ("RES", "RESI", True), ("VDIV", "SCAL", False),
                   ("DC", "DATA", False), ("AB", "ABC", False)]:
    check(f"_seg_match({a!r},{b!r}) == {want}", A._seg_match(a, b) is want)

# ---------------------------------------------------------------- §3 全仓基线
print("\n§3 全仓基线（六套库 + 脚本；MISS 集合需与冻结基线完全一致）", flush=True)

# 冻结基线：每条都已人工核对手册，说明见注释。新增 MISS = 有新命令缺手册出处，必须复核。
MISS_BASELINE: dict[str, list[str]] = {
    # 我方参照物是本仓的《DH1766 指令速查》(SCPI_COMMANDS_DH1766A.md)；STAT 组不在其中，
    # 出处是用户手册 4.2.2（提取版在 §4.2.9 后被截断）。库内 40/40 已真机验证过。
    "dh1766": ["STAT:OPER", "STAT:OPER:COND", "STAT:OPER:ENAB", "STAT:PRES",
               "STAT:QUES", "STAT:QUES:COND", "STAT:QUES:ENAB", "STAT:QUES:INST:ISUM"],
    "dg832": [],          # 32 HIT / 0 MISS：驱动命令全部可回溯到 docs/02_编程手册.txt
    "dho": [],
    "mho": [],
    # 前 5 条 = 实测可用但手册查无出处的旧短形式（C{n}:VDIV/OFST/ATTN、TDIV?、TRDL?，
    # 见 docs/review_20260915.md E6/E7）；SYST:ERR? 是 SCPI-99 标准命令，提取版缺该节。
    "sds": ["ATTN", "OFST", "SYST:ERR", "TDIV", "TRDL", "VDIV"],
    # SYST:ERR?/SYST:VERS? 同上（SDG 提取版无 SYSTem 节）；FCNT? 已真机验证，提取版表中无。
    "sdg": ["FCNT", "SYST:ERR", "SYST:VERS"],
    # READ? 是真实命令（手册正文有 READ?，提取版未给出带冒号链形式）。
    "k3446x": ["READ"],
    # 共享内核 rigol_scope/：按两系列手册**并集**判。唯一 MISS 是 families.py 里
    # "无 *OPT? 支持" 这条**否定性说明文字**（不是命令调用；两手册都没记载 *OPT?，
    # 与 MHO 实测"查询超时"一致）。
    "rigol_scope": ["*OPT"],
    # 探测脚本**故意**发无出处/待验证命令（探针语义），MISS 属预期。
    # *VID = 探测器里的 PowerShell 通配符（'*VID_1AB1*'），被提取器当成 IEEE-488 公共命令
    # 的形状了；非 SCPI，属已知提取假阳性。
    "scripts": ["*VID", "ATTN", "CHDR", "CPLE", "READ", "SANU", "SYST:FIRM", "TRDL",
                "VDIV", "WVTP"],
}

# 必须命中的代表命令（每套库抽最有代表性的几条，覆盖长/短形式与选择器剥离）
MUST_HIT: dict[str, list[str]] = {
    "rigol_scope": [":WAVeform:DATA?", ":MEASure:ITEM", ":DISPlay:DATA?",
                    ":ACQuire:TYPE", ":TRIGger:EDGE:SLOPe", ":TIMebase:MAIN:SCALe"],
    "dg832": [":SOUR{n}:APPL:SIN", ":SOUR{n}:VOLT:OFFS", ":OUTP{n}:LOAD",
              ":OUTP{n}:VOLL:HIGH?", ":COUN:MEAS?", ":SOUR{n}:SWE:TIME",
              ":SOUR{n}:FUNC:PULS:WIDT", ":SYST:CSC"],
    "dh1766": [":VOLT", ":CURR", ":OUTP", ":APPL:VOLT", ":SYST:ERR?", ":MEAS:VOLT?"],
    "dho": [":WAVeform:DATA?", ":MEASure:ITEM?", ":CHANnel1:SCALe", ":RUN"],
    "mho": [":WAVeform:DATA?", ":MEASure:ITEM?", ":DISPlay:DATA?", ":AUToset",
            ":SYSTem:LOCKed", ":MEASure:DELete"],
    "sds": [":MEASure:MODE", ":MEASure:SIMPle:ITEM", ":WAVeform:PREamble?",
            ":TRIGger:STATus?", ":SYSTem:SHUTdown"],
    "sdg": ["C1:BSWV", "C1:OUTP", ":BSWV?", "C1:MDWV"],
    "k3446x": [":MEAS:VOLT:DC?", ":CONF:VOLT:DC", ":SENS:VOLT:DC:NPLC", ":TRIG:SOUR"],
}

indexes = {t: A.build_index((ROOT / m).read_text(encoding="utf-8")) for t, _d, m in A.TARGETS}
multi_files = [ROOT / p for p in (
    "TEST_SCRIPTS/common/probe_new_instruments.py", "TEST_SCRIPTS/common/probe_all.py",
    "TEST_SCRIPTS/common/probe_siglent.py", "TEST_SCRIPTS/common/verify_all_devices.py",
    "TEST_SCRIPTS/common/verify_resolver.py",
    "TEST_SCRIPTS/common/usb_pnp_reset.py")]
EXTRA_FILES = {
    "dg832": ["TEST_SCRIPTS/dg832/verify_dg832.py",
              "TEST_SCRIPTS/dg832/test_dg832_write_matrix.py",
              "TEST_SCRIPTS/dg832/verify_dg832_edge_cases.py"],
    "sds": ["TEST_SCRIPTS/common/sds_simple_meas.py", "TEST_SCRIPTS/common/sds_snap.py",
            "TEST_SCRIPTS/common/sds_trace_analyze.py", "TEST_SCRIPTS/common/pixel_measure.py"],
    "mho": ["TEST_SCRIPTS/mho/verify_mho.py"],
    "dh1766": ["TEST_SCRIPTS/dh1766/test_dh1766_full.py",
               "TEST_SCRIPTS/dh1766/test_dh1766_modes.py",
               "TEST_SCRIPTS/dh1766/psu_remote_lock_probe.py"],
}


def group_files(tag: str, code_dir: str) -> list[Path]:
    files = [p for p in (ROOT / code_dir).rglob("*.py")]
    files += [ROOT / p for p in EXTRA_FILES.get(tag, [])]
    return [f for f in files if f not in multi_files]


groups: list[tuple[str, list[Path], set]] = [
    (tag, group_files(tag, code_dir), indexes[tag]) for tag, code_dir, _m in A.TARGETS]
groups.append(("scripts", multi_files, set().union(*indexes.values())))
# 共享内核按 dho ∪ mho 判（与 auditor 的 rigol_scope 组同口径）
groups.append(("rigol_scope",
               sorted((ROOT / "rigol_scope").rglob("*.py"))
               + [ROOT / "TEST_SCRIPTS/common/rigol_scope_reset.py"],
               indexes["dho"] | indexes["mho"]))

for tag, files, idx in groups:
    hit_keys, miss = set(), set()          # 与 auditor 同口径：按**唯一键**统计
    for f in files:
        if not f.exists():
            continue
        for cmd, _ln, interp in A.extract_cmds(A.strip_comments(f.read_text(encoding="utf-8"))):
            k = A.norm_head(cmd)
            if not k:
                continue
            if interp and A.is_dynamic(cmd):
                continue                    # DYN：静态不可核，与 auditor 同口径地两边都不计
            if A.is_hit(k, idx):
                hit_keys.add(k)
            else:
                miss.add(A.key_str(k))
    hits = len(hit_keys)
    want = set(MISS_BASELINE.get(tag, []))
    extra_miss = sorted(miss - want)          # 新出现的无出处命令 → 必须复核
    gone = sorted(want - miss)                # 基线里的 MISS 消失了 → 索引/手册变了
    check(f"{tag}: MISS 与基线一致", not extra_miss and not gone,
          f"{hits} HIT / {len(miss)} MISS" if not (extra_miss or gone)
          else f"新增 {extra_miss} / 消失 {gone}")

    for cmd in MUST_HIT.get(tag, []):
        check(f"{tag}: 必须命中 {cmd}", A.is_hit(A.norm_head(cmd), idx))

print(f"\n== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL: ' + ', '.join(fails[:6])} ==")
sys.exit(1 if fails else 0)
