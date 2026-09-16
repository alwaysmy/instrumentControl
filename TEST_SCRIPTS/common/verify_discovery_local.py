"""发现层**网络与分块**的离线回归（只用 loopback，不扫任何真实网段）。

来源：2026-09-16 实机排查"找不到 MHO"时踩到的两个缺陷——
① `local_cidrs()` 假设 /24，而本机仪器网卡是 **/16**（`192.168.1.100/255.255.0.0`）：
   同一广播域里但不在 `/24` 内的仪器会被**静默漏掉**（最难查的假阴性）；
② `probe_open_ports()` 一次性 `gather` 整个 /16（6.5 万协程）→ `MemoryError`。

    python TEST_SCRIPTS/common/verify_discovery_local.py

断言：
    §1 local_cidrs 用接口**真实掩码**（/16 就报 /16；掩码缺失/非法退回 /24；max_prefix 收敛）
    §2 chunked() 分块边界（空 / 整除 / 不整除 / size<=0）
    §3 probe_open_ports 在 loopback 上功能正确（开着的端口能发现、关闭的不误报）
    §4 大列表分块后不 MemoryError（20000 个地址、关闭端口、极小超时）
"""
from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import common.discovery as cd  # noqa: E402

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:58s} {str(detail)[:100]}", flush=True)
    if not ok:
        fails.append(name)


class _Addr:
    """psutil 地址条目的最小替身（只用到 family/address/netmask）。"""

    def __init__(self, address, netmask="255.255.255.0"):
        self.family = socket.AF_INET
        self.address = address
        self.netmask = netmask


def _fake_psutil(entries):
    class _P:
        @staticmethod
        def net_if_addrs():
            return entries
    return _P


print("§1 local_cidrs：按接口真实掩码（/16 不能报成 /24）", flush=True)
_saved = sys.modules.get("psutil")
# /16 网卡（本机实况）+ /24 网卡 + 一条掩码缺失的
sys.modules["psutil"] = _fake_psutil({
    "以太网": [_Addr("192.168.1.100", "255.255.0.0")],
    "WLAN": [_Addr("172.16.80.245", "255.255.255.0")],
    "怪网卡": [_Addr("10.9.9.9", None)],
})
got = cd.local_cidrs()
check("/16 网卡 → 报 192.168.0.0/16（不是 /24）", "192.168.0.0/16" in got, str(got))
check("/24 网卡 → 仍报 /24", "172.16.80.0/24" in got, str(got))
check("掩码缺失 → 退回 /24（不崩）", "10.9.9.0/24" in got, str(got))
check("max_prefix=20 收敛更宽的网段", cd.local_cidrs(max_prefix=20)[0] == "192.168.0.0/20",
      str(cd.local_cidrs(max_prefix=20)))
check("max_prefix=8 时不放大（/16 保持 /16）", cd.local_cidrs(max_prefix=8)[0] == "192.168.0.0/16",
      str(cd.local_cidrs(max_prefix=8)))
if _saved is not None:
    sys.modules["psutil"] = _saved
else:
    sys.modules.pop("psutil", None)

print("\n§2 chunked() 分块边界", flush=True)
check("空列表 → 空块列表（调用方先挡空输入）", cd.chunked([], 2) == [], str(cd.chunked([], 2)))
check("正好整除", cd.chunked([1, 2, 3, 4], 2) == [[1, 2], [3, 4]])
check("不整除 → 余数成尾块", cd.chunked([1, 2, 3], 2) == [[1, 2], [3]])
check("size<=0 → 不分块", cd.chunked([1, 2, 3], 0) == [[1, 2, 3]])

print("\n§3 probe_open_ports 功能（loopback）", flush=True)
srv = socket.socket()
srv.bind(("127.0.0.1", 0))
srv.listen(4)
port = srv.getsockname()[1]
def _serve():
    for _ in range(4):
        try:
            c, _a = srv.accept()
            c.close()
        except OSError:
            return   # 测试收尾关掉 listener 后的正常退出

threading.Thread(target=_serve, daemon=True).start()
res = cd.probe_open_ports(["127.0.0.1"], ports=(port, 1), timeout_s=0.5)
check("开着的端口被发现", port in res.get("127.0.0.1", set()), str(res))
check("关闭的端口不误报", 1 not in res.get("127.0.0.1", set()), str(res))
srv.close()

print("\n§4 大列表分块不 MemoryError", flush=True)
big = ["127.0.0.1"] * 20000
res4 = cd.probe_open_ports(big, ports=(1,), timeout_s=0.05, chunk=2048)
check("20000 个地址（默认分块）跑完不爆内存", len(res4) == 1, f"{len(res4)} 条结果")
check("显式 chunk=5000 亦可", len(cd.probe_open_ports(big[:5000], ports=(1,),
                                                     timeout_s=0.05, chunk=5000)) == 1)

print(f"\n== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL'} ==")
for f in fails:
    print(f"  - {f}")
sys.exit(1 if fails else 0)
