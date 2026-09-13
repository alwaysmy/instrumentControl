"""SDS 远程关机测试：:SYSTem:SHUTdown（手册 237 页确认存在）。

流程：关机前留痕 -> 发送关机命令 -> 轮询端口验证离线 -> 留痕。
注意：关机后需手动开机（设备无网络唤醒验证）。

⚠ 破坏性：设备将离线且必须**人工到现场开机**。故本脚本必须显式传 `--yes`
才执行（与 MCP 工具 `sds_shutdown(confirm=True)` 的门槛对齐）；
不带 `--yes` 只打印提示并退出，不会发出任何命令。

用法：
    python TEST_SCRIPTS/common/test_sds_shutdown.py --yes
"""
import argparse
import json
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sds_control import SDS  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"
HOST = "192.168.31.220"
PORT = 4880  # VXI-11 走 inst0，端口探测用 HiSLIP 口 + RPC 口均可，测 111/4880


def port_open(ip: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="SDS 远程关机测试（破坏性）")
    ap.add_argument("--yes", action="store_true",
                    help="确认执行关机：设备将离线，需人工现场开机")
    args = ap.parse_args()
    if not args.yes:
        print("拒绝执行：这是关机测试（设备离线后必须人工现场开机）。"
              "确认无误请显式加 --yes。")
        return 2

    out = {"timestamp": datetime.now().isoformat(timespec="seconds"), "steps": []}

    scope = SDS(f"TCPIP0::{HOST}::inst0::INSTR")
    scope.connect()
    idn = scope.idn()
    print(f"关机前 IDN: {idn}")
    out["steps"].append({"step": "pre_idn", "value": idn})
    scope.close()

    print("发送 :SYSTem:SHUTdown ...")
    scope2 = SDS(f"TCPIP0::{HOST}::inst0::INSTR")
    scope2.connect()
    try:
        scope2.write(":SYSTem:SHUTdown")
        out["steps"].append({"step": "shutdown_cmd", "sent": True})
    except Exception as e:
        # 设备可能立即断开，write 报错也算发送成功
        out["steps"].append({"step": "shutdown_cmd", "sent": True, "note": str(e)[:100]})
        print(f"  write 异常（可能已断开）: {type(e).__name__}")
    try:
        scope2.close()
    except Exception:
        pass

    print("轮询离线状态（最多 60s）...")
    t0 = time.monotonic()
    offline_at = None
    while time.monotonic() - t0 < 60:
        time.sleep(2)
        alive = port_open(HOST, 111) or port_open(HOST, 4880)
        elapsed = round(time.monotonic() - t0, 1)
        print(f"  {elapsed}s: {'在线' if alive else '离线'}")
        if not alive and offline_at is None:
            offline_at = elapsed
            out["steps"].append({"step": "offline", "after_s": elapsed})
            break
    if offline_at is None:
        out["steps"].append({"step": "offline", "after_s": None})
        print("!! 60s 内未检测到离线——关机命令可能未生效")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"sds_shutdown_test_{stamp}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"留痕: {f}")
    print("关机后需手动开机（SDS 无网络唤醒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
