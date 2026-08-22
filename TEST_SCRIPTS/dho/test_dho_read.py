"""DHO 系列示波器实测脚本（只读快照 + 波形读取演示）。

用法：
    python TEST_SCRIPTS/dho/test_dho_read.py [resource] [--host IP] [--allow-scan]
        --wave            读取 CH1 屏幕波形并保存 CSV（默认关闭）
        --full            全量 snapshot（含通道配置查询）

安全约定：
    - 默认仅 *IDN? 与触发状态查询；
    - 设备被他人占用时请勿运行 --wave/--full（会切换 WAVeform 配置）。
输出：TEST_DATA/dho/ 下带时间戳的 JSON 留痕。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dho_control import DHO, find_dho  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dho"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("resource", nargs="?", default=None)
    p.add_argument("--host", action="append")
    p.add_argument("--cidr", default=None)
    p.add_argument("--allow-scan", action="store_true")
    p.add_argument("--wave", action="store_true", help="读取 CH1 屏幕波形存 CSV")
    p.add_argument("--full", action="store_true", help="全量只读快照")
    args = p.parse_args()

    resource = (
        args.resource
        or find_dho(hosts=args.host, allow_scan=args.allow_scan, cidr=args.cidr)
    )
    print(f"== 连接 {resource} ==")

    record: dict = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "resource": resource,
    }
    with DHO(resource) as scope:
        print(f"IDN : {scope.idn()}")
        print(f"触发状态: {scope.trigger_status()}")
        record["idn"] = scope.idn()
        record["trigger_status"] = scope.trigger_status()

        if args.full:
            snap = scope.snapshot()
            for k, v in snap.items():
                print(f"{k}: {v}")
            record["snapshot"] = snap

        if args.wave:
            wf = scope.get_waveform(1, mode="NORMal", fmt="BYTE", points=1000)
            print(
                f"波形: {wf['points']} 点, xinc={wf['xinc']:.3e}s, "
                f"v范围 [{min(wf['v']):.3f}, {max(wf['v']):.3f}] V"
            )
            out_dir = OUT_DIR
            out_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = out_dir / f"dho_ch1_wave_{stamp}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["time_s", "voltage_v"])
                w.writerows(zip(wf["t"], wf["v"]))
            print(f"波形 CSV: {csv_path}")
            record["wave"] = {
                "points": wf["points"],
                "xinc_s": wf["xinc"],
                "v_min": min(wf["v"]),
                "v_max": max(wf["v"]),
                "csv": str(csv_path),
            }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUT_DIR / f"dho_read_{stamp}.json"
    out_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"留痕已保存: {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
