"""LAN 设备端口诊断：对指定 IP 扫描常用仪器端口并尝试 *IDN?。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/diag_lan_ports.py <ip> [<ip> ...]

输出：控制台 + TEST_DATA/common/port_diag_<时间戳>.json
"""
from __future__ import annotations

import json
import socket
import sys
from datetime import datetime
from pathlib import Path

import pyvisa

OUT_DIR = Path(__file__).resolve().parents[2] / "TEST_DATA" / "common"

# 常用仪器端口：VXI-11 portmapper / HiSLIP / 各厂商 SCPI raw / Web
PORTS = (111, 4880, 5025, 5555, 1234, 10001, 1024, 80, 443)


def scan_ports(ip: str, timeout_s: float = 0.8) -> list[int]:
    open_ports = []
    for port in PORTS:
        try:
            with socket.create_connection((ip, port), timeout=timeout_s):
                open_ports.append(port)
        except OSError:
            continue
    return open_ports


def try_idn(rm: pyvisa.ResourceManager, ip: str, port: int) -> list[str]:
    results = []
    variants = [
        (f"TCPIP0::{ip}::{port}::SOCKET", {"read_termination": "\n", "write_termination": "\n"}),
        (f"TCPIP0::{ip}::{port}::SOCKET", {}),
        (f"TCPIP0::{ip}::inst0::INSTR", {}),
        (f"TCPIP0::{ip}::hislip0::INSTR", {"read_termination": "\n"}),
    ] if port != 111 else [
        (f"TCPIP0::{ip}::inst0::INSTR", {}),
    ]
    for res, kw in variants:
        try:
            inst = rm.open_resource(res, open_timeout=3000, **kw)
            inst.timeout = 2500
            try:
                idn = inst.query("*IDN?").strip()
                if idn:
                    results.append(f"port{port}: {res} ({kw or 'no-term'}) -> {idn}")
                    break
            finally:
                inst.close()
        except Exception as e:
            results.append(f"port{port}: {res} FAIL {type(e).__name__}")
    return results


def main() -> None:
    ips = sys.argv[1:] or ["192.168.31.146"]
    out: dict = {"timestamp": datetime.now().isoformat(timespec="seconds"), "hosts": {}}
    rm = pyvisa.ResourceManager()
    for ip in ips:
        entry = {"open_ports": [], "idn_attempts": []}
        print(f"== {ip} ==")
        ports = scan_ports(ip)
        entry["open_ports"] = ports
        print(f"  开放端口: {ports or '无'}")
        for port in ports:
            if port in (80, 443):
                continue  # Web 口不发 SCPI
            for line in try_idn(rm, ip, port):
                entry["idn_attempts"].append(line)
                print(f"  {line}")
        out["hosts"][ip] = entry

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"port_diag_{stamp}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n留痕已保存: {f}")


if __name__ == "__main__":
    main()
