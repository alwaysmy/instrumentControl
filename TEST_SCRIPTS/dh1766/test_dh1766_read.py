"""DH1766A 实测脚本：识别设备 + 读电压电流 + 开关通道演示。

用法：
    python TEST_SCRIPTS/dh1766/test_dh1766_read.py [VISA资源地址]

不带参数时自动扫描并选取 *IDN? 含 "DH1766" 的设备。

安全约定：
    - 只对 CH1 做开关演示（当前实测三路全关、空载），开 1 秒后关闭，恢复原状态；
    - 若 CH1 原本就是开着的，只读不操作。
输出：TEST_DATA/dh1766/ 下带时间戳的 JSON 留痕文件。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from dh1766_control import DH1766, find_dh1766  # noqa: E402
from dh1766_control.visa import VisaClient  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dh1766"


def main() -> None:
    resource = sys.argv[1] if len(sys.argv) > 1 else find_dh1766()
    print(f"\n== 连接 {resource} ==")

    with VisaClient(resource, timeout_ms=5000) as client:
        ps = DH1766(client)
        print(f"IDN : {ps.idn()}")

        # ---- 只读：电压/电流/设定值/状态 ----
        print("\n-- 回读（只读）--")
        print(f"输出电压 V : {ps.measure_voltage_all()}")
        print(f"输出电流 A : {ps.measure_current_all()}")
        print(f"设定电压 V : {ps.get_voltage_set()}")
        print(f"设定电流 A : {ps.get_current_set()}")
        states = ps.get_output_state()
        print(f"输出状态   : {['ON' if s else 'OFF' for s in states]}")

        # ---- 开关通道演示：CH1 开 1 秒后关，恢复原状态 ----
        print("\n-- 开关通道演示（CH1，1 秒）--")
        was_on = states[0]
        ps.set_output(1, True)
        time.sleep(0.5)
        print(f"CH1 开启后状态: {ps.get_output_state()}  电压: {ps.measure_voltage_all()}")
        if was_on:
            print("CH1 原本开启，按原状态保持开启")
        else:
            time.sleep(1.0)
            ps.set_output(1, False)
            time.sleep(0.5)
            print(f"CH1 关闭后状态: {ps.get_output_state()}  电压: {ps.measure_voltage_all()}")

        # ---- 留痕 ----
        out_dir = OUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "resource": resource,
            "snapshot": ps.snapshot(),
            "ch1_demo": {"was_on": was_on, "opened": True, "closed": not was_on},
        }
        out_file = out_dir / f"dh1766_{stamp}.json"
        out_file.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n留痕已保存: {out_file}")


if __name__ == "__main__":
    main()
