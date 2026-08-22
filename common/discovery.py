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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import pyvisa

SCAN_WORKERS = 32
SCAN_TIMEOUT_MS = 1500
# TCP 端口预筛（任一通即候选）：VXI-11 portmapper / HiSLIP / SCPI raw(5025 Keysight 等 /
# 5555 Rigol)。仅用于快速淘汰死地址与非仪器主机；设备身份仍由 VISA + *IDN? 确认。
SCAN_PROBE_PORTS = (111, 4880, 5025, 5555)
PROBE_TIMEOUT_S = 0.6
PROBE_WORKERS = 128


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
    """对单个资源发送 *IDN?，成功返回识别串，失败/超时返回 None。

    SOCKET 资源自动配置 \\n 读写终止符（VISA socket 会话无协议层终止符，
    不配则命令不完整导致设备不应答）。
    """
    kwargs: dict = {}
    if "SOCKET" in resource.upper():
        kwargs = {"read_termination": "\n", "write_termination": "\n"}
    try:
        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(resource, **kwargs)
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


# LAN 多协议探测顺序（实测 2026-08-23：DH1766A-1 仅 raw socket 5025 可达；
# RIGOL DHO924S 示波器仅 raw socket 5555 可达；VISA SOCKET 会话必须显式配置
# \n 终止符，否则命令不完整导致超时）
LAN_PROTOCOLS: tuple[tuple[str, dict], ...] = (
    ("TCPIP0::{host}::inst0::INSTR", {}),
    ("TCPIP0::{host}::hislip0::INSTR", {"read_termination": "\n"}),
    ("TCPIP0::{host}::5025::SOCKET",
     {"read_termination": "\n", "write_termination": "\n"}),
    ("TCPIP0::{host}::5555::SOCKET",
     {"read_termination": "\n", "write_termination": "\n"}),
)


def identify_lan(host: str, timeout_ms: int = 3000) -> Optional[tuple[str, str]]:
    """按 LAN_PROTOCOLS 逐协议探测 *IDN?，成功返回 (可用资源串, idn)，全败返回 None。

    host 含 '::' 视为完整资源串，仅按其本身探测。
    """
    resources = [host] if "::" in host else [t.format(host=host) for t, _ in LAN_PROTOCOLS]
    rm = pyvisa.ResourceManager()
    try:
        for res in resources:
            kwargs = next(
                (kw for t, kw in LAN_PROTOCOLS if t.format(host=host) == res),
                {} if res.endswith("INSTR") else
                {"read_termination": "\n", "write_termination": "\n"},
            )
            try:
                inst = rm.open_resource(res, open_timeout=timeout_ms, **kwargs)
                inst.timeout = timeout_ms
                try:
                    idn = inst.query("*IDN?").strip()
                    if idn:
                        return (res, idn)
                finally:
                    inst.close()
            except Exception:
                continue
        return None
    finally:
        rm.close()


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


def probe_alive(ip: str, ports: tuple[int, ...] = SCAN_PROBE_PORTS,
                timeout_s: float = PROBE_TIMEOUT_S) -> bool:
    """TCP 端口预筛：任一指定端口可建立连接返回 True（死地址秒级淘汰）。"""
    for port in ports:
        try:
            with socket.create_connection((ip, port), timeout=timeout_s):
                return True
        except OSError:
            continue
    return False


def scan_cidr(
    cidr: str,
    idn_contains: str,
    timeout_ms: int = SCAN_TIMEOUT_MS,
    prefilter: bool = True,
) -> list[FindResult]:
    """并发扫描网段内全部地址，返回所有在线设备的 FindResult（含非目标设备）。

    prefilter=True（默认）先经 TCP 端口预筛淘汰无仪器服务的地址，再对候选做 VISA
    *IDN? 识别（纯 VISA 全网段实测约 8.5 分钟，预筛后约数秒）。
    每个在线设备实时打印留痕（[HIT] 为 IDN 匹配目标）；无响应地址静默跳过。
    """
    net = ipaddress.ip_network(cidr, strict=False)
    addrs = [str(h) for h in net.hosts()]
    print(f"[scan] 网段 {cidr} 共 {len(addrs)} 个地址，workers={SCAN_WORKERS}")

    if prefilter:
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
            alive = [
                a for a, ok in zip(addrs, pool.map(probe_alive, addrs)) if ok
            ]
        print(
            f"[scan] 端口预筛({','.join(map(str, SCAN_PROBE_PORTS))}) "
            f"候选 {len(alive)}/{len(addrs)}，耗时 {time.monotonic() - t0:.1f}s"
        )
        for a in alive:
            print(f"[scan] 候选: {a}")
        addrs = alive

    needle = idn_contains.lower()
    hits: list[FindResult] = []
    done = 0
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        futures = {pool.submit(identify_lan, a, timeout_ms): a for a in addrs}
        for fut in as_completed(futures):
            done += 1
            addr = futures[fut]
            found = fut.result()
            if not found:
                continue
            res, idn = found
            mark = "HIT" if needle in idn.lower() else "dev"
            print(f"[scan {done}/{len(addrs)}] [{mark}] {res} -> {idn}")
            hits.append(FindResult(resource=res, idn=idn, source="scanned"))
    return hits


def find_device(
    idn_contains: str,
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    allow_scan: bool = False,
    cidr: Optional[str] = None,
    timeout_ms: int = 3000,
    prefilter: bool = True,
) -> FindResult:
    """按查找链发现 *IDN? 含 idn_contains 的设备，未找到抛 RuntimeError。

    层① resource 完整资源串（USB/TCPIP 均可）→ 层② hosts（IP/host 列表，
    按 LAN_PROTOCOLS 自动选协议：VXI-11 / HiSLIP / raw5025-SOCKET）→
    层③ list_resources 全扫 → 层④ CIDR 网段扫描。
    层③④ 仅在未给显式参数、或显式全失败且 allow_scan=True 时执行；
    prefilter 仅对层④生效：True 先 TCP 端口预筛再 VISA 识别（推荐）。
    要固定协议时把完整资源串传给 resource（如 TCPIP0::ip::hislip0::INSTR）。
    """
    needle = idn_contains.lower()

    def matches(idn: str) -> bool:
        return needle in idn.lower()

    attempts: list[tuple[str, str, str]] = []
    mismatched: list[tuple[str, str]] = []
    explicit_failed = False

    explicit_targets: list[str] = ([resource] if resource else []) + list(hosts or [])
    for target in explicit_targets:
        hit: Optional[tuple[str, str]] = None
        if "::" in target:
            idn = identify(target, timeout_ms)
            hit = (target, idn) if idn else None
        else:
            hit = identify_lan(target, timeout_ms)
        if hit is None:
            explicit_failed = True
            attempts.append(("explicit", target, "无响应/打开失败"))
            print(f"[explicit] [--] {target}")
            continue
        res, idn = hit
        attempts.append(("explicit", res, idn))
        print(f"[explicit] [{'HIT' if matches(idn) else 'dev'}] {res} -> {idn}")
        if matches(idn):
            return FindResult(resource=res, idn=idn, source="explicit")
        mismatched.append((res, idn))
    if mismatched:
        found = "; ".join(f"{res} -> {idn}" for res, idn in mismatched)
        raise ValueError(
            f"显式指定的设备在线但不是目标（期望 *IDN? 含 {idn_contains!r}）：{found}；拒绝自动换设备"
        )

    def try_listed() -> Optional[FindResult]:
        for res in list_resources():
            idn = identify(res, timeout_ms)
            attempts.append(("listed", res, idn or "无响应/打开失败"))
            print(f"[listed] [{'HIT' if idn and matches(idn) else '--'}] {res}"
                  + (f" -> {idn}" if idn else ""))
            if idn and matches(idn):
                return FindResult(resource=res, idn=idn, source="listed")
        return None

    if not explicit_targets or (explicit_failed and allow_scan):
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
            for cand in scan_cidr(segment, idn_contains, SCAN_TIMEOUT_MS, prefilter=prefilter):
                if matches(cand.idn):
                    return cand

    chain = "\n".join(f"  [{layer}] {target}: {result}" for layer, target, result in attempts)
    raise RuntimeError(f"未找到 *IDN? 含 {idn_contains!r} 的设备，尝试链路：\n{chain}")


def _main() -> None:
    for res, idn in scan().items():
        print(f"{res:45s} -> {idn or '(no response)'}")


if __name__ == "__main__":
    _main()
