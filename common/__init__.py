"""instrumentControl 通用层：VISA 客户端与统一设备发现（多设备共用）。

用法：
    from common import find_device, FindResult

    hit = find_device("DH1766", hosts=["192.168.1.100"])          # 显式 LAN
    hit = find_device("DH1766", allow_scan=True, cidr="192.168.1.0/24")  # 最后手段
"""
from .discovery import (
    FindResult,
    detect_cidr,
    find_device,
    identify,
    list_resources,
    scan,
    scan_cidr,
    tcpip_resource,
)
from .visa_client import VisaClient

__all__ = [
    "FindResult",
    "VisaClient",
    "detect_cidr",
    "find_device",
    "identify",
    "list_resources",
    "scan",
    "scan_cidr",
    "tcpip_resource",
]
