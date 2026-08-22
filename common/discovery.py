"""VISA 设备统一发现引擎：显式指定 → 已有资源列表 → 网段扫描（fallback 可开关）。

查找链（find_device）：
    层① resource 显式资源串（USB/TCPIP 均可）
    层② hosts 显式 host/IP 列表 → TCPIP0::<host>::<proto>::INSTR
    层③ list_resources 全扫（传统行为）
    层④ CIDR 网段并发扫描
层③④ 仅在未给显式参数、或显式全失败且 allow_scan=True 时执行。

安全语义：
    - 显式指定在线但 *IDN? 不匹配 idn_contains → ValueError（不静默换设备）；
    - 显式指定无响应 → allow_scan=True 才降级下一层；
    - 每层尝试均记录，最终失败 RuntimeError 打印完整链路可回溯。
"""
from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import pyvisa

SCAN_WORKERS = 32
SCAN_TIMEOUT_MS = 1500


@dataclass
class FindResult:
    """发现结果：resource 命中的资源串，idn 为 *IDN? 原文，source 标记命中层。"""

    resource: str
    idn: str
    source: str  # explicit | listed | scanned


def list_resources() -> list[str]:
    """列出本机所有 VISA 资源（USB/串口/LAN...）。"""
    rm = pyvisa.ResourceManager()
    try:
        return list(rm.list_resources())
    finally:
        rm.close()


def identify(resource: str, timeout_ms: int = 3000) -> Optional[str]:
    """对单个资源发送 *IDN?，成功返回识别串，失败/超时返回 None。"""
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
    """扫描全部已有 VISA 资源，返回 {resource: idn}，无法识别的设备为 None。"""
    result: dict[str, Optional[str]] = {}
    for res in list_resources():
        result[res] = identify(res)
    return result


def tcpip_resource(host: str, proto: str = "inst0") -> str:
    """host 或完整资源串规范化为 TCPIP 资源名；已含 '::' 视为完整资源串原样返回。"""
    if "::" in host:
        return host
    return f"TCPIP0::{host}::{proto}::INSTR"


def detect_cidr() -> Optional[str]:
    """经 UDP 路由探测本机出口 IP，返回所在 /24 网段；失败返回 None。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return str(ipaddress.ip_network(f"{ip}/24", strict=False))
    except Exception:
        return None
    finally:
        s.close()


def scan_cidr(
    cidr: str,
    idn_contains: str,
    timeout_ms: int = SCAN_TIMEOUT_MS,
) -> list[FindResult]:
    """并发扫描网段内全部地址，返回所有在线设备的 FindResult（含非目标设备）。

    每个在线设备实时打印留痕（[HIT] 为 IDN 匹配目标）；无响应地址静默跳过。
    """
    net = ipaddress.ip_network(cidr, strict=False)
    addrs = [str(h) for h in net.hosts()]
    print(f"[scan] 网段 {cidr} 共 {len(addrs)} 个地址，workers={SCAN_WORKERS}，单地址超时 {timeout_ms}ms")
    needle = idn_contains.lower()
    hits: list[FindResult] = []
    done = 0
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        futures = {pool.submit(identify, tcpip_resource(a), timeout_ms): a for a in addrs}
        for fut in as_completed(futures):
            done += 1
            addr = futures[fut]
            idn = fut.result()
            if not idn:
                continue
            res = tcpip_resource(addr)
            mark = "HIT" if needle in idn.lower() else "dev"
            print(f"[scan {done}/{len(addrs)}] [{mark}] {res} -> {idn}")
            hits.append(FindResult(resource=res, idn=idn, source="scanned"))
    return hits


def find_device(
    idn_contains: str,
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    proto: str = "inst0",
    allow_scan: bool = False,
    cidr: Optional[str] = None,
    timeout_ms: int = 3000,
) -> FindResult:
    """按查找链发现 *IDN? 含 idn_contains 的设备，未找到抛 RuntimeError。

    参数见模块 docstring。proto 仅对 hosts 生效（inst0=VXI-11 / hislip0=HiSLIP）。
    """
    needle = idn_contains.lower()

    def matches(idn: str) -> bool:
        return needle in idn.lower()

    attempts: list[tuple[str, str, str]] = []

    def probe(res: str, layer: str) -> Optional[str]:
        idn = identify(res, timeout_ms)
        attempts.append((layer, res, idn or "无响应/打开失败"))
        tag = "HIT" if idn and matches(idn) else ("dev" if idn else "--")
        print(f"[{layer}] [{tag}] {res}" + (f" -> {idn}" if idn else ""))
        return idn

    explicit: list[str] = []
    if resource:
        explicit.append(tcpip_resource(resource))
    explicit.extend(tcpip_resource(h, proto) for h in (hosts or []))

    explicit_failed = False
    mismatched: list[tuple[str, str]] = []
    for res in explicit:
        idn = probe(res, "explicit")
        if idn is None:
            explicit_failed = True
        elif matches(idn):
            return FindResult(resource=res, idn=idn, source="explicit")
        else:
            mismatched.append((res, idn))
    if mismatched:
        found = "; ".join(f"{res} -> {idn}" for res, idn in mismatched)
        raise ValueError(
            f"显式指定的设备在线但不是目标（期望 *IDN? 含 {idn_contains!r}）：{found}；拒绝自动换设备"
        )

    def try_listed() -> Optional[FindResult]:
        for res in list_resources():
            idn = probe(res, "listed")
            if idn and matches(idn):
                return FindResult(resource=res, idn=idn, source="listed")
        return None

    if not explicit or (explicit_failed and allow_scan):
        hit = try_listed()
        if hit:
            return hit

    if not allow_scan:
        attempts.append(("scanned", "-", "allow_scan=False，跳过网段扫描"))
    else:
        segment = cidr or detect_cidr()
        if segment is None:
            attempts.append(("scanned", "-", "无法探测本机网段且未显式给 cidr"))
        else:
            if not cidr:
                print(f"[scan] 未指定网段，自动探测为 {segment}（多网卡环境建议显式传 cidr）")
            for hit in scan_cidr(segment, idn_contains, SCAN_TIMEOUT_MS):
                if matches(hit.idn):
                    return hit

    chain = "\n".join(f"  [{layer}] {target}: {result}" for layer, target, result in attempts)
    raise RuntimeError(f"未找到 *IDN? 含 {idn_contains!r} 的设备，尝试链路：\n{chain}")


def _main() -> None:
    for res, idn in scan().items():
        print(f"{res:45s} -> {idn or '(no response)'}")


if __name__ == "__main__":
    _main()
