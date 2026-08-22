"""dh1766_control — 北京大华 DH1766 系列三路可编程直流电源控制库。

用法：
    from dh1766_control import DH1766, VisaClient, find_dh1766

    with VisaClient(find_dh1766()) as client:
        ps = DH1766(client)
        print(ps.idn())
        print(ps.measure_voltage_all())

安全模式（接入负载后）：
    ps = DH1766(client, safe_mode=True)   # 输出ON的通道拒绝修改设定
"""
from .dh1766 import DH1766
from .discovery import find_dh1766, identify, list_resources, scan
from .visa import VisaClient

__all__ = [
    "DH1766",
    "VisaClient",
    "find_dh1766",
    "identify",
    "list_resources",
    "scan",
]

__version__ = "0.1.0"
