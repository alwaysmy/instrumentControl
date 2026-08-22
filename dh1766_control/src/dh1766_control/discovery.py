"""设备发现：VISA 资源枚举与 *IDN? 识别。"""
from __future__ import annotations

from typing import Optional

import pyvisa


def list_resources() -> list[str]:
    """列出本机所有 VISA 资源（USB/串口/LAN...）。"""
    rm = pyvisa.ResourceManager()
    try:
        return list(rm.list_resources())
    finally:
        rm.close()


def identify(resource: str, timeout_ms: int = 3000) -> Optional[str]:
    """对单个资源发送 *IDN?，成功返回识别串，失败返回 None。"""
    try:
        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(resource)
        inst.timeout = timeout_ms
        try:
            return inst.query("*IDN?").strip()
        finally:
            inst.close()
            rm.close()
    except Exception:
        return None


def scan() -> dict[str, Optional[str]]:
    """扫描全部资源，返回 {resource: idn}，无法识别的设备为 None。"""
    result: dict[str, Optional[str]] = {}
    for res in list_resources():
        result[res] = identify(res)
    return result


def find_dh1766() -> str:
    """扫描并返回 *IDN? 含 'DH1766' 的资源地址，未找到抛 RuntimeError。"""
    for res, idn in scan().items():
        if idn and "DH1766" in idn:
            return res
    raise RuntimeError("未找到 DH1766 设备（请检查 USB 连接与 VISA 驱动）")
