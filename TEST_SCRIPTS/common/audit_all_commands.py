"""SCPI 命令全面审计器：扫描代码全部命令串，与提取手册比对存在性。

方法：
    1. 正则提取 .py 中 SCPI 形态字符串（f-string 骨架的 {} 归一为占位）；
    2. 手册命令头归一化：每段取大写前 4 字符（SCPI 短形式规则）建索引；
    3. 待验命令同样归一化后查索引，输出 HIT/MISS。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    ("dh1766", "dh1766_control/src/dh1766_control",
     "dh1766_control/docs/SCPI_COMMANDS_DH1766A.md"),
    ("dho", "dho_control",
     "dho_control/docs/DHO800编程手册_output/DHO800编程手册.md"),
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


def norm_head(cmd: str) -> str:
    """命令头归一化：去参数、按冒号分段、每段取大写前 4 字符拼接。"""
    cmd = cmd.strip().lstrip(":").split(" ")[0].split("?")[0].split(",")[0]
    cmd = re.sub(r"\{[^}]*\}", "", cmd)
    cmd = re.sub(r"<[^>]*>", "", cmd)
    segs = [s for s in cmd.split(":") if s]
    return "".join(s.upper()[:4] for s in segs)


def build_index(manual: str) -> set[str]:
    idx = set()
    # 两段及以上命令头（允许 <n>/<x> 占位与数字）
    for m in re.finditer(r":([A-Za-z]+(?:<[a-z0-9]+>|<[a-z]+[0-9]*>|\d+)*:[A-Za-z0-9<>]+(?:<[a-z0-9]+>)?(?::[A-Za-z0-9<>]+)*)", manual):
        idx.add(norm_head(m.group(1)))
    # 单段根命令（:RUN、:STOP、*CLS 等）
    for m in re.finditer(r":([A-Z]{3,8})(?![A-Za-z])", manual):
        idx.add(m.group(1)[:4])
    for m in re.finditer(r"\*([A-Z]{2,5})", manual):
        idx.add("*" + m.group(1)[:4])
    return idx


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


def extract_cmds(py_text: str) -> list[tuple[str, int]]:
    out = []
    for m in re.finditer(r'"(\*[A-Z]{2,5}[?]?|:[A-Za-z][A-Za-z0-9:{}<_,. ]*\??)"', py_text):
        s = m.group(1)
        if len(s) >= 3:
            ln = py_text[: m.start()].count("\n") + 1
            out.append((s, ln))
    for m in re.finditer(r'f"([:*][A-Za-z][A-Za-z0-9:{}<_,. ]*)"', py_text):
        s = m.group(1).replace("{n}", "1").replace("{ch}", "C1")
        s = re.sub(r"\{[^}]*\}", "X", s)
        ln = py_text[: m.start()].count("\n") + 1
        out.append((s, ln))
    return out


def main() -> int:
    report = []
    total_miss = 0
    for tag, code_dir, manual_rel in TARGETS:
        manual_path = ROOT / manual_rel
        idx = build_index(manual_path.read_text(encoding="utf-8"))
        files = [p for p in (ROOT / code_dir).rglob("*.py")]
        # common 脚本按其服务的设备归组：sds_simple_meas→sds，probe_new_instruments→k3446x
        if tag == "sds":
            files.append(ROOT / "TEST_SCRIPTS/common/sds_simple_meas.py")
            files.append(ROOT / "TEST_SCRIPTS/common/sds_snap.py")
            files.append(ROOT / "TEST_SCRIPTS/common/sds_trace_analyze.py")
            files.append(ROOT / "TEST_SCRIPTS/common/pixel_measure.py")
        if tag == "k3446x":
            files.append(ROOT / "TEST_SCRIPTS/common/probe_new_instruments.py")
        seen = {}
        for f in files:
            text = strip_comments(f.read_text(encoding="utf-8"))
            rel = f.relative_to(ROOT)
            for cmd, ln in extract_cmds(text):
                h = norm_head(cmd)
                if not h or h in ("SYST",):
                    if h == "SYST":
                        pass
                key = h
                hit = key in idx
                if key not in seen or not seen[key][2]:
                    seen[key] = (cmd, f"{rel}:{ln}", hit)
        misses = [(c, loc) for c, loc, hit in seen.values() if not hit]
        hits = sum(1 for _, _, hit in seen.values() if hit)
        total_miss += len(misses)
        print(f"== {tag}: {hits} HIT, {len(misses)} MISS ==")
        report.append(f"## {tag}\n")
        for c, loc, hit in sorted(seen.values(), key=lambda x: x[1]):
            mark = "HIT " if hit else "**MISS**"
            report.append(f"- [{mark}] `{c}` @ {loc}")
            if not hit:
                print(f"  MISS: {c}  @ {loc}")
        report.append("")
    (ROOT / "docs" / "command_audit_full_20260823.md").write_text(
        "# SCPI 全量审计（代码 vs 手册）\n\n" + "\n".join(report),
        encoding="utf-8",
    )
    print(f"\n总 MISS: {total_miss}；报告: docs/command_audit_full_20260823.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
