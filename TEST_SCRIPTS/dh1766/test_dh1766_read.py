"""DH1766A 实测脚本：识别设备 + 读电压电流 + 开关通道演示。

用法：
    python TEST_SCRIPTS/dh1766/test_dh1766_read.py [resource] [options]

接口指定与 fallback（common 统一发现层）：
    resource            完整 VISA 资源串（USB/TCPIP 均可），最高优先
    --host IP           TCPIP host/IP，可多次（自动选协议：VXI-11/HiSLIP/raw5025）
    --cidr CIDR         fallback 网段，如 192.168.1.0/24（配合 --allow-scan）
    --allow-scan        显式全部失败后允许网段扫描（最后手段）
不带参数时扫描本机已有 VISA 资源并匹配 *IDN? 含 DH1766 的设备（原行为）。

安全约定：
    - 只对 CH1 做开关演示（当前实测三路全关、空载），开 1 秒后关闭，恢复原状态；
    - 若 CH1 原本就是开着的，只读不操作；
    - **try/finally 兜底**：任何异常/中断路径都会把关断动作执行完（铁律）；
    - 任一通道带电（设备疑似在使用/接负载）时默认**跳过**演示，
      确认安全后加 `--force-switch-demo` 强制执行。
输出：TEST_DATA/dh1766/ 下带时间戳的 JSON 留痕文件。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from common.discovery import find_device  # noqa: E402
from dh1766_control import DH1766  # noqa: E402
from dh1766_control.visa import VisaClient  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dh1766"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DH1766A 识别+读取+开关演示")
    p.add_argument("resource", nargs="?", default=None, help="完整 VISA 资源串（最高优先）")
    p.add_argument("--host", action="append", help="TCPIP host/IP，可多次（自动选协议）")
    p.add_argument("--cidr", default=None, help="fallback 扫描网段")
    p.add_argument("--allow-scan", action="store_true", help="允许最后手段网段扫描")
    p.add_argument("--force-switch-demo", action="store_true",
                   help="已有通道带电时仍强制执行 CH1 开关演示（默认跳过）")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    hit = find_device(
        "DH1766",
        resource=args.resource,
        hosts=args.host,
        allow_scan=args.allow_scan,
        cidr=args.cidr,
    )
    resource = hit.resource
    print(f"\n== 连接 {resource} (source={hit.source}) ==")

    with VisaClient(resource, timeout_ms=5000) as client:
        ps = DH1766(client)
        print(f"IDN : {ps.idn()}")

        # ---- 只读：电压/电流/设定值/状态 ----
        print("\n-- 回读（只读）--")
        print(f"输出电压 V : {ps.measure_voltage_all()}")
        print(f"输出电流 A : {ps.measure_current_all()}")
        print(f"设定电压 V : {ps.apply_voltage()}")
        print(f"设定电流 A : {ps.apply_current()}")
        states = ps.get_output_state()
        print(f"输出状态   : {['ON' if s else 'OFF' for s in states]}")
        cur_mode = ps.output_mode()
        print(f"输出模式   : {cur_mode}")

        # ---- 开关通道演示：CH1 开 1 秒后关，恢复原状态 ----
        # 安全：① try/finally 保证任何异常/中断路径都恢复进入时的输出状态
        #       （AGENTS.md 铁律"测试脚本必须 try/finally 恢复被改设定并关闭输出"）；
        #       ② 任一通道已带电（疑似设备在用/接负载）默认跳过演示，
        #       确认安全后用 --force-switch-demo 强制执行。
        print("\n-- 开关通道演示（CH1，1 秒）--")
        was_on = states[0]
        if any(states) and not args.force_switch_demo:
            print("  跳过：已有通道带电（{}），疑似设备在使用/接负载；"
                  "确认安全后加 --force-switch-demo 强制执行".format(
                      ["ON" if s else "OFF" for s in states]))
            demo = {"skipped": True, "reason": "channel_energized", "states": states}
        else:
            demo = {"was_on": was_on, "opened": True, "closed": not was_on}
            try:
                ps.set_output(1, True, cur_mode)
                time.sleep(0.5)
                print(f"CH1 开启后状态: {ps.get_output_state()}  电压: {ps.measure_voltage_all()}")
                if was_on:
                    print("CH1 原本开启，按原状态保持开启")
                else:
                    time.sleep(1.0)
            finally:
                if not was_on:
                    try:
                        ps.set_output(1, False, cur_mode)
                        time.sleep(0.5)
                        print(f"CH1 关闭后状态: {ps.get_output_state()}  电压: {ps.measure_voltage_all()}")
                    except Exception as e:  # 恢复失败必须显式告警，不能静默
                        demo["restore_error"] = f"{type(e).__name__}: {e}"
                        print(f"!! 恢复 CH1 关闭失败: {demo['restore_error']}")

        # ---- 留痕 ----
        out_dir = OUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "resource": resource,
            "discovery": {"source": hit.source, "idn": hit.idn},
            "snapshot": ps.snapshot(),
            "ch1_demo": demo,
        }
        out_file = out_dir / f"dh1766_{stamp}.json"
        out_file.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n留痕已保存: {out_file}")


if __name__ == "__main__":
    main()
