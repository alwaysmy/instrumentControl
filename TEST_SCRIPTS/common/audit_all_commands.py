"""SCPI 命令全面审计器：扫描代码全部命令串，与提取手册比对存在性。

方法（2026-09-15 重写提取与归一化，见下）：
    1. 逐字符串字面量提取其中的 SCPI 片段（≥2 段冒号链 / 单段查询 / *公共命令）；
    2. 两侧按**同一套** SCPI 短形式规则归一：每段取大写前缀（=SDS 手册的长短形式规则），
       剥掉通道选择器前缀（C1/C{n}/{ch}…）与占位符（{n}/<n>/尾数字）；
    3. 归一化键相等即 HIT；不等输出 MISS。

为什么重写（旧版的两个结构性缺陷）
----------------------------------
① **漏检**：旧提取器只认"以 `:` 或 `*` 开头"的字符串字面量，于是 `C{n}:VDIV?`、
   `{ch}:OUTP?`、`TDIV?`、`PRIN? BMP`、`ACQ:MDEP?` 这类**不带前导冒号**的常量根本不
   进扫描——`sds_control/sds.py` 只被抽出 7 条、`sdg_control/commands.py` 只 2 条，
   而这几套库里最可疑的命令（SDS 的 `VDIV/OFST/ATTN/TDIV/TRDL` 实测在手册里查无出处）
   恰好全在这一类里。审计器对自己最该管的命令是盲的。
② **假阳性**：旧归一化逐段截"大写前 4 字符"，手册写全拼、代码写短形式时对不上
   （Keysight `:MEAS:VOLT:DC?` vs 手册 `:MEASure:VOLTage:DC?`）；单段混合大小写根命令
   （`:CLEar`/`:SINGle`/`:TFORce`/`:AUToset`）因索引正则 `:([A-Z]{3,8})(?![A-Za-z])`
   整条不入索引 → 稳定误报。

已知边界（刻意保守，宁可报 MISS 也不放过）
------------------------------------------
- 归一化按"大写前缀=短形式"规则，因此**大小写写错的段**会被判 MISS（例如把手册的
  `SCALe` 写成 `SCALE`：`SCALE` 无小写 → 键 `SCALE` ≠ 手册键 `SCAL`）。方向是安全的：
  审计的职责是"代码里没有无出处的命令"，多报要人工甄别，漏报才是事故。
- 手册侧只按冒号链与单段命令建索引，示例代码里的变量名（如 SDS 手册 Python 例程里的
  `TDIV_ENUM`）不会被误当成命令——它们没有前导冒号。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    ("dh1766", "dh1766_control/src/dh1766_control",
     "dh1766_control/docs/SCPI_COMMANDS_DH1766A.md"),
    ("dg832", "dg832_control",
     "dg832_control/docs/02_编程手册.txt"),
    ("dho", "dho_control",
     "dho_control/docs/DHO800编程手册_output/DHO800编程手册.md"),
    ("mho", "mho_control",
     "mho_control/docs/MHO900编程手册_output/MHO900编程手册.md"),
    ("sds", "sds_control",
     "sds_control/docs/SDS800XHD_Series_ProgrammingGuide_CN11G_output/"
     "SDS800XHD_Series_ProgrammingGuide_CN11G.md"),
    ("sdg", "sdg_control",
     "sdg_control/docs/SDG_Programming-Guide_PG02_C02C_output/"
     "SDG_Programming-Guide_PG02_C02C.md"),
    ("k3446x", "keysight_3446x",
     "keysight_3446x/docs/Truevolt_Series_Operating_and_Service_Guide_output/"
     "Truevolt_Series_Operating_and_Service_Guide.md"),
]

SCRIPT_DIRS = ["TEST_SCRIPTS/dh1766", "TEST_SCRIPTS/dho", "TEST_SCRIPTS/common"]

# ---- SCPI 片段提取 ----
# 段：可带占位符（`{ch}`/`<n>`）+ 名称 + 可选后缀（CHANnel1 / CHANnel<n> / C{n} / D15）。
# 首段允许**直接以占位符开头**——SDG/SDS 常量写作 `{ch}:OUTP?`，不允许的话整条命令
# 会从 `:OUTP?` 起才匹配，前缀丢失（实测踩过：sdg_control/commands.py 只能抽到 2 条）。
_SEG = (r"(?:\{[^{}]*\}|<[^<>]*>|[A-Za-z][A-Za-z0-9]*"
        r"(?:\{[^{}]*\}|<[^<>]*>|\d+)?)")
_STR_LIT_RE = re.compile(r'''(?:[fFrRbB]{0,2})("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')''')
_CMD_RE = re.compile(
    r"(?P<common>\*[A-Za-z]{2,5}\??)"                     # *IDN? / *RST / *CLS
    r"|(?P<chain>" + _SEG + r"(?::" + _SEG + r")+\??)"    # ≥2 段：A:B / A:B:C?
    r"|(?P<single>[A-Za-z][A-Za-z0-9]{3,}\?(?=\s|$|[,\"']))"  # 单段查询：TDIV? / PRIN?
)
# 单段查询里明显不是 SCPI 的英文词（避免 "PASS?" 之类混进 MISS）
_SINGLE_STOPLIST = {"PASS", "FAIL", "OKAY", "READY", "DONE", "TRUE", "FALSE", "NONE",
                    "WHY", "HOW", "WHAT", "WHEN", "WHO"}

# 通道/信源选择器前缀（首段命中即剥掉）：C / C1 / C{n} / {ch} / P<n> / D0 / CHANnel<n> …
_SELECTOR_RE = re.compile(
    r"^(?:\{\w+\}|<[\w]+>)$"                          # {ch} / <n>
    r"|^[A-Za-z]{1,2}(?:\d+|\{[^}]*\}|<[^<>]*>)?$"    # C / C1 / C{n} / P2 / D0 / M1
    r"|^[A-Za-z]{2,}(?:\{[^}]*\}|<[^<>]*>$)"          # CHANnel<n> 这类"名字+占位符"
)


def _seg_key(seg: str) -> str:
    """段归一化：去占位符/尾数字 → 取大写前缀（无小写则整体大写）；纯占位段返回空串。"""
    s = re.sub(r"\{[^}]*\}|<[^<>]*>", "", seg)
    if not s:
        return ""                 # `{n}`/`<node>` 这类纯占位段：不是命令名的一部分
    s = re.sub(r"\d+$", "", s) or s
    m = re.match(r"[A-Z]+", s)
    if m and m.group() and m.group() != s:
        return m.group()          # 混合大小写：大写前缀即 SCPI 短形式
    return s.upper()


def norm_head(cmd: str) -> tuple[str, ...]:
    """命令头归一化：取命令段（去参数），逐段归一后返回**段键元组**；剥掉首段通道选择器。

    `C{n}:VDIV?` → `("VDIV",)`；`:MEASure:MODE SIMPle` → `("MEAS","MODE")`；
    `{ch}:OUTP?` → `("OUTP",)`（对上手册 `:OUTPut`）；`*IDN?` → `("*IDN",)`。

    返回元组而非拼接串：段边界必须保留，否则"段内前缀"无法判定
    （代码写全拼 `COUPLING`、手册写 `COUPling` 时，拼成串就再也对不上了）。
    """
    cmd = cmd.strip()
    cmd = cmd.split(" ")[0].split("?")[0].split(",")[0]
    star = cmd.startswith("*")
    cmd = cmd.lstrip("*:").strip()
    if not cmd:
        return ("*",) if star else ()
    segs = [s for s in cmd.split(":") if s]
    if len(segs) > 1 and _SELECTOR_RE.match(segs[0]):
        segs = segs[1:]            # 通道选择器不是 SCPI 路径的一部分
    keys = tuple(k for k in (_seg_key(s) for s in segs) if k)   # 纯占位段（{base}）归一后为空 → 丢
    if not keys:
        return ()
    if star:
        return tuple("*" + keys[0] if i == 0 else k for i, k in enumerate(keys))
    return keys


def is_dynamic(cmd: str) -> bool:
    """命令是否含**整段占位符**（`{base}:{v}?` / `CONF:{base}` 这类运行时拼接）。

    只对 **f-string 里拼出来的**命令串启用（见 extract_cmds 的 interpolated 标记）：
    命令名本身是算出来的，静态无从核对手册。而 `.format()`/`{}` 模板常量
    （如 `":STATus:QUES:INST:ISUM{n}:{node}?"`）是**完整命令模板**，仍照常核对。
    """
    return bool(re.search(r"(?:^|:)\{[^{}]*\}(?=:|$|\?)", cmd))


def key_str(keys: tuple[str, ...]) -> str:
    """段键元组 → 展示串（报告/日志用）。"""
    return ":".join(keys)


def _iter_candidates(literal: str):
    """从单个字符串字面量的内容里提取 SCPI 片段（跳过中段匹配）。"""
    for m in _CMD_RE.finditer(literal):
        s = m.start()
        if s > 0:
            prev = literal[s - 1]
            if prev.isalnum() or prev == "_":
                continue                              # 词中段（如 "abcMEAS:..."）
            if prev == ":" and s > 1 and (literal[s - 2].isalnum() or literal[s - 2] in "}_"):
                continue                              # 冒号链中段（整条已在更早位置匹配）
        text = m.group(0)
        if m.lastgroup == "single" or (text.endswith("?") and ":" not in text
                                       and not text.startswith("*")):
            if text[:-1].upper() in _SINGLE_STOPLIST:
                continue
        yield text


def _docstring_nodes(tree) -> set[int]:
    """收集模块/类/函数**文档字符串**节点的 id（它们是说人话的地方，不参与审计）。"""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                ids.add(id(body[0].value))
    return ids


def _joined_str_text(node: "ast.JoinedStr") -> str:
    """把 f-string 还原成带 `{占位}` 的模板串，使被插值切断的命令重新拼回整条。

    例：`f":MEASure:ADVanced:P{n}:TYPE {t}"` 在 AST 里是 3 个片段
    （常量 / FormattedValue / 常量），不还原就会抽出 `:MEASure:ADVanced:P` 与 `:TYPE`
    两条残缺命令（旧版提取器同样会漏掉这类写法）。
    """
    out = []
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            out.append(part.value)
        elif isinstance(part, ast.FormattedValue):
            name = ""
            if isinstance(part.value, ast.Name):
                name = part.value.id
            elif isinstance(part.value, ast.Attribute):
                name = part.value.attr
            out.append("{" + (name or "x") + "}")
        else:
            out.append("{}")
    return "".join(out)


def extract_cmds(py_text: str) -> list[tuple[str, int, bool]]:
    """扫描源码，返回 [(命令串, 行号, 是否来自 f-string 拼接)]。

    基于 AST：只看**字符串字面量**，且排除文档字符串（docstring 里写的是给人看的
    命令描述，常带缩写路径与中文，收进来会变成一堆假 MISS）；f-string 还原成模板串。
    Python 源码解析失败时退化为"整体正则扫"，保证脚本对非 .py 文本仍可用。
    """
    out: list[tuple[str, int, bool]] = []
    try:
        tree = ast.parse(py_text)
    except SyntaxError:
        tree = None
    if tree is None:                      # 非 Python 文本：退化为整体正则扫（无 f-string 概念）
        for lit in _STR_LIT_RE.finditer(py_text):
            for cand in _iter_candidates(lit.group(1)[1:-1]):
                out.append((cand, py_text[: lit.start(1)].count("\n") + 1, False))
        return out
    skip = _docstring_nodes(tree)
    for node in ast.walk(tree):
        interpolated = isinstance(node, ast.JoinedStr)
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in skip):
            body = node.value
        elif interpolated:
            body = _joined_str_text(node)
        else:
            continue
        if not body.strip():
            continue
        for cand in _iter_candidates(body):
            out.append((cand, node.lineno, interpolated))
    return out


def build_index(manual: str) -> set[tuple[str, ...]]:
    """手册命令 → 段键元组索引。

    四类写法都要覆盖（各手册体例不同，实测）：
      ① 带前导冒号的冒号链：`:WAVeform:SOURce`（RIGOL/Siglent 提取版体例）；
      ② **不带**前导冒号的冒号链：`CONFigure:TEMPerature`（Keysight Truevolt 提取版
         通篇如此，只按 ① 建索引会一条都不命中）；
      ③ 单段命令：`:RUN` / `:PRINt?` / `:CLEar` / `:AUToset`；
      ④ IEEE-488 公共命令：`*IDN` / `*RST`。
    """
    idx: set[tuple[str, ...]] = set()
    for m in re.finditer(r":(" + _SEG + r"(?::" + _SEG + r")+)", manual):
        idx.add(norm_head(m.group(1)))
    for m in re.finditer(r"(?<![:\w])(" + _SEG + r"(?::" + _SEG + r")+)", manual):
        idx.add(norm_head(m.group(1)))
    for m in re.finditer(r":([A-Z][A-Za-z]{2,15})(?![\w:])", manual):
        idx.add(norm_head(m.group(1)))     # 单段命令：大写开头、≥3 字符（滤掉 ":A" 之类噪声）
    for m in re.finditer(r"\*([A-Za-z]{2,5})\b", manual):
        idx.add(("*" + m.group(1).upper(),))
    idx.discard(())
    return idx


def _seg_match(a: str, b: str) -> bool:
    """单段比较：完全相等，或一方是另一方的前缀（较短者 ≥3 字符）。

    覆盖两种真实写法差异：① 一侧写全拼、另一侧写短形式（代码 `COUPLING` vs 手册
    `COUPling`；代码 `MEAS:RES` vs 手册 `MEASure:RESistance`）；② SCPI 长短形式之间的
    任意前缀缩写。较短段设 3 字符下限，避免 `D`/`M` 这类单字母选择器乱配。
    """
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 3 and long_.startswith(short)


def is_hit(keys: tuple[str, ...], idx: set[tuple[str, ...]]) -> bool:
    """命令键是否命中手册索引。

    判定两种形态：
      ① **整条同长逐段匹配**（段内允许长短形式差异）；
      ② **后缀路径匹配**——手册只单列了子节点（SDS 提取版把 `:DTIMe<n>` 与
         `:MEASure:ADVanced` 分开写）、或代码用 SCPI 允许的尾部路径缩写时命中。

    未做的校验：段序颠倒、多段/少段的前缀路径（如代码写 `:MEAS:VOLT` 而手册只有
    `:MEASure:VOLTage:DC`）会判 MISS——方向保守，报出来人工一眼可辨；逐字符正确性
    仍由设备 `SYST:ERR?` 兜底（AGENTS.md 铁律 3）。
    """
    if keys in idx:
        return True
    n = len(keys)
    for cand in idx:
        m = len(cand)
        if m <= n and all(_seg_match(x, y) for x, y in zip(keys[n - m:], cand)):
            return True
    return False


def strip_comments(py_text: str) -> str:
    out = []
    for line in py_text.splitlines():
        # 简易剥离：非引号内的 # 之后内容
        code, in_str, esc = [], None, False
        for chch in line:
            if esc:
                code.append(chch)
                esc = False
                continue
            if chch == "\\":
                code.append(chch)
                esc = True
                continue
            if in_str:
                code.append(chch)
                if chch == in_str:
                    in_str = None
                continue
            if chch in "\"'":
                in_str = chch
                code.append(chch)
                continue
            if chch == "#":
                break
            code.append(chch)
        out.append("".join(code))
    return "\n".join(out)


def main() -> int:
    report = [f"<!-- 由 TEST_SCRIPTS/common/audit_all_commands.py 生成，勿手改；"
              f"重跑即覆盖。MISS 需人工甄别（判别口径见 docs/review_20260915.md §四）。 -->\n"]
    total_miss = 0
    indexes: dict[str, set[tuple[str, ...]]] = {}
    for tag, code_dir, manual_rel in TARGETS:
        manual_path = ROOT / manual_rel
        indexes[tag] = build_index(manual_path.read_text(encoding="utf-8"))
    # 跨设备脚本（探测/巡检类）按"全部手册索引的并集"审计——它们本来就同时访问多台仪器
    groups: list[tuple[str, list[Path], set[tuple[str, ...]]]] = []
    for tag, code_dir, _m in TARGETS:
        groups.append((tag, [p for p in (ROOT / code_dir).rglob("*.py")], indexes[tag]))
    # common 脚本按其服务的设备归组：sds_simple_meas→sds，probe_new_instruments→k3446x
    multi = [ROOT / "TEST_SCRIPTS/common/probe_new_instruments.py",
             ROOT / "TEST_SCRIPTS/common/probe_all.py",
             ROOT / "TEST_SCRIPTS/common/probe_siglent.py",
             ROOT / "TEST_SCRIPTS/common/verify_all_devices.py",
             ROOT / "TEST_SCRIPTS/common/verify_resolver.py"]
    extra = {
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
    for tag, files, idx in groups:
        files = list(files) + [ROOT / p for p in extra.get(tag, [])]
        files = [f for f in files if f not in multi]
        total_miss += _audit_group(tag, files, idx, report)
    union: set[tuple[str, ...]] = set().union(*indexes.values())
    total_miss += _audit_group("scripts(multi-device，按全部手册并集判)", multi, union, report)
    # 共享内核：DHO800/900 与 MHO900 共用 rigol_scope/，其命令按**两手册并集**判
    # （共享命令两边都该有；差异分支里的专用拼写——如 :MEASure:CLEar / :MEASure:DELete——
    #  命中其一即可。逐家族的拼写仍由 dho/mho 各自的 TARGETS 按各自手册核对。）
    rigol_files = sorted((ROOT / "rigol_scope").rglob("*.py")) + [
        ROOT / "TEST_SCRIPTS/common/rigol_scope_reset.py"]
    total_miss += _audit_group("rigol_scope(共享内核，按两系列并集判)",
                               rigol_files, indexes["dho"] | indexes["mho"], report)

    (ROOT / "docs" / "command_audit_full_20260823.md").write_text(
        "# SCPI 全量审计（代码 vs 手册）\n\n"
        "判据：命令键（逐段取 SCPI 短形式、剥掉通道选择器）命中手册索引 = HIT；\n"
        "命中含「后缀命中」（手册只单列子节点、或代码用 SCPI 尾部路径缩写的情况）。\n"
        "**MISS 不等于猜测命令**——需逐条核对手册后归档（历史甄别见\n"
        "`docs/command_audit_20260823.md` 与本轮 `docs/review_20260915.md`）。\n\n"
        + "\n".join(report),
        encoding="utf-8",
    )
    print(f"\n总 MISS: {total_miss}；报告: docs/command_audit_full_20260823.md")
    return 0


def _audit_group(tag: str, files: list[Path], idx: set[tuple[str, ...]],
                 report: list[str]) -> int:
    """审计一组文件（同设备族）并与索引比对；返回 MISS 数，追加报告段落。"""
    seen: dict[tuple[str, ...], tuple[str, str, bool]] = {}
    dyn: dict[tuple[str, ...], tuple[str, str]] = {}
    for f in files:
        if not f.exists():
            continue
        source = f.read_text(encoding="utf-8")
        rel = f.relative_to(ROOT)
        for cmd, ln, interp in extract_cmds(strip_comments(source)):
            key = norm_head(cmd)
            if not key:
                continue
            hit = is_hit(key, idx)
            if interp and is_dynamic(cmd):
                # f-string 拼出来的命令名：静态不可核，一律列 DYN
                # （既不算 MISS 也不算 HIT——否则 f"state:{cmd}" 这类日志串会因
                #   段内前缀兼容偶然命中 `:STATe`，在报告里冒充一条"命令"）
                dyn.setdefault(key, (cmd, f"{rel}:{ln}"))
                continue
            # 同一命令只留一处出处；HIT 与 MISS 各自保留更早的那条
            if key not in seen or (seen[key][2] != hit):
                seen[key] = (cmd, f"{rel}:{ln}", hit)
    misses = [(c, loc) for c, loc, hit in seen.values() if not hit]
    hits = sum(1 for _, _, hit in seen.values() if hit)
    print(f"== {tag}: {hits} HIT, {len(misses)} MISS, {len(dyn)} DYN ==")
    report.append(f"## {tag}（{hits} HIT / {len(misses)} MISS / {len(dyn)} DYN）\n")
    for c, loc, hit in sorted(seen.values(), key=lambda x: x[1]):
        mark = "HIT " if hit else "**MISS**"
        report.append(f"- [{mark}] `{c}` @ {loc}")
        if not hit:
            print(f"  MISS: {c}  @ {loc}")
    for c, loc in sorted(dyn.values(), key=lambda x: x[1]):
        report.append(f"- [DYN ] `{c}` @ {loc}（运行时拼接，静态不可核）")
    report.append("")
    return len(misses)


if __name__ == "__main__":
    sys.exit(main())
