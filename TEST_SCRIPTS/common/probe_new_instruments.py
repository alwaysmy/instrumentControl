"""新接入仪器 SCPI 冒烟探测（只读查询为主，不改设备设置、不触发输出）。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/probe_new_instruments.py

覆盖：Keysight 34465A / Siglent SDG2122X / Siglent SDS824X HD
地址由 common.resolver 解析（不写死 IP；历史标注的当时网段尾号已删除）
约定：仅查询类命令；不执行 *RST/:SYST:RESet 等复位；不改变任何输出状态。
输出：控制台 + TEST_DATA/common/new_instr_probe_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pyvisa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"

# 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
DEVICES = {
    "34465A": resolve("dmm"),
    "SDG2122X": resolve("sdg"),
    "SDS824X_HD": resolve("sds"),
}

QUERIES = {
    "34465A": [
        ("*IDN?", str), ("*OPT?", str), (":SYST:ERR?", str), (":CONF?", str),
        (":MEAS:VOLT:DC?", float), (":READ?", float),
    ],
    "SDG2122X": [
        ("*IDN?", str), (":SYST:ERR?", str),
        ("C1:OUTP?", str), ("C2:OUTP?", str),
        ("C1:BSWV WVTP?", str), ("C1:BSWV FRQ?", float), ("C1:BSWV AMP?", float),
        ("C2:BSWV WVTP?", str),
    ],
    "SDS824X_HD": [
        ("*IDN?", str), ("*OPT?", str), ("*OPC?", int), (":SYST:ERR?", str),
        ("C1:CPLE?", str), ("C1:ATTN?", str), ("C1:VDIV?", str),
        ("TRDL?", str), ("CHDR?", str),
    ],
}


def main() -> None:
    rm = pyvisa.ResourceManager()
    report: dict = {"timestamp": datetime.now().isoformat(timespec="seconds"), "devices": {}}
    for name, res in DEVICES.items():
        print(f"== {name}  {res} ==")
        entry = {}
        try:
            inst = rm.open_resource(res, open_timeout=5000)
            inst.timeout = 4000
            inst.read_termination = "\n"
            inst.write_termination = "\n"
            for cmd, cast in QUERIES[name]:
                try:
                    raw = inst.query(cmd).strip()
                    try:
                        val = cast(raw) if cast is not str else raw
                    except ValueError:
                        val = raw
                    entry[cmd] = {"ok": True, "value": val}
                    print(f"  {cmd:24s} -> {raw[:80]}")
                except Exception as e:
                    entry[cmd] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                    print(f"  {cmd:24s} -> FAIL {type(e).__name__}")
            inst.close()
        except Exception as e:
            entry["connect"] = {"ok": False, "error": str(e)}
            print(f"  连接失败: {e}")
        report["devices"][name] = entry

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"new_instr_probe_{stamp}.json"
    f.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n留痕已保存: {f}")


if __name__ == "__main__":
    main()
