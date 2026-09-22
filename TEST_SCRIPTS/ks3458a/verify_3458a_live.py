"""ks3458a 真机验收（只读 + 同值 config）：Keysight VISA 通路 / 状态回读 / 单次与多次读数。

为什么单独有真机脚本：`verify_3458a_offline.py` 用假 transport 覆盖协议与边界；
本脚本在真机上验证"通路 + 指令 + 回读"确实可用（2026-09-23 首次跑通）。

**不测**：`read_burst`（改设备配置为数字档）、`configure_acv`（切交流）、`reset`
（破坏性）——这三项需要显式授权后单独跑，见 docs/3458a_integration_*.md。

用法：
    python TEST_SCRIPTS/ks3458a/verify_3458a_live.py [resource]
    （缺省 GPIB0::9::INSTR；本机必须已装 Keysight IO Libraries + 82357B）
留痕：TEST_DATA/ks3458a/verify_3458a_live_<stamp>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from keysight_3458a import DMM3458A  # noqa: E402
from keysight_3458a.transport import keysight_visa_core  # noqa: E402

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="ascii", errors="replace")
    except Exception:
        pass

RESOURCE = sys.argv[1] if len(sys.argv) > 1 else "GPIB0::9::INSTR"
rows: list[dict] = []


def rec(name: str, ok: bool, detail=""):
    rows.append({"item": name, "ok": bool(ok), "detail": str(detail)[:220]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:46s} {str(detail)[:90]}", flush=True)


def main() -> int:
    print(f"resource      : {RESOURCE}")
    print(f"Keysight VISA : {keysight_visa_core()}")
    d = DMM3458A(RESOURCE, timeout_s=20.0)
    try:
        t0 = time.time()
        res = d.connect()
        rec("connect + recover + prepare", True, f"{res} ({time.time()-t0:.1f}s)")
    except Exception as e:
        rec("connect", False, f"{type(e).__name__}: {e}")
        return finish()

    try:
        idn = d.idn()
        rec("ID? (3458A 无 *IDN?)", "3458" in idn.upper(), repr(idn))
        st = d.state()
        rec("state() 设备回读", st.get("id") is not None and st.get("nplc") is not None,
            f"id={st.get('id')!r} func={st.get('function')!r} range={st.get('range_v')} "
            f"nplc={st.get('nplc')} trig={st.get('trig')} inbuf={st.get('inbuf')}")
        rec("TEMP? 内部温度", st.get("temperature_c") is not None,
            f"{st.get('temperature_c')} C")
        rec("ERRSTR? 队列", str(st.get("error", "")).startswith("0,"), repr(st.get("error")))

        t0 = time.time()
        v1 = d.read_dcv()
        rec("read_dcv() 单次", isinstance(v1, float), f"{v1:.9e} V ({time.time()-t0:.2f}s)")

        t0 = time.time()
        avg = d.read_avg(3)
        rec("read_avg(3)", isinstance(avg, float), f"{avg:.9e} V ({time.time()-t0:.2f}s)")

        t0 = time.time()
        s3 = d.read_stats(3)
        rec("read_stats(3)", s3.get("n") == 3,
            f"mean={s3.get('mean'):.9e} sd={s3.get('stddev'):.2e} "
            f"min/max={s3.get('min'):.9e}/{s3.get('max'):.9e} ({time.time()-t0:.2f}s)")
        rec("读数一致性（同档同积分时间）", abs(avg - v1) < max(1e-3, abs(v1) * 0.5),
            f"|avg-v1|={abs(avg-v1):.3e}")
    finally:
        d.close()
    return finish()


def finish() -> int:
    out_dir = ROOT / "TEST_DATA" / "ks3458a"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = out_dir / f"verify_3458a_live_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    f.write_text(json.dumps({
        "when": datetime.now().isoformat(timespec="seconds"),
        "resource": RESOURCE,
        "keysight_visa_core": keysight_visa_core(),
        "note": "只读 + 同值 config；未做 RESET / burst / ACV",
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== result: {len(rows) - n_fail}/{len(rows)} PASS ==\nevidence: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
