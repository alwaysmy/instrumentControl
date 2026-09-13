"""DH1766A LAN 只读探测脚本（傅师傅指示：只读取，不设置任何参数）。

用法：
    python TEST_SCRIPTS/dh1766/test_dh1766_readonly_lan.py [IP]
    不传 IP 时走 common.resolver 解析（不写死 IP，换网段/换口自适应）。

连接形态（实测确认）：
    - DH1766A LAN 为 SCPI-over-TCP，端口 5025（手册 §3.10/§9；实测 OPEN）；
    - NI-VISA 打不开 SOCKET 资源（RSRC_NFOUND），改用 pyvisa-py 后端 '@py'；
    - 本脚本子类化 VisaClient 仅替换 ResourceManager 后端，不改动库文件
      （待傅师傅完善 instrumentControl 接口后可原生支持）。

安全约定：
    - 仅调用查询类方法：*IDN? / MEAS:VOLT? / MEAS:CURR? / MEAS:POWR? /
      设定值回读 / 输出状态回读；
    - 不发送任何写命令（无 clear/beep/output/set_*）。

留痕：TEST_DATA/dh1766/dh1766_readonly_<时间戳>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pyvisa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from common.resolver import resolve  # noqa: E402
from dh1766_control import DH1766  # noqa: E402
from dh1766_control.visa import VisaClient  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dh1766"
DEFAULT_IP = None  # 默认走 common.resolver 解析（不写死 IP，换网段/换口自适应）
PORT = 5025


class PyVisaClient(VisaClient):
    """VisaClient 的 pyvisa-py 后端变体（仅替换 ResourceManager('@py')）。"""

    def __init__(self, resource: str, timeout_ms: int = 5000, **kw):
        self.resource = resource
        self.rm = pyvisa.ResourceManager("@py")
        self.inst = self.rm.open_resource(resource)
        self.inst.timeout = timeout_ms
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"
        self.inst.chunk_size = 4096


def main() -> None:
    ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IP
    resource = f"TCPIP0::{ip}::{PORT}::SOCKET" if ip else resolve("psu")
    print(f"\n== 连接 {resource} ==")

    with PyVisaClient(resource, timeout_ms=3000) as client:
        ps = DH1766(client)
        idn = ps.idn()
        print(f"IDN : {idn}")

        print("\n-- 只读回读 --")
        volts = ps.measure_voltage_all()
        currs = ps.measure_current_all()
        powers = ps.measure_power_all()
        vset = [ps.get_voltage(ch) for ch in (1, 2, 3)]
        iset = [ps.get_current(ch) for ch in (1, 2, 3)]
        states = ps.get_output_state()

        for ch in (1, 2, 3):
            i = ch - 1
            print(
                f"CH{ch}: V={volts[i]:+.4f} V  I={currs[i]:+.4f} A  "
                f"P={powers[i]:+.4f} W | 设定 V={vset[i]:.3f} I={iset[i]:.3f} | "
                f"输出={'ON' if states[i] else 'OFF'}"
            )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "resource": resource,
            "readonly": True,
            "idn": idn,
            "channels": {
                f"CH{ch}": {
                    "meas_v": volts[ch - 1],
                    "meas_i": currs[ch - 1],
                    "meas_p": powers[ch - 1],
                    "set_v": vset[ch - 1],
                    "set_i": iset[ch - 1],
                    "output_on": states[ch - 1],
                }
                for ch in (1, 2, 3)
            },
        }
        out_file = OUT_DIR / f"dh1766_readonly_{stamp}.json"
        out_file.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n留痕已保存: {out_file}")


if __name__ == "__main__":
    main()
