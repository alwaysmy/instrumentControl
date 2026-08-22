"""设备发现：薄壳转发 common 统一发现引擎（USB/LAN + fallback 可开关）。

运行环境要求：sys.path 需含项目根目录（以便 import common）。
"""
from __future__ import annotations

from typing import Optional

from common.discovery import (  # noqa: F401  (re-export)
    FindResult,
    find_device,
    identify,
    list_resources,
    scan,
)


def find_dh1766(
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    cidr: Optional[str] = None,
    allow_scan: bool = False,
    proto: str = "inst0",
    timeout_ms: int = 3000,
) -> str:
    """发现 *IDN? 含 'DH1766' 的设备，返回资源地址；未找到抛 RuntimeError。

    查找链：显式 resource → 显式 hosts(TCPIP) → 已有 VISA 资源列表 →
    CIDR 网段扫描（仅 allow_scan=True 时作为最后手段）。
    显式指定在线但 IDN 不匹配时抛 ValueError（拒绝静默换设备）。
    """
    hit = find_device(
        "DH1766",
        resource=resource,
        hosts=hosts,
        proto=proto,
        allow_scan=allow_scan,
        cidr=cidr,
        timeout_ms=timeout_ms,
    )
    return hit.resource
