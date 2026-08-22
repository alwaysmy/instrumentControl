"""Siglent 两台仪器 SCPI 查询格式修正验证（只读）。

背景：首轮探测中 SDG2122X 的 `C1:BSWV WVTP?` 子参数式查询超时，
SDS824X HD 的 `C1:CPLE?` 命令名待核实；本脚本试整体查询与候选命令名。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/probe_siglent.py

输出：控制台 + TEST_DATA/common/siglent_probe_<时间戳>.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pyvisa

OUT_DIR = Path(__file__).resolve().parents[2] / "TEST_DATA" / "common"


def query_many(rm: pyvisa.ResourceManager, res: str, cmds: list[str], tag: str) -> dict:
    entry: dict = {}
    inst = rm.open_resource(res, open_timeout=5000)
    inst.timeout = 4000
    inst.read_termination = "\n"
    inst.write_termination = "\n"
    try:
        for cmd in cmds:
            try:
                raw = inst.query(cmd).strip()
                entry[cmd] = {"ok": True, "value": raw[:200]}
                print(f"  [{tag}] {cmd:20s} -> {raw[:110]}")
            except Exception as e:
                entry[cmd] = {"ok": False, "error": type(e).__name__}
                print(f"  [{tag}] {cmd:20s} -> FAIL {type(e).__name__}")
    finally:
        inst.close()
    return entry


def main() -> None:
    rm = pyvisa.ResourceManager()
    report: dict = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "devices": {"SDG2122X": {}, "SDS824X_HD": {}},
    }

    print("== SDG2122X  .206 ==")
    report["devices"]["SDG2122X"] = query_many(
        rm,
        "TCPIP0::192.168.31.206::inst0::INSTR",
        [
            "C1:BSWV?",          # 基础波形参数整体查询
            "C2:BSWV?",
            "C1:OUTWV?",         # 输出阻抗/负载等
            "C1:MDWV?",          # 调制参数整体查询
            "SYST:VERS?",
            "SYST:FIRM?",
            "C1:SWEEPWV?",
        ],
        "SDG",
    )

    print("== SDS824X HD  .220 ==")
    report["devices"]["SDS824X_HD"] = query_many(
        rm,
        "TCPIP0::192.168.31.220::inst0::INSTR",
        [
            "C1:COUPLING?",      # 耦合候选名 A
            "CPL?",              # 耦合候选名 B
            "C1:OFF?",           # 垂直偏移
            "C1:SKEW?",          # 通道偏斜
            "SANU? 1",           # 屏幕模拟量？探针性查询
            "HORI:SCAL?",        # 时基档位候选
            "TRIG:MODE?",        # 触发模式
            "TRIG:SOURCE?",
            "ACQ:MDEP?",         # 存储深度候选
        ],
        "SDS",
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"siglent_probe_{stamp}.json"
    f.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    devices = report["devices"]
    n_ok = sum(1 for d in devices.values() for v in d.values() if v.get("ok"))
    n_all = sum(len(d) for d in devices.values())
    print(f"\n结果: {n_ok}/{n_all} OK")
    print(f"留痕已保存: {f}")


if __name__ == "__main__":
    main()
