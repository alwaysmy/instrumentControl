"""SDS 波形时间轴受控验证（设备空闲）。

流程：确认信号 → STOP 冻结 → 读全部参数 → 读多组点数数据 → 交叉验证 interval
      → 恢复 RUN。

判定：用设备测量的 FREQ 反推真实 interval，与 PREamble/ACQ:SRAT? 对比。
输出：TEST_DATA/sds/wave_timebase_verify_<时间戳>.json
"""
from __future__ import annotations

import json
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sds_control import SDS
from sds_control.commands import PREAMBLE_OFFSETS, TDIV_ENUM

OUT = ROOT / "TEST_DATA" / "sds"
OUT.mkdir(parents=True, exist_ok=True)
RES = "TCPIP0::192.168.31.220::inst0::INSTR"

log: dict = {"steps": []}


def rec(name, **kw):
    log["steps"].append({"name": name, **kw})
    print(f"[{name}] " + " ".join(f"{k}={v}" for k, v in kw.items()), flush=True)


def read_preamble(s: SDS) -> dict:
    raw = s.query_raw("WAV:PRE?")
    i = raw.find(b"#")
    nd = int(raw[i + 1: i + 2])
    ln = int(raw[i + 2: i + 2 + nd])
    body = raw[i + 2 + nd: i + 2 + nd + ln]
    out = {}
    for key, (off, fmt) in PREAMBLE_OFFSETS.items():
        size = {"h": 2, "i": 4, "f": 4, "d": 8}[fmt]
        out[key] = struct.unpack("<" + fmt, body[off: off + size])[0]
    return out


def read_wave(s: SDS, points: int, width: str = "WORD"):
    s.write(f"WAV:WIDT {width}")
    s.write(f"WAV:POIN {points}")
    s.write("WAV:STAR 0")
    time.sleep(0.4)
    pre = read_preamble(s)
    data = s.query_raw("WAV:DATA?")
    i = data.find(b"#")
    nd = int(data[i + 1: i + 2])
    ln = int(data[i + 2: i + 2 + nd])
    blob = data[i + 2 + nd: i + 2 + nd + ln]
    codes = (struct.unpack(f"<{len(blob)//2}h", blob) if width == "WORD"
             else struct.unpack(f"<{len(blob)}b", blob))
    return pre, codes


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log["timestamp"] = stamp
    s = SDS(RES, timeout_ms=30000)
    s.connect()
    orig_trig_status = None
    try:
        # ---- 1. 确认信号与初始状态 ----
        rec("idn", value=s.idn()[:60])
        orig_trig_status = s.query(":TRIGger:STATus?").strip()
        rec("初始触发状态", value=orig_trig_status)
        for ch in ("C1", "C2"):
            try:
                vpp = s.measure_simple("PKPK", ch, timeout_s=6.0)
                freq = s.measure_simple("FREQ", ch, timeout_s=6.0)
                rec(f"{ch}信号", vpp=f"{vpp:.4f}V", freq=f"{freq:.1f}Hz")
            except Exception as e:
                rec(f"{ch}信号", error=type(e).__name__)

        # 选一个有信号的通道
        target = None
        for ch in ("C2", "C1"):
            try:
                f = s.measure_simple("FREQ", ch, timeout_s=6.0)
                if f > 0:
                    target = ch
                    break
            except Exception:
                pass
        if target is None:
            rec("abort", reason="两通道均无有效频率信号，无法交叉验证")
            return 2
        rec("验证通道", value=target)
        dev_freq = s.measure_simple("FREQ", target, timeout_s=8.0)
        dev_vpp = s.measure_simple("PKPK", target, timeout_s=8.0)
        rec("设备测量", freq=f"{dev_freq:.2f}Hz", vpp=f"{dev_vpp:.4f}V")

        # ---- 2. STOP 冻结 ----
        s.write(":STOP")
        time.sleep(1.0)
        rec("冻结后状态", value=s.query(":TRIGger:STATus?").strip())

        # ---- 3. 读全部参数 ----
        params = {
            "ACQ_SRAT": s.query("ACQ:SRAT?").strip(),
            "ACQ_MDEP": s.query("ACQ:MDEP?").strip(),
            "ACQ_POIN": s.query("ACQ:POIN?").strip(),
            "TDIV": s.query("TDIV?").strip(),
        }
        rec("参数", **params)
        s.write(f":WAVeform:SOURce CHANnel{target[-1]}")
        time.sleep(0.3)
        pre = read_preamble(s)
        rec("PREamble", **{k: (f"{v:.6g}" if isinstance(v, float) else v)
                           for k, v in pre.items()})

        # ---- 4. 多组点数读数据并交叉验证 ----
        srat = float(params["ACQ_SRAT"].rstrip("SAsa/s").replace("E+", "e"))
        # ACQ:SRAT? 返回如 "1.00E+09"，直接 float
        try:
            srat_val = float(params["ACQ_SRAT"])
        except ValueError:
            srat_val = None
        rec("采样率解析", value=srat_val)

        results = []
        for pts in (10000, 20000, 50000, 100000):
            pre_i, codes = read_wave(s, pts)
            up_cross = sum(1 for k in range(1, len(codes))
                           if codes[k - 1] < 0 <= codes[k])
            cycles = up_cross
            if cycles >= 2:
                real_span = cycles / dev_freq
                real_interval = real_span / len(codes)
            else:
                real_span = real_interval = None
            item = {
                "requested_points": pts,
                "got_points": len(codes),
                "pre_point_num": pre_i["point_num"],
                "pre_interval": pre_i["interval"],
                "cycles": cycles,
                "real_span_s": real_span,
                "real_interval_s": real_interval,
                "ratio_pre_vs_real": (pre_i["interval"] / real_interval
                                      if real_interval else None),
                "ratio_srat_vs_real": ((1 / srat_val) / real_interval
                                       if (real_interval and srat_val) else None),
            }
            results.append(item)
            rec(f"读{pts}点", **{k: (f"{v:.6g}" if isinstance(v, float) else v)
                                 for k, v in item.items() if k != "requested_points"})
            time.sleep(0.3)
        log["results"] = results
    finally:
        # ---- 5. 恢复 RUN ----
        try:
            s.write(":RUN")
            time.sleep(0.5)
            rec("恢复RUN", value=s.query(":TRIGger:STATus?").strip())
        except Exception as e:
            rec("恢复RUN失败", error=str(e)[:80])
        s.close()

    out = OUT / f"wave_timebase_verify_{stamp}.json"
    out.write_text(json.dumps(log, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    print(f"\n留痕: {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
