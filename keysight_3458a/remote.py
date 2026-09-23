"""父进程侧的 worker 代理：`RemoteDMM` —— 与 `DMM3458A` **同名接口**，但每次调用都过子进程。

两个关键保证（对应 `worker.py` 文档里的两条理由）：

* **干净进程**：子进程只加载 Keysight VISA 栈 —— 避开"MCP 长驻进程里已装系统 VISA
  （pyvisa）导致 `viOpen` 访问违例 / `viWrite` `INV_OBJECT`"的串味问题；
* **硬截止 + kill**：调用超过 `deadline_s` 没回来（典型：卡在 `ioGPIB` 里），直接
  `kill()` 子进程 —— Windows 强制回收句柄，接口随之释放；下一次调用自动拉起新 worker。

用法::

    with RemoteDMM("GPIB0::9::INSTR") as d:
        print(d.idn(), d.read_dcv())

`RemoteDMM` 暴露的方法与 `DMM3458A` 同名（白名单见 `worker.ALLOWED_METHODS`），
所以 MCP 工具与脚本可以原样迁移。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .transport import TransportError

ROOT = Path(__file__).resolve().parent.parent


class RemoteDMM:
    """3458A 的进程外代理（接口同 `DMM3458A`）。"""

    def __init__(self, resource: str = "GPIB0::9::INSTR", timeout_s: float = 30.0,
                 deadline_s: float = 120.0, python: Optional[str] = None,
                 env: Optional[dict] = None):
        self.resource = resource
        self.timeout_s = float(timeout_s)
        self.deadline_s = float(deadline_s)
        self._python = python or sys.executable
        self._env = env
        self._proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._connected = False
        self.kills = 0                      # 统计：被 kill 的次数（可观测性）

    # ---------- 进程管理 ----------
    def _start(self) -> None:
        """只**拉起**子进程（不连接设备）；连接由调用方的 `connect()` 触发。"""
        if self._proc is not None and self._proc.poll() is None:
            return
        env = dict(os.environ if self._env is None else self._env)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        # 子进程**不再登记会话锁**：父进程（MCP/脚本）已经登记，子进程再登记会让父进程
        # 把自己人误判成"另一个进程在用"（实测假告警）。见 DMM3458A._claim()。
        env["INSTRUMENT_NO_SESSION_LOCK"] = "1"
        self._proc = subprocess.Popen(
            [self._python, "-u", "-m", "keysight_3458a.worker"],
            cwd=str(ROOT), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1)

    def kill(self, why: str = "") -> None:
        """强杀子进程（句柄随之回收）。下次调用会自动重启 worker。

        `why` 为空表示**正常关闭**（不计入 `kills`）；带原因表示异常/超时强杀（计入）。
        """
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:                                     # noqa: BLE001
            pass
        if why:
            self.kills += 1
            sys.stderr.write(f"[3458A worker] killed: {why}\n")

    # ---------- RPC ----------
    def _rpc(self, payload: dict, deadline_s: Optional[float] = None) -> Any:
        self._start_if_needed()
        assert self._proc is not None and self._proc.stdin and self._proc.stdout
        self._id += 1
        # **必须每次带上 resource**：子进程按它建会话；漏了就会永远去连默认地址
        # （2026-09-23 实测：传 GPIB9::9::INSTR 却连上了 GPIB0::9 的真表，静默串台）。
        payload = {"id": self._id, "resource": self.resource, **payload}
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        except Exception as exc:                              # noqa: BLE001
            self.kill(f"写入请求失败：{exc}")
            raise TransportError(f"3458A worker 写入失败（已重启）：{exc}") from exc

        box: "queue.Queue[str]" = queue.Queue()

        def _reader() -> None:
            try:
                box.put(self._proc.stdout.readline() if self._proc else "")
            except Exception as exc:                          # noqa: BLE001
                box.put(f"__ERR__{exc}")

        threading.Thread(target=_reader, daemon=True).start()
        limit = float(deadline_s if deadline_s is not None else self.deadline_s)
        try:
            line = box.get(timeout=limit)
        except queue.Empty:
            self.kill(f"超过硬截止 {limit:.0f}s 无响应（疑似卡在 ioGPIB 内）")
            raise TransportError(
                f"3458A worker 超过硬截止 {limit:.0f}s 未响应 → 已 kill 并回收句柄"
                f"（这正是独立进程的意义：卡死不再拖垮 MCP）")
        if not line:
            self.kill("子进程退出/管道关闭")
            raise TransportError("3458A worker 无输出（已 kill，下次调用会重启）")
        if line.startswith("__ERR__"):
            self.kill(line)
            raise TransportError(f"3458A worker 读管道异常：{line[7:]}")
        try:
            rep = json.loads(line)
        except Exception as exc:                              # noqa: BLE001
            self.kill(f"回复非法 JSON：{line[:80]!r}")
            raise TransportError(f"3458A worker 回复非法 JSON：{line[:80]!r}") from exc
        if not rep.get("ok"):
            raise TransportError(f"{rep.get('error')}")
        return rep.get("result")

    def _start_if_needed(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            self._start()

    def call(self, method: str, **kwargs) -> Any:
        # 除 connect/close/recover/prepare 之外的操作：**自动先连**（同 DMM3458A 的用法习惯）
        if method not in ("connect", "close", "recover", "prepare_for_read") and not self._connected:
            self.connect()
        out = self._rpc({"op": "call", "method": method, "kwargs": kwargs})
        if method == "connect":
            self._connected = True
        elif method == "close":
            self._connected = False
        return out

    def get(self, attr: str) -> Any:
        return self._rpc({"op": "get", "attr": attr})

    # ---------- 与 DMM3458A 同名的方法（MCP 工具直接用这些）----------
    def connect(self, recover: Any = "auto", force: bool = False) -> Any:
        out = self.call("connect", recover=recover, force=force)
        self._connected = True
        return out

    def close(self) -> None:
        try:
            if self._proc is not None and self._proc.poll() is None:
                self._rpc({"op": "close"}, deadline_s=10.0)
        except Exception:                                     # noqa: BLE001
            pass
        finally:
            self._connected = False
            self.kill()

    def idn(self, timeout_s: Optional[float] = None) -> str:
        return self.call("idn", **({"timeout_s": timeout_s} if timeout_s else {}))

    def state(self) -> dict:
        return self.call("state")

    def error_string(self) -> str:
        return self.call("error_string")

    def temperature(self) -> Any:
        return self.call("temperature")

    def read_dcv(self, timeout_s: Optional[float] = None) -> float:
        return self.call("read_dcv", **({"timeout_s": timeout_s} if timeout_s else {}))

    def read_acv(self, timeout_s: Optional[float] = None) -> float:
        return self.call("read_acv", **({"timeout_s": timeout_s} if timeout_s else {}))

    def read_avg(self, n: int = 1) -> float:
        return self.call("read_avg", n=n)

    def read_stats(self, n: int = 1) -> dict:
        return self.call("read_stats", n=n)

    def read_series(self, n: int = 10, interval_s: Optional[float] = None,
                    timeout_s: Optional[float] = None) -> dict:
        kwargs: dict = {"n": n}
        if interval_s is not None:
            kwargs["interval_s"] = interval_s
        if timeout_s is not None:
            kwargs["timeout_s"] = timeout_s
        return self.call("read_series", **kwargs)

    def read_burst(self, n: int, **kwargs) -> dict:
        # burst 的硬截止按 n×采样间隔放大（worker 内部也有自己的超时预算）
        interval = float(kwargs.get("sample_interval_s") or 1e-3)
        limit = min(300.0, max(60.0, 30.0 + 3.0 * int(n) * interval))
        return self._rpc({"op": "call", "method": "read_burst",
                          "kwargs": {"n": n, **kwargs}}, deadline_s=limit)

    def configure_dcv(self, dcv_range: Any = 10.0, nplc: Optional[float] = None) -> Any:
        kwargs: dict = {"dcv_range": dcv_range}
        if nplc is not None:
            kwargs["nplc"] = nplc
        return self.call("configure_dcv", **kwargs)

    def set_range(self, dcv_range: Any) -> Any:
        return self.call("set_range", dcv_range=dcv_range)

    def set_autorange(self, on: bool = True) -> Any:
        return self.call("set_autorange", on=on)

    def set_nplc(self, nplc: float) -> Any:
        return self.call("set_nplc", nplc=nplc)

    def configure_acv(self, *args, **kwargs) -> Any:
        return self.call("configure_acv", *args, **kwargs)

    def reset(self) -> Any:
        return self.call("reset")

    def unstick(self) -> dict:
        return self.call("unstick")

    def recover(self) -> Any:
        return self.call("recover")

    def prepare_for_read(self) -> Any:
        return self.call("prepare_for_read")

    def write(self, cmd: str) -> Any:
        return self.call("write", cmd=cmd)

    def query(self, cmd: str, timeout_s: Optional[float] = None) -> str:
        return self.call("query", **{"cmd": cmd, **({"timeout_s": timeout_s} if timeout_s else {})})

    # ---------- 同名属性 ----------
    @property
    def current_nplc(self) -> Any:
        return self.get("current_nplc")

    @property
    def current_range(self) -> Any:
        return self.get("current_range")

    @property
    def holders(self) -> list:
        try:
            return self.get("holders")
        except Exception:                                     # noqa: BLE001
            return []

    # ---------- 上下文管理 ----------
    def __enter__(self) -> "RemoteDMM":
        self._start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):                                        # pragma: no cover
        try:
            self.kill()
        except Exception:                                     # noqa: BLE001
            pass

    def __repr__(self) -> str:                                # pragma: no cover
        return (f"RemoteDMM({self.resource!r}, pid="
                f"{self._proc.pid if self._proc else None}, kills={self.kills})")


def worker_available() -> tuple[bool, str]:
    """能否用进程外 worker：拉起子进程并做一次 `__sleep 0` 往返（不碰设备）。"""
    try:
        d = RemoteDMM("GPIB0::9::INSTR")
        try:
            out = d._rpc({"op": "__sleep", "seconds": 0}, deadline_s=30.0)
            return (out == "slept"), str(out)
        finally:
            d.kill()
    except Exception as exc:                                  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"
