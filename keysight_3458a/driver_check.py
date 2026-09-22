"""3458A 通路预检查：82357B USB/GPIB 是否插着、驱动是否正常、Keysight VISA 是否可用。

用途（**连不上时的第一诊断**，AGENTS.md：报错要给可执行结论，不要只说"超时"）：
    >>> from keysight_3458a.driver_check import check_gpib_driver
    >>> r = check_gpib_driver()
    >>> r["verdict"], r["message"]

判定分层（本机 2026-09-23 实测的现场顺序）：
    1) 设备不在 → `device_absent`（没插 / 线松 / 仪器没上电）
    2) 在但 `Status != OK` 或 ProblemCode=28 → `driver_missing`
       → **提示用户安装 Keysight IO Libraries Suite**（82357B 的驱动由它提供；
         不要试图自己装：需要管理员权限与厂商安装包）
    3) 驱动正常但没有 `ktvisa32.dll` → `iolib_missing` → 同样是装 IO Libraries Suite
    4) 都正常 → `ok`

实现：PnP 查询走 PowerShell（SetupAPI 的纯 ctypes 版本要近百行，这里不值得）；
结果缓存 `_CACHE_TTL` 秒，避免每次调用都起进程。**只读**，不碰仪器。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import winreg
from typing import Optional

# 82357B USB/GPIB 转换器（Keysight/Agilent）
GPIB_USB_VID_PID = "VID_0957&PID_0718"
GPIB_USB_NAME = "Keysight Technologies 82357B"
# 82357B 的"驱动未安装"典型值（CM_PROB_FAILED_INSTALL）
PROBLEM_DRIVER_MISSING = 28
SUITE_DIR = r"C:\Program Files\Keysight\IO Libraries Suite"

_CACHE: dict = {}
_CACHE_TTL = 30.0


def _ps_json(script: str, timeout_s: float = 20.0):
    """跑一段 PowerShell 并解析 JSON（失败返回 None，不抛——诊断工具本身要稳）。"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", script],
            capture_output=True, timeout=timeout_s)
    except Exception:
        return None
    out = (r.stdout or b"").decode("utf-8", "replace").strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def _gpib_usb_devices() -> list[dict]:
    """列出 82357B 类设备的 PnP 状态（含 ProblemCode）。"""
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"$devs = Get-PnpDevice -PresentOnly | Where-Object {{ $_.InstanceId -like '*{GPIB_USB_VID_PID}*' }};"
        "$out = foreach ($d in $devs) {"
        "  $prob = (Get-PnpDeviceProperty -InstanceId $d.InstanceId"
        "           -KeyName 'DEVPKEY_Device_ProblemCode').Data;"
        "  [pscustomobject]@{ instance_id=$d.InstanceId; status=[string]$d.Status;"
        "    class=[string]$d.Class; name=[string]$d.FriendlyName; problem=$prob }"
        "};"
        "@($out) | ConvertTo-Json -Compress -Depth 4"
    )
    data = _ps_json(script)
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    return [d for d in data if isinstance(d, dict)]


def _suite_info() -> dict:
    """Keysight IO Libraries Suite 安装信息（注册表只读）。"""
    info: dict = {"dir": SUITE_DIR if os.path.isdir(SUITE_DIR) else None,
                  "version": None, "install_date": None}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Keysight\IO Libraries Suite\CurrentVersion") as k:
            for name, key in (("version", "CurrentVersion"),
                              ("install_date", "InstallDate")):
                try:
                    info[name] = str(winreg.QueryValueEx(k, key)[0])
                except OSError:
                    pass
    except OSError:
        pass
    return info


def _ktvisa32() -> Optional[str]:
    """Keysight VISA 核心 DLL（先查 VXIPNPPATH，再查 System32）。"""
    try:
        p = _visa_base()
        if p:
            cand = os.path.join(p, "Win64", "ktvisa", "ktbin", "ktvisa32.dll")
            if os.path.isfile(cand):
                return cand
    except Exception:
        pass
    cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                        "System32", "ktvisa32.dll")
    return cand if os.path.isfile(cand) else None


def _visa_base() -> Optional[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\VXIPNP_Alliance\VXIPNP\CurrentVersion") as k:
            return winreg.QueryValueEx(k, "VXIPNPPATH")[0]
    except OSError:
        return None


def check_gpib_driver(use_cache: bool = True) -> dict:
    """检查 82357B + 驱动 + Keysight VISA，返回结论与**可执行**提示。

    返回体：
        ok        : bool             —— 通路前置条件是否齐备
        verdict   : str              —— ok / device_absent / driver_missing / iolib_missing
        message   : str              —— 给用户看的一句话（缺驱动时=提示装 IO Libraries Suite）
        devices   : list[dict]       —— 找到的 82357B PnP 设备（实例 ID/状态/问题码）
        suite     : dict             —— IO Libraries Suite 版本/目录
        ktvisa32  : str | None       —— Keysight VISA 核心 DLL 路径
    """
    key = "gpib_driver"
    now = time.time()
    if use_cache and key in _CACHE and now - _CACHE[key][0] < _CACHE_TTL:
        return _CACHE[key][1]

    devices = _gpib_usb_devices()
    suite = _suite_info()
    kt = _ktvisa32()

    bad = [d for d in devices
           if str(d.get("status", "")).upper() != "OK"
           or (d.get("problem") not in (None, 0))]
    if not devices:
        verdict = "device_absent"
        message = (f"未找到 {GPIB_USB_NAME}（{GPIB_USB_VID_PID}）：检查适配器是否插好、"
                   f"3458A 是否上电、GPIB 电缆是否接在适配器上")
    elif bad:
        verdict = "driver_missing"
        problems = ", ".join(f"{d.get('name') or '?'} status={d.get('status')} "
                             f"problem={d.get('problem')}" for d in bad)
        message = (f"{GPIB_USB_NAME} 已插上但驱动异常（{problems}）——"
                   f"请**安装 Keysight IO Libraries Suite**（82357B 的驱动由它提供），"
                   f"装完重新插拔适配器；不要装 NI-488.2（不支持 82357B）")
    elif not kt:
        verdict = "iolib_missing"
        message = ("找到适配器但缺少 Keysight VISA 核心 ktvisa32.dll——"
                   "请安装 Keysight IO Libraries Suite")
    else:
        verdict = "ok"
        message = (f"{GPIB_USB_NAME} 驱动正常"
                   + (f"，Keysight IO Libraries {suite.get('version')}" if suite.get("version")
                      else ""))

    result = {
        "ok": verdict == "ok",
        "verdict": verdict,
        "message": message,
        "devices": devices,
        "suite": suite,
        "ktvisa32": kt,
    }
    _CACHE[key] = (now, result)
    return result


if __name__ == "__main__":                       # 手工排查入口
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="ascii", errors="replace")
        except Exception:
            pass
    print(json.dumps(check_gpib_driver(use_cache=False), ensure_ascii=False, indent=2))
