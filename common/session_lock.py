"""跨进程**会话咨询锁**：多个客户端/MCP 实例同时操作同一台仪器时的软性告警。

为什么需要（2026-09-17 实机论证，见 `docs/visa_concurrency_20260917.md`）：
**同一台设备开两个会话并发会"静默串台"**——两个客户端会互相读到对方的响应
（DG832/USB 实测约一半查询丢响应 + 100+ 次答非所问；MHO 的 VXI-11/raw 两会话同样串台），
而响应本身都是合法值，调用方判断不出来。本机实测曾同时存在 14 个 instrument MCP 实例。

设计口径（用户指定，2026-09-17）：
- **键 = VISA 地址**（资源串，规范化大小写）——"同一台设备"目前就按同一个 VISA 地址区分；
- 同一台设备的**另一个接口**（如 MHO 的 `inst0`(VXI-11) 与 `5555`(raw)、HiSLIP）**不参与判重**，
  只额外给一条告警：**跨接口并发是否安全尚未验证**（本次实验里 raw 与 VXI-11 互相读到
  对方响应的现象，是在 VXI-11 已被并发搞错位之后观察到的，不能作为定论）；
- 本模块只**告警**、**不阻塞**：仪器共享是常见需求，硬拦会误伤；调用方看到 warning 自行决定。

实现：`<配置目录>/session_locks/<addr>.json`，内容 {pid, started, ts, resource, kind}。
"活跃"判据 = pid 仍存在 **且** ts 新鲜（TTL 内）；过期/死进程的锁文件会被顺手清掉。
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
from pathlib import Path
from typing import Optional

# 锁文件 TTL：超过这么久没刷新就视为过期（MCP 每次工具调用都会刷新自己的锁）
LOCK_TTL_S = 180.0


def _locks_dir() -> Path:
    """锁目录：与地址解析层同一个用户级配置目录（`%LOCALAPPDATA%\\instrumentControl`）。"""
    try:
        from common.resolver import CONFIG_DIR  # 复用同一处配置根，避免两套路径

        base = Path(CONFIG_DIR)
    except Exception:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "instrumentControl"
    return base / "session_locks"


def resource_key(resource: Optional[str]) -> Optional[str]:
    """地址键：资源串规范化（去空白、大写）——**判重就按它**。"""
    if not resource:
        return None
    return re.sub(r"\s+", "", str(resource)).upper()


def device_key(resource: Optional[str]) -> Optional[str]:
    """物理设备键（**仅用于"同设备不同接口"的额外告警**，不用于判重）。

    - LAN/VXI-11/SOCKET → `TCPIP::<host>`（同 IP 的不同协议/端口视为同一台设备）
    - USB-TMC          → `USB::<vid>:<pid>:<serial>`
    - 串口             → `ASRL::<port>`
    解析不出来时返回地址键本身（退化为"只按地址判"）。
    """
    if not resource:
        return None
    s = str(resource).strip()
    m = re.match(r"(TCPIP\d*)::([^:]+)::", s, re.I)
    if m:
        return f"TCPIP::{m.group(2).upper()}"
    m = re.match(r"(USB\d*)::0x([0-9A-Fa-f]+)::0x([0-9A-Fa-f]+)::([^:]+)::", s, re.I)
    if m:
        return f"USB::{m.group(2).upper()}:{m.group(3).upper()}:{m.group(4).upper()}"
    m = re.match(r"(ASRL\d*)::", s, re.I)
    if m:
        return f"ASRL::{m.group(1).upper()}"
    return resource_key(resource)


def _fname(key: str, pid: int | None = None) -> str:
    """地址键（+ PID）→ 锁文件名：可读前缀 + 短哈希，**每个进程一份**。

    为什么带 PID（2026-09-17 实机踩到）：一开始按地址命名 → 同一资源的不同进程写的是
    **同一个文件**：后写的把先写的**覆盖**掉，扫描时又因文件名相同被当成"自己的锁"跳过
    → 永远不告警（还会悄悄删掉别人的占用记录）。带 PID 后每个进程一份，互不干扰。
    """
    import hashlib

    safe = re.sub(r"[^0-9A-Za-z]+", "_", key)[:60].strip("_") or "res"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"{safe}_{h}__{os.getpid() if pid is None else pid}.json"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        import psutil

        return bool(psutil.pid_exists(pid))
    except Exception:
        pass
    if os.name == "nt":
        # ⚠ Windows 上**绝不能**用 `os.kill(pid, 0)` 探活：Python 的 os.kill 在
        # Windows 上除 CTRL_C/CTRL_BREAK 之外一律走 TerminateProcess——"探活"会
        # 变成"杀掉对方进程"。这里用 OpenProcess 只拿查询权限句柄（不改状态）。
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return True            # 探不动就当活着（宁可多告警，也不误删他人锁）
    try:
        os.kill(pid, 0)            # POSIX：信号 0 才是真正的探活
        return True
    except Exception:
        return False


def touch(resource: Optional[str], kind: str = "", host: str | None = None) -> dict:
    """刷新"本进程正在用该资源"的锁，并返回他人占用情况。

    返回 `{"key", "device", "holders": [...], "warnings": [...]}`：
    - `holders`：**同一地址**的其他活跃进程（就是 H3/H4 里会串台的场景）；
    - `warnings`：可直接拼进工具返回体的中文告警（同地址最严重；同设备不同接口次之）。

    本函数**绝不抛异常**（锁是辅助设施，不能因为它让工具失败）：任何 IO 问题都降级为
    空告警，并把原因写进 `error` 字段。
    """
    out: dict = {"key": None, "device": None, "holders": [], "other_interfaces": [],
                 "warnings": []}
    key = resource_key(resource)
    if not key:
        return out
    dev = device_key(resource)
    out["key"], out["device"] = key, dev
    if host is None:
        try:
            host = socket.gethostname()
        except Exception:
            host = ""
    d = _locks_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        now = time.time()
        mine = d / _fname(key)
        mine.write_text(json.dumps({"pid": os.getpid(), "ts": now,
                                    "started": out.setdefault("started", now),
                                    "resource": resource, "kind": kind, "host": host},
                                   ensure_ascii=False), encoding="utf-8")
        for f in d.glob("*.json"):
            if f.name == mine.name:
                continue
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            ts = float(rec.get("ts") or 0)
            pid = int(rec.get("pid") or 0)
            if ts and now - ts > LOCK_TTL_S:
                try:
                    f.unlink()               # 过期即清理（顺手做，不额外留垃圾）
                except Exception:
                    pass
                continue
            if not _pid_alive(pid):
                try:
                    f.unlink()               # 进程已死：清理
                except Exception:
                    pass
                continue
            rec["file"] = f.name
            if rec.get("key_") == key or resource_key(rec.get("resource")) == key:
                out["holders"].append(rec)
            elif dev and device_key(rec.get("resource")) == dev:
                out["other_interfaces"].append(rec)
        for h in out["holders"]:
            age = max(0.0, now - float(h.get("started") or h.get("ts") or now))
            out["warnings"].append(
                f"⚠ 另一个进程（PID {h.get('pid')}，已运行 {age:.0f}s）正在使用**同一地址** "
                f"{resource}：实测同一设备两会话并发会**响应串台**（互相读到对方的答案，"
                "且值都合法、判断不出来）——请勿同时操作，或先与对方确认。")
        for h in out["other_interfaces"]:
            out["warnings"].append(
                f"⚠ 另一个进程（PID {h.get('pid')}）正在使用**同一台仪器的另一接口** "
                f"（{h.get('resource')}）：**跨接口并发是否安全尚未验证**（本次实测中 raw 与 "
                "VXI-11 通道有互相读到对方响应的现象，但该现象出现在通道已被并发搞错位之后，"
                "不能作为定论）——建议也按同一台设备串行。")
    except Exception as e:                      # noqa: BLE001 —— 锁是辅助设施，绝不阻断工具
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def release(resource: Optional[str]) -> None:
    """释放本进程对该资源的锁（幂等；进程退出时也可靠 TTL/pid 判据自动过期）。"""
    key = resource_key(resource)
    if not key:
        return
    f = _locks_dir() / _fname(key, os.getpid())
    try:
        if f.exists():
            rec = json.loads(f.read_text(encoding="utf-8"))
            if int(rec.get("pid") or 0) == os.getpid():
                f.unlink()
    except Exception:
        pass


def holders(resource: Optional[str]) -> list[dict]:
    """只读查询：当前**同一地址**的活跃占用者（含自己）。"""
    key = resource_key(resource)
    if not key:
        return []
    out = []
    try:
        for f in _locks_dir().glob("*.json"):
            rec = json.loads(f.read_text(encoding="utf-8"))
            if int(rec.get("pid") or 0) == os.getpid():
                continue
            if resource_key(rec.get("resource")) == key and _pid_alive(int(rec.get("pid") or 0)):
                out.append(rec)
    except Exception:
        pass
    return out
