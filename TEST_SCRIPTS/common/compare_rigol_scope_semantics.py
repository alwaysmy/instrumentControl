"""DHO800/900 与 MHO900 编程手册的**语义层**比对：同名命令的参数集/取值差异。

命令名一致不等于语义一致（枚举值、返回格式、默认值可能不同）。本脚本对两套驱动
**实际会用到**的命令，逐条摘出两份手册里的 `{A|B|C}` 枚举与默认值，并排打印差异，
供"能否合并驱动"的决策与后续合并时的差异表使用。

用法：python TEST_SCRIPTS/common/compare_rigol_scope_semantics.py [--full]
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DHO = ROOT / "dho_control/docs/DHO800编程手册_output/DHO800编程手册.md"
MHO = ROOT / "mho_control/docs/MHO900编程手册_output/MHO900编程手册.md"
OUT_DIR = ROOT / "TEST_DATA" / "common"

# 两套驱动都会用到的关键命令（段键 → 手册里的小节标题样式）
CASES = [
    ("ACQuire:TYPE",       r":ACQuire:TYPE"),
    ("ACQuire:MDEPth",     r":ACQuire:MDEPth"),
    ("ACQuire:SRATe?",     r":ACQuire:SRATe"),
    ("CHANnel:DISPlay",    r":CHANnel<n>:DISPlay"),
    ("CHANnel:SCALe",      r":CHANnel<n>:SCALe"),
    ("CHANnel:OFFSet",     r":CHANnel<n>:OFFSet"),
    ("CHANnel:COUPling",   r":CHANnel<n>:COUPling"),
    ("CHANnel:PROBe",      r":CHANnel<n>:PROBe"),
    ("CHANnel:BWLimit",    r":CHANnel<n>:BWLimit"),
    ("TIMebase:MAIN:SCALe", r":TIMebase:MAIN:SCALe"),
    ("TIMebase:MAIN:OFFSet", r":TIMebase:MAIN:OFFSet"),
    ("TRIGger:MODE",       r":TRIGger:MODE"),
    ("TRIGger:STATus?",    r":TRIGger:STATus"),
    ("TRIGger:SWEep",      r":TRIGger:SWEep"),
    ("TRIGger:EDGE:SLOPe", r":TRIGger:EDGE:SLOPe"),
    ("TRIGger:EDGE:SOURce", r":TRIGger:EDGE:SOURce"),
    ("MEASure:ITEM",       r":MEASure:ITEM"),
    ("MEASure:CLEar/DELete", r":MEASure:(CLEar|DELete)"),
    ("WAVeform:SOURce",    r":WAVeform:SOURce"),
    ("WAVeform:MODE",      r":WAVeform:MODE"),
    ("WAVeform:FORMat",    r":WAVeform:FORMat"),
    ("WAVeform:POINts",    r":WAVeform:POINts"),
    ("WAVeform:PREamble?", r":WAVeform:PREamble"),
    ("DISPlay:DATA?",      r":DISPlay:DATA"),
    ("SYSTem:ERRor?",      r":SYSTem:ERRor"),
    ("SYSTem:VERSion?",    r":SYSTem:VERSion"),
]


def section(text: str, pattern: str, span: int = 2600) -> str:
    """截取命令小节正文（标题行起 span 字符）。"""
    m = re.search(r"^#{1,4}\s*[0-9.]*\s*" + pattern + r"\b", text, re.M)
    if not m:
        m = re.search(r"^#{1,4}.*" + pattern + r"\b", text, re.M)
    if not m:
        return ""
    i = m.start()
    nxt = re.search(r"^#{1,3}\s*[0-9.]+\s", text[i + 10:], re.M)
    end = i + 10 + (nxt.start() if nxt else span)
    return text[i : min(end, i + span)]


def enums(body: str) -> list[str]:
    """摘出 `{A|B|C}` 枚举（去重、保序，过滤明显非枚举的噪声）。"""
    out, seen = [], set()
    for raw in re.findall(r"\{([^{}]{1,120})\}", body):
        vals = [v.strip() for v in raw.replace("\n", " ").split("|")]
        vals = [v for v in vals if v and len(v) <= 24 and re.fullmatch(r"[A-Za-z0-9_+\-\. ]+", v)]
        if len(vals) >= 2:
            key = "|".join(vals)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def ranges(body: str) -> list[str]:
    """摘出"范围"表里的取值线索（如 1 至 1000 / 1k|10k|…）。"""
    out = []
    for m in re.finditer(r"[:：]?\s*([0-9][^\n]{0,40}?至[^\n]{0,40})", body):
        s = m.group(1).strip()
        if s and s not in out:
            out.append(s)
    return out[:3]


def main() -> int:
    dho_t, mho_t = DHO.read_text(encoding="utf-8"), MHO.read_text(encoding="utf-8")
    rows = []
    print("=== 同名命令的语义比对（DHO800/900  vs  MHO900）===\n")
    for tag, pat in CASES:
        bd, bm = section(dho_t, pat), section(mho_t, pat)
        ed, em = enums(bd), enums(bm)
        same = ed == em
        rows.append({"cmd": tag, "same_enums": same, "dho_enums": ed, "mho_enums": em,
                     "dho_found": bool(bd), "mho_found": bool(bm)})
        mark = "一致" if same else ("**不同**" if (ed or em) else "（两侧都没摘到枚举）")
        print(f"--- {tag}  → {mark}")
        if not bd:
            print("    DHO: 手册未找到该小节")
        if not bm:
            print("    MHO: 手册未找到该小节")
        if not same:
            print(f"    DHO: {ed[:4]}")
            print(f"    MHO: {em[:4]}")
        elif ed:
            print(f"    共同: {ed[:3]}")

    diff = [r for r in rows if not r["same_enums"] and (r["dho_enums"] or r["mho_enums"])]
    missing = [r for r in rows if not r["dho_found"] or not r["mho_found"]]
    print(f"\n=== 摘要：{len(rows)} 条比对，{len(diff)} 条枚举不同，{len(missing)} 条某侧手册缺小节 ===")
    for r in diff:
        print(f"  枚举不同: {r['cmd']}")
    for r in missing:
        print(f"  手册缺小节: {r['cmd']}（DHO={r['dho_found']} MHO={r['mho_found']}）")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"rigol_scope_semantics_{stamp}.json"
    import json
    out.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"),
                               "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n留痕: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
