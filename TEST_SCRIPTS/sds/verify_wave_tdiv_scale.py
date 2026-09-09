"""TDIV 缩放实验：验证读取的数据是否为屏幕波形（interval 是否可信）。

原理：改 TDIV 使屏幕时间窗按比例变化，若读出的周期数同步变化 → 读的是屏幕
      波形且 interval 正确；若周期数不变 → 读的是固定内存片段。

安全：记录原 TDIV，测后恢复；只读数据不做其他改动。
输出：TEST_DATA/sds/wave_tdiv_scale_<时间戳>.json
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
from sds_control.commands import PREAMBLE_OFFSETS

OUT = ROOT / "TEST_DATA" / "sds"
OUT.mkdir(parents=True, exist_ok=True)
RES = "TCPIP0::192.168.31.220::inst0::INSTR"

log: dict = {"steps": []}


def rec(name, **kw):
    log["steps"].append({"name": name, **kw})
    print(f"[{name}] " + " ".join(f"{k}={v}" for k, v in kw.items()), flush=True)


def preamble(s):
    raw = s.query_raw(":WAVeform:PREamble?")
    i = raw.find(b"#")
    nd = int(raw[i + 1: i + 2])
    ln = int(raw[i + 2: i + 2 + nd])
    body = raw[i + 2 + nd: i + 2 + nd + ln]
    out = {}
    for key, (off, fmt) in PREAMBLE_OFFSETS.items():
        size = {"h": 2, "i": 4, "f": 4, "d": 8}[fmt]
        out[key] = struct.unpack("<" + fmt, body[off: off + size])[0]
    return out


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s = SDS(RES, timeout_ms=30000)
    s.connect()
    orig_tdiv = None
    try:
        orig_tdiv = s.query("TDIV?").strip()
        rec("原TDIV", value=orig_tdiv)
        rec("idn", value=s.idn()[:50])
        # 信号确认
        dev_freq = s.measure_simple("FREQ", "C2", timeout_s=8.0)
        dev_vpp = s.measure_simple("PKPK", "C2", timeout_s=8.0)
        rec("C2信号", freq=f"{dev_freq:.1f}Hz", vpp=f"{dev_vpp:.4f}V")

        results = []
        for tdiv in ("5.00E-06", "5.00E-05", "5.00E-04"):
            s.write(f"TDIV {tdiv}")
            time.sleep(1.5)
            acq_poin = s.query("ACQ:POIN?").strip()
            srat = s.query("ACQ:SRAT?").strip()
            tdiv_actual = s.query("TDIV?").strip()
            s.write(":WAVeform:SOURce C2")
            s.write("WAV:WIDT WORD")
            s.write(f"WAV:POIN {int(float(acq_poin))}")
            s.write("WAV:STAR 0")
            time.sleep(0.5)
            pre = preamble(s)
            data = s.query_raw("WAV:DATA?")
            i = data.find(b"#")
            nd = int(data[i + 1: i + 2])
            ln = int(data[i + 2: i + 2 + nd])
            blob = data[i + 2 + nd: i + 2 + nd + ln]
            codes = struct.unpack(f"<{len(blob)//2}h", blob)
            up = sum(1 for k in range(1, len(codes)) if codes[k-1] < 0 <= codes[k])
            span_by_freq = up / dev_freq if dev_freq > 0 else None
            item = {
                "tdiv_set": tdiv,
                "tdiv_actual": tdiv_actual,
                "acq_poin": acq_poin,
                "acq_srat": srat,
                "pre_point_num": pre["point_num"],
                "pre_interval": pre["interval"],
                "pre_tdiv_idx": pre["tdiv"],
                "got_points": len(codes),
                "up_crossings": up,
                "span_by_freq_s": span_by_freq,
                "screen_span_expected_s": float(tdiv_actual.rstrip("S")) * 10,
                "interval_by_freq_s": (span_by_freq / len(codes)
                                       if span_by_freq else None),
            }
            results.append(item)
            rec(f"TDIV={tdiv}", **{k: (f"{v:.6g}" if isinstance(v, float) else v)
                                  for k, v in item.items() if k != "tdiv_set"})
            time.sleep(0.3)
        log["results"] = results
    finally:
        if orig_tdiv:
            s.write(f"TDIV {orig_tdiv}")
            time.sleep(0.8)
            rec("恢复TDIV", value=s.query("TDIV?").strip())
        s.close()

    out = OUT / f"wave_tdiv_scale_{stamp}.json"
    out.write_text(json.dumps(log, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    print(f"\n留痕: {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
