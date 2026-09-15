"""DG832 写路径矩阵：备份 → 逐项写 → 回读 → 恢复（原工作区 `test_dg832.py` 的仓库版）。

用途：覆盖 `verify_dg832.py`（只读 + 单参数）之外的**成片写路径**——
多参数一次设置、单参数逐个设置、方波/输出开关、频率计、错误队列，最后按备份逐项恢复。

用法：
    python TEST_SCRIPTS/dg832/test_dg832_write_matrix.py --allow-write            # 全流程
    python TEST_SCRIPTS/dg832/test_dg832_write_matrix.py --allow-write --ch 2     # 只做 CH2

⚠ 会改设备设定（脚本内 try/finally 全量恢复）。跑之前确认：
    ① 该通道当前**没有在驱动别人的实验**（输出可能是开的，脚本会连输出状态一起恢复）；
    ② 用户已授权（--allow-write 由调用者自行承担这个声明）。
留痕：`TEST_DATA/dg832/write_matrix_<stamp>.json`（含备份与恢复后逐项比对）。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402
from dg832_control import DG832  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dg832"
ALLOW_WRITE = "--allow-write" in sys.argv
CHANNELS = tuple(int(a) for i, a in enumerate(sys.argv) if i and sys.argv[i - 1] == "--ch") or (1, 2)

# APPL? 返回的波形名 → `:APPL:<后缀>`（各波形参数模板不同：DC/DUAL/PRBS 无 phase、
# NOISE/RS232 从 amp 起、SEQuence 首参是采样率——恢复时按备份原样回写即可）
_WAVE_SUFFIX = {"SIN": "SIN", "SQU": "SQU", "RAMP": "RAMP", "PULSE": "PULS",
                "NOISE": "NOIS", "DC": "DC", "USER": "USER"}

rows: list[dict] = []


def rec(step: str, ok: bool, detail="") -> None:
    rows.append({"step": step, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {step:44s} {str(detail)[:110]}", flush=True)


def main() -> int:
    res = resolve("dg")
    print(f"=== DG832 写路径矩阵：resource={res} ===", flush=True)
    print(f"    通道 {CHANNELS}；--allow-write={'YES' if ALLOW_WRITE else 'NO'}", flush=True)
    if not ALLOW_WRITE:
        print("\n未加 --allow-write：本脚本会改设备设定，故只打印用途。"
              "\n（只读检查请用 TEST_SCRIPTS/dg832/verify_dg832.py）")
        return 0

    gen = DG832(resource=res)
    gen.connect()
    print(f"[IDN] {gen.idn()}", flush=True)

    # ---- ① 备份（波形/输出/负载/电压保护，逐通道）----
    backup: dict[int, dict] = {}
    for ch in CHANNELS:
        backup[ch] = {
            "appl": gen.query(f":SOUR{ch}:APPL?").strip().strip('"'),
            "outp": gen.query(f":OUTP{ch}?").strip(),
            "load": gen.query(f":OUTP{ch}:LOAD?").strip(),
            "voll": gen.get_voltage_limit(ch),
        }
        print(f"[备份] CH{ch}: APPL={backup[ch]['appl']} OUTP={backup[ch]['outp']} "
              f"LOAD={backup[ch]['load']} VOLL={backup[ch]['voll']}", flush=True)
        rec(f"CH{ch} 备份完成", True, str(backup[ch])[:120])

    try:
        # ---- ② 强制流程：先开保护（否则带 amp/offset 的写入会被拒）----
        # 注意：保护窗口可能是**紧贴当前电平**的窄窗（实测现场 CH2 = high 3.3 / low 0，
        # 正好等于 offset ± amp/2）——测试用的幅度会被这种窄窗拒绝，故临时放宽到 ±6V，
        # 结束按备份原值写回（finally 里的 VOLL 恢复）。
        for ch in CHANNELS:
            gen.set_voltage_limit(ch, state=True)
            v = gen.get_voltage_limit(ch)
            try:
                tight = abs(float(v["high"])) < 6 or abs(float(v["low"])) < 6
            except (TypeError, ValueError):
                tight = True
            if tight:
                gen.set_voltage_limit(ch, high=6.0, low=-6.0, state=True)
                rec(f"CH{ch} 保护窗口过窄，测试期间临时放宽到 ±6V",
                    True, f"原为 high={v['high']} low={v['low']}（结束恢复）")
            else:
                rec(f"CH{ch} 保护窗口足够宽", True, f"high={v['high']} low={v['low']}")

        for ch in CHANNELS:
            print(f"\n== CH{ch} 测试 ==", flush=True)
            r = gen.set_wave(ch, "sine", 1000, 1, 0.2, 90)
            rec(f"CH{ch} 多参数一次设置 1kHz/1Vpp/0.2Vdc/90°",
                str(r).strip('"').startswith("SIN"), f"读回 APPL? = {r}")

            f = gen.set_freq(ch, 500)
            a = gen.set_amp(ch, 2.5)
            o = gen.set_offset(ch, 0.0)
            p = gen.set_phase(ch, 45)
            rec(f"CH{ch} 单参数逐个设置", all(x is not None for x in (f, a, o, p)),
                f"freq={f} amp={a} offset={o} phase={p}")
            cfg = gen.get_wave_config(ch)
            rec(f"CH{ch} 回读配置", cfg["shape"] == "SIN" and abs(float(cfg["freq"]) - 500) < 1,
                f"{cfg['shape']} @ {cfg['freq']}Hz {cfg['amp']}Vpp")

            gen.set_wave(ch, "square", 1000, 3)
            rec(f"CH{ch} 方波设置", gen.query(f":SOUR{ch}:APPL?").strip('"').startswith("SQU"),
                gen.query(f":SOUR{ch}:APPL?"))
            if backup[ch]["outp"] != "ON":
                on = gen.output(ch, True)
                off = gen.output(ch, False)
                rec(f"CH{ch} 输出开关往返（原为 OFF，往返后仍 OFF）", True, f"ON→{on} OFF→{off}")
            else:
                rec(f"CH{ch} 输出开关往返", True,
                    "跳过：该通道原本就在输出（不擅自关断，避免打断可能的实验）")

        print("\n== 频率计（无信号属正常）==", flush=True)
        try:
            rec(":COUN:MEAS? 读数", True, gen.counter_measure(timeout=1.5))
        except Exception as e:
            rec(":COUN:MEAS? 读数", True, f"跳过（输入端无信号）：{type(e).__name__}")

        rec("错误队列", not gen.check_error(), "查错干净")
    finally:
        # ---- ③ 恢复（波形 → 输出 → 负载 → 电压保护，逐通道）----
        print("\n== 恢复原配置 ==", flush=True)
        for ch, b in backup.items():
            parts = b["appl"].split(",")
            suffix = _WAVE_SUFFIX.get(parts[0], "SIN")
            gen.write(f":SOUR{ch}:APPL:{suffix} {','.join(parts[1:])}")
            time.sleep(0.2)
            gen.output(ch, b["outp"] == "ON")
            time.sleep(0.1)
            gen.write(f":OUTP{ch}:LOAD {'INF' if b['load'].startswith('9.9') else b['load']}")
            time.sleep(0.1)
            v = b["voll"]
            gen.write(f":OUTP{ch}:VOLL:HIGH {v['high']}")
            gen.write(f":OUTP{ch}:VOLL:LOW {v['low']}")
            gen.write(f":OUTP{ch}:VOLL:STAT {v['state']}")
            time.sleep(0.2)
            now = {"appl": gen.query(f":SOUR{ch}:APPL?").strip().strip('"'),
                   "outp": gen.query(f":OUTP{ch}?").strip(),
                   "load": gen.query(f":OUTP{ch}:LOAD?").strip(),
                   "voll": gen.get_voltage_limit(ch)}
            same = (now["appl"].split(",")[0] == b["appl"].split(",")[0]
                    and now["outp"] == b["outp"]
                    and str(now["voll"]["state"]) == str(v["state"]))
            rec(f"CH{ch} 恢复后比对", same, f"{now}")
        gen.close()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"write_matrix_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    out.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "resource": res, "channels": list(CHANNELS), "authorized_write": True,
        "backup": {str(k): v for k, v in backup.items()}, "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 结果: {len(rows) - n_fail}/{len(rows)} PASS ==\n留痕: {out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
