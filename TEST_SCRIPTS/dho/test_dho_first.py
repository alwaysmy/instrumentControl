"""dho_control 首次实机验证：只读冒烟 -> snapshot -> 波形读取（分阶段留痕）。"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dho_control import DHO, find_dho  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dho"
OUT_DIR.mkdir(parents=True, exist_ok=True)
results = []


def rec(name, ok, detail=""):
    results.append({"item": name, "ok": ok, "detail": str(detail)[:300]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    resource = find_dho(hosts=["192.168.31.146"])
    print(f"连接: {resource}")
    with DHO(resource) as scope:
        idn = scope.idn()
        rec("*IDN?", bool(idn), idn)
        print(f"版本: {scope.version()}")
        print("错误队列:", scope.system_error() or "干净")

        # 只读快照
        try:
            snap = scope.snapshot()
            for k, v in snap.items():
                print(f"  {k}: {v}")
            rec("snapshot()", True)
        except Exception as e:
            rec("snapshot()", False, f"{type(e).__name__}: {e}")
            snap = {}

        # 波形读取（会临时改 WAVeform 配置，属采集类无面板副作用）
        try:
            t0 = time.monotonic()
            wf = scope.get_waveform(1, mode="NORMal", fmt="BYTE", points=1000)
            dt = time.monotonic() - t0
            vs = wf["v"]
            rec(
                "get_waveform CH1",
                wf["points"] > 0,
                f"{wf['points']}点 {dt:.1f}s V范围[{min(vs):.4f},{max(vs):.4f}]V "
                f"xinc={wf['xinc']:.3e}",
            )
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv = OUT_DIR / f"dho_ch1_wave_{stamp}.csv"
            import csv as csvmod

            with open(csv, "w", newline="", encoding="utf-8") as fh:
                w = csvmod.writer(fh)
                w.writerow(["time_s", "voltage_v"])
                w.writerows(zip(wf["t"], wf["v"]))
            print(f"  波形 CSV: {csv}")
        except Exception as e:
            rec("get_waveform CH1", False, f"{type(e).__name__}: {e}")

        print("错误队列终态:", scope.system_error() or "干净")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"dho_first_verify_{stamp}.json"
    f.write_text(
        json.dumps({"timestamp": stamp, "resource": resource, "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    n_fail = sum(1 for r in results if not r["ok"])
    print(f"\n== 结果: {len(results) - n_fail}/{len(results)} PASS ==")
    print(f"留痕: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
