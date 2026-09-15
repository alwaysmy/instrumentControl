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
import json
import socket
import subprocess
import sys
import threading
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

# 串口探测挂起硬超时（驱动层 open 可能不受 open_timeout 约束）。
# 实测（9 口）：并发 8 会让子进程互相争抢串口资源、多数误报超时；并发 4 正常，
# 全量探测约 15s 完成。
SERIAL_PROBE_TIMEOUT_S = 8.0

# 本进程内探测挂起的串口：后续发现跳过，避免每轮重复空等（子进程隔离已保证
# 不会污染本进程，这里纯粹是速度优化）。显式重新发现用 forget_hanging_ports() 清空。
_HANGING_PORTS: set[str] = set()


def forget_hanging_ports() -> None:
    """清空「挂起串口」缓存（显式重新发现前调用，允许重新探测这些口）。"""
    _HANGING_PORTS.clear()

# 串口探测走**子进程**（不是本进程线程）。
# 为什么必须子进程（2026-09-15 实测，MCP 服务器反复掉线）：
#   某些串口会让驱动层 open **永久挂起**且无视 open_timeout。在本进程里用
#   daemon 线程 + join 超时"看起来"能脱身，但那个线程仍卡在驱动里、持续持有
#   VISA 原生状态；此后**本进程的任何 VISA 调用都会让进程直接死亡**（无异常、
#   无栈，客户端只看到连接断开）。实测：设备工具因地址缓存过期触发自动发现，
#   第一次 37s 返回后，第二个工具调用即整个服务器掉线；同一序列在修复前后
#   稳定复现。
#   子进程隔离后，超时即 kill——子进程连同卡住的句柄一起消失，本进程原生
#   状态不被污染。代价是每口一次解释器启动（并行，约 1s 量级），可接受。
_SERIAL_PROBE_SCRIPT = r'''
import json, sys
import pyvisa
res, timeout_ms = sys.argv[1], int(sys.argv[2])
out = {"resource": res, "idn": None, "note": None}
rm = None
try:
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(res, open_timeout=2000)
    inst.timeout = timeout_ms
    inst.write_termination = "\n"
    inst.read_termination = "\n"
    try:
        idn = inst.query("*IDN?").strip()
        out["idn"] = idn or None
        if not idn:
            out["note"] = "打开成功但无 *IDN? 响应（非 SCPI 设备或波特率不匹配）"
    finally:
        inst.close()
except Exception as e:
    code = getattr(e, "error_code", 0)
    if "BUSY" in str(e).upper() or code == -1073807346:
        out["note"] = "串口被占用（其他程序打开中）"
    else:
        out["note"] = "打开失败: " + type(e).__name__
finally:
    if rm is not None:
        try:
            rm.close()
        except Exception:
            pass
print(json.dumps(out, ensure_ascii=False))
'''


def probe_serial_isolated(resource: str, timeout_ms: int = 1500,
                          hard_timeout_s: float = SERIAL_PROBE_TIMEOUT_S) -> dict:
    """在**子进程**里探测一个串口，超时即杀。返回 {resource,idn,note}。

    这是唯一安全的串口探测方式——详见 `_SERIAL_PROBE_SCRIPT` 上方说明
    （本进程线程探测会留下卡死线程，导致后续任何 VISA 调用令进程崩溃）。
    """
    cmd = [sys.executable, "-c", _SERIAL_PROBE_SCRIPT, resource, str(int(timeout_ms))]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=hard_timeout_s,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"resource": resource, "idn": None,
                "note": f"探测超时({hard_timeout_s:.0f}s，驱动挂起，疑似被占用)"}
    except Exception as e:
        return {"resource": resource, "idn": None,
                "note": f"子进程启动失败: {type(e).__name__}"}
    if p.returncode != 0:
        return {"resource": resource, "idn": None,
                "note": f"子进程异常退出 rc={p.returncode}"}
    for line in reversed((p.stdout or "").strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return {"resource": resource, "idn": None, "note": "子进程无有效输出"}


def probe_serials_isolated(resources: list[str], timeout_ms: int = 1500,
                           hard_timeout_s: float = SERIAL_PROBE_TIMEOUT_S,
                           workers: int = 4) -> list[dict]:
    """并行探测多个串口（每个一口子进程），保持入参顺序返回。

    已确认挂起的口（`_HANGING_PORTS`）直接跳过返回占位结果——省下每轮 8s×N 的
    空等（实测 9 口中 4 个挂起，全量 55s → 跳过挂起口后约 10s）。子进程隔离
    已保证挂起口不会污染本进程，缓存只是加速；`forget_hanging_ports()` 可清空。
    """
    if not resources:
        return []
    todo = [r for r in resources if r not in _HANGING_PORTS]
    skipped = [r for r in resources if r in _HANGING_PORTS]
    results: dict[str, dict] = {
        r: {"resource": r, "idn": None, "note": "已知挂起（本轮跳过，instr_discover 可重探）"}
        for r in skipped
    }
    if todo:
        with ThreadPoolExecutor(max_workers=min(workers, len(todo)) or 1) as pool:
            for entry in pool.map(
                    lambda r: probe_serial_isolated(r, timeout_ms, hard_timeout_s), todo):
                results[entry["resource"]] = entry
                if str(entry.get("note") or "").startswith("探测超时"):
                    _HANGING_PORTS.add(entry["resource"])
    return [results[r] for r in resources]


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
    不配则命令不完整导致设备不应答）。open_timeout 与读超时同设——
    否则离线资源的 TCP 连接阶段可达 60s+（系统默认）。
    """
    kwargs: dict = {}
    if "SOCKET" in resource.upper():
        kwargs = {"read_termination": "\n", "write_termination": "\n"}
    rm = pyvisa.ResourceManager()
    try:
        inst = rm.open_resource(resource, open_timeout=timeout_ms, **kwargs)
        inst.timeout = timeout_ms
        try:
            return inst.query("*IDN?").strip()
        finally:
            inst.close()
    except Exception:
        return None
    finally:
        rm.close()


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


# LAN 多协议探测顺序（实测 2026-08-23：RIGOL DHO 系列示波器仅 raw socket 5555 可达；
# 大华 DH1766A-1 电源仅 raw socket 5025 可达；VISA SOCKET 会话必须显式配置
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
    """经 UDP 路由探测本机出口 IP，返回所在 /24 网段；失败返回 None。

    仅接受 RFC1918 私网（10/172.16-31/192.168）。注意 Python 的 is_private
    会把 198.18.0.0/15（benchmark 段，代理 fake-IP 常用）也判为私有，
    必须显式排除——扫它得到 254 个假地址且 VISA open 全部挂起。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        addr = ipaddress.ip_address(ip)
        ok = addr in ipaddress.ip_network("10.0.0.0/8") or \
            addr in ipaddress.ip_network("172.16.0.0/12") or \
            addr in ipaddress.ip_network("192.168.0.0/16")
        if not ok:
            return None
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
    print(f"[scan] 网段 {cidr} 共 {len(addrs)} 个地址，workers={SCAN_WORKERS}", file=sys.stderr)

    if prefilter:
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
            alive = [
                a for a, ok in zip(addrs, pool.map(probe_alive, addrs)) if ok
            ]
        print(
            f"[scan] 端口预筛({','.join(map(str, SCAN_PROBE_PORTS))}) "
            f"候选 {len(alive)}/{len(addrs)}，耗时 {time.monotonic() - t0:.1f}s",
            file=sys.stderr,
        )
        for a in alive:
            print(f"[scan] 候选: {a}", file=sys.stderr)
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
            print(f"[scan {done}/{len(addrs)}] [{mark}] {res} -> {idn}", file=sys.stderr)
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
            print(f"[explicit] [--] {target}", file=sys.stderr)
            continue
        res, idn = hit
        attempts.append(("explicit", res, idn))
        print(f"[explicit] [{'HIT' if matches(idn) else 'dev'}] {res} -> {idn}", file=sys.stderr)
        if matches(idn):
            return FindResult(resource=res, idn=idn, source="explicit")
        mismatched.append((res, idn))
    if mismatched:
        found = "; ".join(f"{res} -> {idn}" for res, idn in mismatched)
        raise ValueError(
            f"显式指定的设备在线但不是目标（期望 *IDN? 含 {idn_contains!r}）：{found}；拒绝自动换设备"
        )

    def try_listed() -> Optional[FindResult]:
        listed = list_resources()
        # 串口先经子进程并行探测（本进程线程探测会留下卡死线程 → 后续 VISA 调用
        # 令进程崩溃，详见 probe_serial_isolated 说明）；非串口在本进程直接识别。
        serial_res = [r for r in listed if r.upper().startswith("ASRL")]
        serial_idn: dict[str, Optional[str]] = {}
        if serial_res:
            for entry in probe_serials_isolated(serial_res, timeout_ms):
                serial_idn[entry["resource"]] = entry.get("idn")
                note = entry.get("note") or entry.get("idn") or "无响应"
                print(f"[listed] [{'HIT' if entry.get('idn') and matches(entry['idn']) else '--'}] "
                      f"{entry['resource']} -> {note}", file=sys.stderr)

        for res in listed:
            if res.upper().startswith("ASRL"):
                idn = serial_idn.get(res)
                attempts.append(("listed", res, idn or "无响应/打开失败/占用"))
            else:
                idn = identify(res, timeout_ms)
                attempts.append(("listed", res, idn or "无响应/打开失败"))
                print(f"[listed] [{'HIT' if idn and matches(idn) else '--'}] {res}"
                      + (f" -> {idn}" if idn else ""), file=sys.stderr)
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
                print(f"[scan] 未指定网段，自动探测为 {segment}（多网卡环境建议显式传 cidr）", file=sys.stderr)
            for cand in scan_cidr(segment, idn_contains, SCAN_TIMEOUT_MS, prefilter=prefilter):
                if matches(cand.idn):
                    return cand

    chain = "\n".join(f"  [{layer}] {target}: {result}" for layer, target, result in attempts)
    raise RuntimeError(f"未找到 *IDN? 含 {idn_contains!r} 的设备，尝试链路：\n{chain}")


def _main() -> None:
    for res, idn in scan().items():
        print(f"{res:45s} -> {idn or '(no response)'}", file=sys.stderr)


if __name__ == "__main__":
    _main()
