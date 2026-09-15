# -*- coding: utf-8 -*-
from __future__ import annotations

"""
instrument MCP Server — 五台仪器的统一 MCP 接口。

设备库：sds_control(示波器) / sdg_control(信号源) / keysight_3446x(万用表) /
dho_control(示波器) / dh1766_control(电源)，经 common 统一发现层。

启动: python mcp_instruments/server.py

地址解析：**server 内不写死任何 IP**。仪器地址随 DHCP/网段/换口/串口号变化，
各专用工具的 `resource` 参数默认 None，由 `_resolve()` 依次取
显式入参 → 环境变量 `INSTRUMENT_<KIND>_RES` → 用户配置 `devices.json`
→ 上次成功缓存 → `find_device()` 自动发现。详见 `_resolve` 上方注释。

安全约定：
    - 复位类命令不暴露（黑名单 confirm 也不放行）；
    - 远程锁定类命令（SYST:REM/RWL/LOCK/COMM:RLST）同样黑名单拦截，纯查询放行；
    - 关机/输出类工具需显式 confirm=True；
    - 每次调用连接→操作→关闭（无状态）+ 全局设备锁串行化。
"""
import contextlib
import os
import re
import sys
import json
import csv
import time
import threading
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for sub in ("dh1766_control/src",):
    sys.path.insert(0, os.path.join(ROOT, sub))

from mcp.server.fastmcp import FastMCP
from mcp import types as mcp_types

mcp = FastMCP("instruments")

# Codex（Windows）对同时声明 prompts+resources 能力的 stdio 服务器存在
# “工具发现成功但不注入会话”的缺陷（实测 kimi-cu 仅声明 tools 可正常注入，
# everything-mcp 与 instrument 声明 prompts 后均注入失败）。本服务器只用 tools，
# 移除 prompts/resources 处理器，使初始化能力收敛为仅 tools。
for _req_type in (
    mcp_types.ListPromptsRequest,
    mcp_types.GetPromptRequest,
    mcp_types.ListResourcesRequest,
    mcp_types.ListResourceTemplatesRequest,
    mcp_types.ReadResourceRequest,
):
    mcp._mcp_server.request_handlers.pop(_req_type, None)

_DEVICE_LOCK = threading.Lock()
_PREWARM_DONE = threading.Event()  # VISA/设备库冷启动完成前置位（看门狗放宽依据）


def _env_float(name: str, default: float) -> float:
    """读环境变量浮点覆盖值（坏值回退默认，配置写错不打断服务）。"""
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


# 看门狗与设备锁等待（设计见 _call 顶部；两者都可用环境变量覆盖，不必改码）：
#   INSTRUMENT_CALL_BUDGET_S：单次调用墙钟上限，超时放弃并报 timeout
#   INSTRUMENT_LOCK_WAIT_S  ：等设备锁的上限，超时报 device_busy（不再无限等）
# 默认 150s：须长于最长合法操作（SDS auto_scale 闭环最坏 ~7 档 ×(PKPK+FREQ 各 6s
# 超时) ≈ 90s+），否则会把正常慢操作误判成挂起。
_CALL_BUDGET_S = _env_float("INSTRUMENT_CALL_BUDGET_S", 150.0)
_LOCK_WAIT_S = _env_float("INSTRUMENT_LOCK_WAIT_S", 30.0)

# 设备专用工具返回体里回填"本次实际用的地址"：模型名 → 解析层的 kind
_MODEL_KIND = {"SDS": "sds", "SDG": "sdg", "DMM": "dmm", "DHO": "dho", "MHO": "mho",
               "DG832": "dg", "DH1766": "psu"}
_LAST_RESOLVED: dict[str, str] = {}  # kind -> 本次调用解析出的资源串（_DEVICE_LOCK 内更新）


def _out_res(model_name: str, resource: str | None) -> str | None:
    """输出用资源串：显式传入优先，否则回填本次解析结果（仅设备类工具）。"""
    return resource or _LAST_RESOLVED.get(_MODEL_KIND.get(model_name, ""))

# ============ 设备地址解析（不写死 IP）============
#
# 实现已下沉到 `common/resolver.py`：MCP 服务器与 `TEST_SCRIPTS/` 共用同一套
# 地址来源（避免"两套缓存/两套键"）。解析顺序：
#   ① 工具入参 resource（显式指定）
#   ② 环境变量 INSTRUMENT_<KIND>_RES（如 INSTRUMENT_SDS_RES）
#   ③ 用户配置 <配置目录>/devices.json（{"sds": "TCPIP0::…::inst0::INSTR", …}）
#   ④ 上次成功缓存 <配置目录>/last_good_resources.json
#      （instr_discover 发现成功后按 *IDN? 回写；连接成功后也会回写）
#   ⑤ 自动发现 common.find_device(idn_contains=…, allow_scan=False)
#      （只查 VISA 已注册资源；LAN 未注册设备请先跑 instr_discover；
#        需要自动扫描可设 INSTRUMENT_ALLOW_SCAN=1）
# 这里保留与既有调用点一致的别名，实现细节见 common/resolver.py。
from common.resolver import (  # noqa: E402
    DEVICE_KINDS,
    idn_kind as _idn_kind,
    known_resources as _known_resources,
    remember as _remember,
    remember_candidates as _remember_candidates,
    resolve as _resolve,
    resource_rank as _resource_rank,
)


def _ok(model, result, resource=None):
    d = {"ok": True, "model": model, "result": result}
    if resource:
        d["resource"] = resource
    return json.dumps(d, ensure_ascii=False, default=str)


def _err(error_type, msg, model=None, resource=None):
    d = {"ok": False, "error_type": error_type, "error": msg}
    if model:
        d["model"] = model
    if resource:
        d["resource"] = resource
    return json.dumps(d, ensure_ascii=False, default=str)


def _call_locked(model_name, connect_fn, fn, close_fn=None, resource=None,
                 lock_wait_s=None):
    """持锁执行：连接→操作→关闭，错误分类。**不直接给工具用**（见 _call）。

    设备锁用 acquire(timeout) 而非无限等待：一旦前一个调用挂在 open 上（实测
    VXI-11 可无视 open_timeout 挂 2min+）并占着锁，后续调用会**快速失败**并明确
    告知原因，而不是全体无限排队（审查文档 D5 的另一半根因）。

    stdout 兜底：连接与操作在 `redirect_stdout(sys.stderr)` 下执行——本仓库函数
    （发现层/校准器）与第三方（pyvisa）都可能有 `print()`，而 stdio 模式下 stdout
    是 JSON-RPC 协议通道，一旦被污染客户端就 `Connection closed`（2026-09-15 实测：
    设备离线触发自动发现 → discovery 的 10 行 print 打进协议流 → 服务器掉线）。
    根因已按库修（改 stderr），这里再兜一层防未来漏网。MCP SDK 在启动时已用
    `sys.stdout.buffer` 捕获协议流，故重定向 `sys.stdout` 不影响协议写出；
    所有设备操作都在 `_DEVICE_LOCK` 内串行，重定向窗口不会并发交叉。
    """
    wait = _LOCK_WAIT_S if lock_wait_s is None else lock_wait_s
    if not _DEVICE_LOCK.acquire(timeout=max(0.0, wait)):
        return _err("device_busy",
                    f"设备锁被占用超过 {wait:.0f}s（另有调用挂起未释放，通常是某台"
                    "设备离线导致 open 卡住）；本次未向任何设备下发命令。"
                    "可稍后重试，或重启 MCP 服务彻底恢复。",
                    model_name, _out_res(model_name, resource))
    try:
        with contextlib.redirect_stdout(sys.stderr):
            try:
                dev = connect_fn()
            except Exception as e:
                return _err("connection", f"{type(e).__name__}: {e}", model_name, _out_res(model_name, resource))
            res = _out_res(model_name, resource)
            try:
                return _ok(model_name, fn(dev), res)
            except ValueError as e:
                return _err("param_validation", str(e), model_name, res)
            except RuntimeError as e:
                return _err("device_error", str(e), model_name, res)
            except Exception as e:
                return _err("communication", f"{type(e).__name__}: {e}", model_name, res)
            finally:
                try:
                    if close_fn is not None:
                        close_fn(dev)
                    elif hasattr(dev, "close"):
                        dev.close()
                except Exception:
                    pass
    finally:
        _DEVICE_LOCK.release()


def _call(model_name, connect_fn, fn, close_fn=None, resource=None,
          budget_s=None, lock_wait_s=None):
    """**所有工具的统一入口**：看门狗（墙钟上限）+ 持锁执行。

    为什么专用工具也要看门狗：设备的 `resource` 默认走解析链（含上次成功缓存），
    缓存地址可能已过期——指向离线主机时 `open` 会挂起（VXI-11 实测无视
    `open_timeout`）。通用工具早先已加看门狗，专用工具当时没有 → 同一个失效地址
    走专用工具即永久冻结。现在统一：调用跑在守护线程里，`join(budget_s)` 到点
    即返回 `timeout`（挂起线程随进程退出，不会永久占住线程）。

    ⚠ 局限性（如实记录）：看门狗**不释放设备锁**——Python 无法中断持有锁的线程。
    所以超时后，本服务器进入"快速失败"模式：后续调用由 `_call_locked` 的锁超时
    报 `device_busy`（不再无限卡死），但真正的恢复需要重启 MCP 进程。要彻底消除
    该模式需改成**按设备分锁**（一台设备挂起只影响它自己），但那要重新论证
    VISA 运行时的并发安全假设，属独立课题，不在此改。

    budget_s=None 时用 `_CALL_BUDGET_S`；预热未完成（VISA 冷启动实测 30-40s）再
    放宽 90s，防误杀首调用。close_fn 缺省调 dev.close()（DH1766 须显式传 _psu_close）。
    """
    budget = (_CALL_BUDGET_S if budget_s is None else budget_s)
    if not _PREWARM_DONE.is_set():
        budget += 90.0
    holder: dict = {}

    def work():
        holder["r"] = _call_locked(model_name, connect_fn, fn, close_fn, resource,
                                   lock_wait_s)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(budget)
    if t.is_alive():
        return _err("timeout",
                    f"{model_name} 调用超过 {budget:.0f}s 未返回（设备离线/总线挂起）。"
                    "已放弃等待；挂起线程仍占着设备锁，后续调用会改报 device_busy，"
                    "重启 MCP 服务可彻底恢复。",
                    model_name, _out_res(model_name, resource))
    return holder.get("r") or _err("internal", "worker 未返回结果", model_name,
                                   _out_res(model_name, resource))



def _verify_idn(kind: str, resource: str, idn: str | None) -> None:
    """连接后核对 *IDN? 是否确为目标设备类（地址可能已被 DHCP 回收给别的设备）。

    配置/缓存里的地址迟早会过期——若该 IP 现在属于另一台设备，继续下发 SCPI
    就是"对未知设备操作"（可能改掉别人的仪器设置）。核对不通过立即断开并报错，
    提示重新发现；核对通过才允许把地址写回缓存。
    """
    token, label, _env = DEVICE_KINDS[kind]
    if not idn or token.upper() not in idn.upper():
        raise RuntimeError(
            f"地址校验失败：{resource} 上的设备 *IDN? = {idn!r}，"
            f"与目标设备（{label}，期望含 {token!r}）不符——地址可能已被 DHCP "
            f"分配给其它设备。请先调用 instr_discover 重新发现，"
            f"或用 config_cli.py 更正本机配置（devices.json）。"
        )


def _sds(resource: str | None = None) -> SDS:
    from sds_control import SDS

    res = _resolve("sds", resource)
    _LAST_RESOLVED["sds"] = res  # 供返回体回填本次实际地址
    s = SDS(res)
    s.connect()
    _verify_idn("sds", res, s.idn())
    _remember("sds", res)
    return s


def _sdg(resource: str | None = None) -> SDG:
    from sdg_control import SDG

    res = _resolve("sdg", resource)
    _LAST_RESOLVED["sdg"] = res  # 供返回体回填本次实际地址
    g = SDG(res)
    g.connect()
    _verify_idn("sdg", res, g.idn())
    _remember("sdg", res)
    return g


def _dmm(resource: str | None = None) -> DMM:
    from keysight_3446x import DMM

    res = _resolve("dmm", resource)
    _LAST_RESOLVED["dmm"] = res  # 供返回体回填本次实际地址
    d = DMM(res)
    d.connect()
    _verify_idn("dmm", res, d.idn())
    _remember("dmm", res)
    return d


def _dho(resource: str | None = None) -> DHO:
    from dho_control import DHO

    res = _resolve("dho", resource)
    _LAST_RESOLVED["dho"] = res  # 供返回体回填本次实际地址
    h = DHO(res)
    h.connect()
    _verify_idn("dho", res, h.idn())
    _remember("dho", res)
    return h


def _mho(resource: str | None = None) -> MHO:
    from mho_control import MHO

    res = _resolve("mho", resource)
    _LAST_RESOLVED["mho"] = res  # 供返回体回填本次实际地址
    m = MHO(res)
    m.connect()
    _verify_idn("mho", res, m.idn())
    _remember("mho", res)
    return m


def _dg(resource: str | None = None, model: str | None = None) -> DG832:
    """DG832 连接（库自带 model 注册表；地址走解析层 kind=dg）。"""
    from dg832_control import DG832

    res = _resolve("dg", resource)
    _LAST_RESOLVED["dg"] = res  # 供返回体回填本次实际地址
    g = DG832(resource=res, **(dict(model=model) if model else {}))
    g.connect()
    _verify_idn("dg", res, g.idn())
    _remember("dg", res)
    return g


def _psu_connect(resource: str | None = None) -> DH1766:
    """DH1766 连接（DH1766 类无 close，退出经 _psu_close 关 client）。"""
    from dh1766_control import DH1766
    from dh1766_control.visa import VisaClient

    res = _resolve("psu", resource)
    _LAST_RESOLVED["psu"] = res  # 供返回体回填本次实际地址
    p = DH1766(VisaClient(res, timeout_ms=5000))
    _verify_idn("psu", res, p.idn())
    _remember("psu", res)
    return p


def _psu_close(p: DH1766) -> None:
    """DH1766 会话收尾：先把面板控制权还给现场，再关连接。

    2026-09-13 实测（V0.1.4.3）：**任何远程会话都会把电源置为 REM（远程模式）**
    ——`SYST:COMM:RLST?` 在新会话的第一条命令即返回 'REM'（此前手册/库用的
    `SYST:COMM:RLST:STAT?` 在本机无响应，已修正）。REM 下现场面板可能不可操作，
    故每次 DH1766 工具调用结束都补发一次 `SYST:LOC`（LOC 只归还面板控制权，
    **不改动输出/电压/模式**；同一会话内后续 SCPI 查询实测仍正常）。
    """
    try:
        if getattr(p, "client", None) is not None:
            p.local()
    except Exception:
        pass
    try:
        if getattr(p, "client", None) is not None:
            p.client.close()
    except Exception:
        pass


# ============ 发现 ============

@mcp.tool()
def instr_discover(cidr: str | None = None) -> str:
    """发现本机所有仪器。返回：
    lan: 网段扫描（TCP 预筛 + 多协议 *IDN?，键=资源串 值=IDN）；
    visa: VISA 资源列表——USB/GPIB/串口均自动探测 *IDN?（串口被占用时
    返回占用提示，空闲则探测后立即断开，约 2s/口）；
    resolved: 地址解析层当前已知映射（配置+缓存，键=设备类 sds/sdg/dmm/dho/psu）；
    recognised_now: 本次发现按 *IDN? 识别并写入缓存的设备地址；
    psu_local_restored: 探测到 DH1766 时是否已补发 SYST:LOC 归还面板控制权
    （该电源任何远程会话都会进 REM，见 dh1766_control/docs/EXPERIENCE.md §3.1）。
    cidr 参数可选（如 '10.0.0.0/24'），默认自动探测本机 /24
    （代理虚拟网卡环境需显式传）。

    **仪器地址不是固定资产**（DHCP/网段/换口/串口号都会漂移）：本工具发现的
    结果会自动回写地址缓存，之后各专用工具不传 resource 也能连上；换了网段或
    发现工具报连接失败时，先重新跑一次本工具即可。"""
    import ipaddress
    import concurrent.futures as cf
    from common.discovery import (
        detect_cidr,
        forget_hanging_ports,
        identify,
        identify_lan,
        list_resources,
        probe_alive,
        probe_serials_isolated,
    )

    # 显式重新发现：清空"挂起串口"缓存，允许重新探测这些口（自动发现路径会跳过
    # 它们以省时；只有用户主动调本工具时才值得重试一遍）
    forget_hanging_ports()

    def fn(_):
        # VISA 资源（USB/串口/GPIB）先探测——不依赖网段，代理干扰不影响

        def probe_visa(r: str):
            """非串口 VISA 资源探测（USB/GPIB 走 VISA，有 open_timeout 兜底）。"""
            up = r.upper()
            entry = {"resource": r}
            if "INSTR" in up:
                idn = identify(r, timeout_ms=2000)
                entry.update(kind="usb/gpib", online=bool(idn), idn=idn)
            else:
                entry.update(kind="other", online=None)
            return entry

        # 串口：**子进程隔离**探测（每口一进程，并行）。
        # 为什么不是本进程线程：驱动层 open 可能永久挂起，线程 join 超时只是
        # "放弃等待"——那个线程仍卡在驱动里持有 VISA 原生状态，之后本进程任何
        # VISA 调用都会让进程直接死亡（2026-09-15 实测，MCP 反复掉线）。
        # 子进程超时可 kill，卡住的句柄随子进程一起消失（见
        # common/discovery.probe_serial_isolated 的完整说明）。
        resources = list_resources()
        non_serial = [r for r in resources if not r.upper().startswith("ASRL")]
        serial_res = [r for r in resources if r.upper().startswith("ASRL")]
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            visa = list(pool.map(probe_visa, non_serial))
        for entry in probe_serials_isolated(serial_res, timeout_ms=1500):
            idn = entry.get("idn")
            item = {"resource": entry["resource"], "kind": "serial",
                    "online": bool(idn) if idn else (None if entry.get("note") else False)}
            if idn:
                item["idn"] = idn
            if entry.get("note"):
                item["note"] = entry["note"]
            visa.append(item)

        # LAN 网段扫描（代理 fake-IP 会污染，任何异常降级为警告，不拖垮 VISA 结果）
        seg = cidr or detect_cidr()
        lan, warn = {}, None
        try:
            if not seg:
                warn = "无法探测本机网段（代理/VPN 虚拟网卡？），LAN 部分跳过；可显式传 cidr"
            else:
                addrs = [str(h) for h in ipaddress.ip_network(seg, strict=False).hosts()]
                with cf.ThreadPoolExecutor(max_workers=128) as pool:
                    alive = [a for a, ok in zip(addrs, pool.map(probe_alive, addrs)) if ok]
                # 代理 fake-IP 模式会对任意 IP 立即 SYN-ACK → 全部误报 alive →
                # 后续 VISA open 逐个挂起拖死线程池（实测 254 全 alive 卡死 5min+）
                if len(alive) > 64:
                    warn = (
                        f"网段 {seg} 探测到 {len(alive)}/{len(addrs)} 地址端口全开——"
                        "疑似代理/VPN fake-IP 干扰，LAN 结果已丢弃。"
                        "请关闭代理后重试，或用 resource 参数直连。"
                    )
                else:
                    with cf.ThreadPoolExecutor(max_workers=32) as pool:
                        for a, r in pool.map(lambda x: (x, identify_lan(x)), alive):
                            if r:
                                lan[r[0]] = r[1]
        except Exception as e:
            warn = f"LAN 扫描异常降级（VISA 结果不受影响）: {type(e).__name__}: {e}"

        # 把发现到的设备按 IDN 回写地址缓存：之后各专用工具无需显式传 resource
        # 即可自动解析（IP 会变，所以地址只做"上次成功"缓存，不是固定资源配置）。
        pairs: list[tuple[str, str]] = [(res, idn) for res, idn in lan.items()]
        pairs += [(e.get("resource", ""), e.get("idn") or "") for e in visa]
        recognised = _remember_candidates(pairs)

        # DH1766 特例：任何远程会话（含发现时的 *IDN? 探测）都会把电源置为 REM，
        # 现场面板可能因此不可操作；探测到它就补发一次 SYST:LOC 归还面板控制权
        # （仅改面板控制权，不触碰输出/电压/模式；失败静默，不影响发现结果）。
        restored_local = False
        psu_res = recognised.get("psu")
        if psu_res:
            try:
                from dh1766_control import DH1766
                from dh1766_control.visa import VisaClient

                p = DH1766(VisaClient(psu_res, timeout_ms=2000))
                p.local()
                p.client.close()
                restored_local = True
            except Exception:
                restored_local = False

        out = {"cidr": seg, "lan": lan, "visa": visa,
               "resolved": _known_resources(), "recognised_now": recognised,
               "psu_local_restored": restored_local}
        if warn:
            out["warning"] = warn
        return out

    return _call("discovery", lambda: None, fn, close_fn=lambda _: None)


# ============ 故障维护兜底：USB-TMC 卡死恢复 ============
#
# 与 instr_discover 同级的"环境维护"工具，不属于任何设备类。
# 恢复顺序见 AGENTS.md 铁律#14：先重连 → 不行再重启该 USB 的 PnP 设备
# （USB 重新枚举，**仪器固件不重启、设定不丢**；DG832 实测 2.4s 恢复）→ 最后才拔插/断电。

@mcp.tool()
def usb_reset(kind: str | None = None, resource: str | None = None,
              confirm: bool = False, escalate: bool = False,
              verify_idn: bool = True, timeout_s: int = 20) -> str:
    """⚠ 故障兜底：重启某台仪器所占用的 **USB PnP 设备节点**（USB-TMC 卡死时用）。

    用在哪：`*IDN?` 超时 / `VI_ERROR_TMO` / `VI_ERROR_SYSTEM_ERROR`，且**先重连一次仍不恢复**时。
    效果：USB 重新枚举——**仪器固件不重启、通道设定/输出/保护全部保留**（DG832 实测 2.4s 恢复）；
    比"拔插 USB"省事，**不要**直接给仪器断电（那是最后手段）。

    参数：kind（解析层设备类 sds/sdg/dmm/dho/mho/dg/psu，地址走解析层）或 resource（USB 资源串）
    二选一；confirm=True 必填（该仪器所有会话会中断 2~3 秒）；escalate=True 时若进程无管理员
    权限会**弹 UAC** 提权；verify_idn=True 复位后轮询 *IDN? 确认设备回来。
    仅支持 USB 资源——LAN 卡死请先重连/换协议（inst0 ↔ raw socket），不属本工具场景。"""
    if not confirm:
        return _err("confirm_required",
                    "usb_reset 会重启该仪器的 USB 设备节点（会话中断约 2~3 秒），需 confirm=True",
                    "USB")
    if not kind and not resource:
        return _err("param_validation", "需要 kind 或 resource 之一", "USB")

    def fn(_):
        from common.resolver import resolve as _res
        from common.usb_reset import (find_instance, is_admin, parse_usb_resource,
                                      restart_device, wait_back)
        res = resource or _res(kind)
        parsed = parse_usb_resource(res)
        if not parsed:
            raise ValueError(f"不是 USB-TMC 资源串（本工具只处理 USB）：{res}")
        vid, pid, serial = parsed
        inst = find_instance(vid, pid, serial)
        if not inst:
            raise RuntimeError(f"未找到 VID=0x{vid} PID=0x{pid} 的 PnP 设备（设备可能已掉线，需拔插）")
        if not is_admin() and not escalate:
            raise RuntimeError("改动设备节点需要管理员权限：加 escalate=True（弹 UAC），"
                               f'或在管理员终端执行 pnputil /restart-device "{inst}"')
        ok, out = restart_device(inst)
        verified = None
        if ok and verify_idn:
            verified, _note = wait_back(res, timeout_s)
        return {"resource": res, "instance": inst, "restart_ok": ok,
                "output": out[:200], "verified_idn": verified}

    return _call("USB", lambda: None, fn, close_fn=lambda _: None)


# ============ 通用护栏 SCPI（新设备零代码接入） ============
#
# 设计取舍：不做多设备接口统一——各库专用工具承载人工筛选的语义与安全门；
# 通用工具只提供"对照手册直发命令"的护栏通道，设备用出价值后再补专用库。

# 复位/存储覆写类黑名单（AGENTS.md 安全红线）：confirm=True 也不放行——
# 需显式授权的复位场景走测试脚本（如 dh1766 --allow-rst），不经 MCP。
_FORBIDDEN_COMMON_RE = re.compile(r"\*(RST|SAV|RCL)")  # *RST / *SAV n / *RCL n

# 子系统助记符表：(短形式, 长形式)。SCPI 允许短形式与长形式之间的**任意前缀**
# （SCPI-99 §6.2.2 命令助记符），只比对两种写法会漏掉中间缩写
# （实测漏网：`:SYST:RESE`、`:SYST:PRESE`、`:SYST:COMMU:RLST RWL`）。
_RESET_NODES = (("RES", "RESET"), ("FACT", "FACTORY"), ("PRES", "PRESET"))
_LOCK_NODES = (("REM", "REMOTE"), ("RWL", "RWL"), ("LOCK", "LOCKED"))
_COMM_NODES = (("COMM", "COMMUNICATE"),)
_RLST_NODES = (("RLS", "RLSTATE"),)


def _mnemonic(token: str, short: str, long: str) -> bool:
    """SCPI 助记符匹配（宽松，黑名单用「宁可误拦」的偏置）。

    接受三类写法：① short..long 之间的任意前缀（SCPI-99 §6.2.2）；② 长形式本身；
    ③ 短形式开头后粘连参数（如 `SYST:REMON` = `SYST:REM ON`，历史实现按正则前缀
    搜索能拦下，行为必须保持）。
    """
    t, lo = token.upper(), long.upper()
    return len(t) >= len(short) and (lo.startswith(t) or t.startswith(short))


def _any_node(token: str, pairs: tuple[tuple[str, str], ...]) -> bool:
    return any(_mnemonic(token, s, l) for s, l in pairs)


def _classify_forbidden(cmd: str) -> str | None:
    """逐条（`;` 分段）判定命令是否命中黑名单；命中返回类别，否则 None。

    必须在**分段**上判定：`*RST;*IDN?` 这类多命令消息单看整串会漏判，
    只看首段又会漏掉后续段（历史缺陷：instr_query 只查 `?` 不看黑名单，
    `"*IDN?;:SYST:RESE"` 可直接复位仪器）。
    """
    for part in cmd.split(";"):
        # 先切出命令头（空格前）再归一——否则 "SYST:REM ON" 归一成 "SYST:REMON"，
        # 参数会粘连到助记符上导致漏判。
        stripped = part.strip()
        if not stripped:
            continue
        head = re.split(r"\s+", stripped)[0].upper().lstrip(":")
        if not head:
            continue
        # 公共命令族（*RST/*SAV/*RCL）在**整段**上搜，不限定在命令头——数据段里混进
        # 这几个词没有正当用途，宁可误拦（防御"参数位置偷发复位"）。
        if _FORBIDDEN_COMMON_RE.search(stripped):
            return "reset"
        segs = [s for s in head.split(":") if s]
        if not segs or not _mnemonic(segs[0], "SYST", "SYSTEM"):
            continue
        if len(segs) >= 2 and _any_node(segs[1], _RESET_NODES):
            return "reset"
        if len(segs) >= 2 and _any_node(segs[1], _LOCK_NODES):
            return "lock"
        if len(segs) >= 3 and _any_node(segs[1], _COMM_NODES) and _any_node(segs[2], _RLST_NODES):
            return "lock"
    return None


# 单条命令单元的形状：命令头以 `?` 结尾，问号后**允许**带参数。
#
# `?` 后带参数是标准 SCPI 写法（`:MEASure:ITEM? VPP,CHANnel2`、`SAMPle:COUNt? MAX`），
# 故不能按"整段以 ? 结尾"判（2026-09-15 曾因此把带参数查询全拒了，用户报障后修正）。
_QUERY_UNIT_RE = re.compile(r"^[:*]?[A-Za-z][A-Za-z0-9:<>{}_.]*\?(?:\s[\s\S]*)?$")


def _is_query_only(cmd: str) -> bool:
    """整条消息是否**纯查询**：每个 `;` 分段都必须是查询单元（问号后允许带参数）。

    为什么按"分段"而不是"整条"判：SCPI 里 `;` 分隔的是**同一条消息内的多个命令单元**，
    设备会逐个执行——实测 DG832 `:SOUR1:PHAS?;:SOUR1:PHAS 123` 的写单元真的生效
    （Keysight 手册明文：`TRIG:SOUR EXT;COUNT 10` 等价于两条命令）。只查首尾会让写命令
    从查询口溜进去；只允许单条单元又会把**多段回读**（`:CHANnel4:DISPlay?;:CHANnel4:SCALe?`）
    一起拒掉——那是合法且常用的用法（2026-09-15 曾这样过度收紧，用户报障后修回）。

    逐段判用同一条正则（一条命令单元 = `_QUERY_UNIT_RE`），不解析助记符：
    写命令（头里无 `?`）、混合消息（`:OUTP1 ON;:OUTP1?`）、复位/锁定类一律拦。
    """
    units = [u for u in (p.strip() for p in (cmd or "").split(";"))]
    if not units or any(not u for u in units):
        return False
    return all(_QUERY_UNIT_RE.match(u) for u in units)


def _is_forbidden(cmd: str) -> bool:
    """黑名单判定（复位/存储覆写一律拦；远程锁定类**只拦写**）。

    语义：复位/存储覆写类一律 forbidden；远程锁定类只在**非纯查询**时拦——
    `SYST:REM?`、`:SYSTem:LOCKed?` 这类纯查询不改变锁定状态，保留用于状态诊断。
    判定按 `;` 分段做，且接受 SCPI 长短形式之间的任意前缀缩写。
    """
    kind = _classify_forbidden(cmd)
    if kind == "reset":
        return True
    if kind == "lock":
        return not _is_query_only(cmd)
    return False


_ERR_CLEAN_RE = re.compile(r"^\+?0\s*,")


def _drain_errors(c) -> list[str]:
    """排空 SYST:ERR? 队列（铁律2），上限 20 条防死循环。"""
    errs: list[str] = []
    for _ in range(20):
        try:
            r = c.query("SYST:ERR?").strip()
        except Exception as e:
            return errs + [f"(SYST:ERR? 查询失败: {type(e).__name__})"]
        if _ERR_CLEAN_RE.match(r) or "no error" in r.lower():
            return errs
        errs.append(r)
    return errs + ["(错误队列超过 20 条，停止排空)"]


def _visa(resource: str, timeout_ms: int = 5000):
    from common.visa_client import VisaClient
    return VisaClient(resource, timeout_ms=max(500, min(timeout_ms, 30000)))


def _guarded_call(resource: str, timeout_ms: int, fn) -> str:
    """通用工具入口：预算由调用方 `timeout_ms` 推出，墙钟兜底与锁超时都交给
    统一 `_call`（专用工具走的是同一个入口，不再有两套看门狗实现）。

    通用工具会指向**任意**发现到的地址（含离线），故预算比专用工具保守：
    max(30, 12+timeout_ms)——下限 30s 覆盖 VISA 冷启动，随后随调用方给的
    timeout_ms 增长（clamp 500-30000ms）。
    """
    budget = max(30.0, 12.0 + timeout_ms / 1000.0)
    return _call("instruments", lambda: _visa(resource, timeout_ms), fn,
                 resource=resource, budget_s=budget)


def _audit_scpi(tool: str, resource: str, cmd: str, **extra) -> str:
    """通用 SCPI 写留痕：TEST_DATA/common/mcp_scpi_audit_YYYYMMDD.jsonl（含拒绝记录）。"""
    d = Path(ROOT) / "TEST_DATA" / "common"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"mcp_scpi_audit_{datetime.now():%Y%m%d}.jsonl"
    entry = {"ts": datetime.now().isoformat(timespec="seconds"),
             "tool": tool, "resource": resource, "cmd": cmd, **extra}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return str(p)


@mcp.tool()
def instr_query(resource: str, cmd: str, timeout_ms: int = 5000) -> str:
    """通用 SCPI 查询——新设备零代码接入：拿到 resource 即可对照手册直发查询。
    resource: 完整 VISA 资源串（instr_discover 可得）；
    cmd: 单条查询命令，必须含 '?'（如 '*IDN?'、':VOLT:DC?'、'C1:BSWV WVTP?'）；
    timeout_ms: IO 超时 500-30000，默认 5000。
    串口(ASRL)设备按默认 9600 波特（EmoeCalibrator 实测值），暂不支持改波特率。
    只读不留痕；写操作用 instr_write（有黑名单/confirm/审计三道护栏）。
    设备无响应有硬超时看门狗（下限 30s，覆盖 VISA 冷启动），离线资源不会冻结 MCP。

    护栏：`cmd` 里每条 `;` 分段**都必须是查询**——判据是"命令头里带 '?'"，
    **问号后允许带参数**（`:MEASure:ITEM? VPP,CHANnel1`、`:TRIGger:EDGE:LEVel? MAX`
    都是标准 SCPI 查询写法）。之所以逐段判而不是"整条以 ? 结尾"：SCPI 允许用 `;`
    串联多条命令，只查首尾会让 `"*IDN?;*RST"` 之类的写命令从查询口溜进去；
    命中的按 `forbidden` 拒绝。多命令消息要么全是查询，要么走 instr_write。"""
    if "?" not in cmd:
        return _err("param_validation", f"查询命令必须含 '?': {cmd!r}",
                    "instruments", resource)
    if _is_forbidden(cmd) or not _is_query_only(cmd):
        _audit_scpi("instr_query", resource, cmd, refused="multi_or_forbidden")
        return _err("forbidden",
                    f"instr_query 只接受纯查询消息（每个 ';' 分段都以 '?' 结尾）"
                    f"且不得含复位/锁定类命令: {cmd!r}", "instruments", resource)

    def fn(c):
        return {"response": c.query(cmd)}

    return _guarded_call(resource, timeout_ms, fn)


@mcp.tool()
def instr_write(resource: str, cmd: str, readback_cmd: str | None = None,
                confirm: bool = False, timeout_ms: int = 5000) -> str:
    """通用 SCPI 写——新设备零代码接入。⚠ 必须 confirm=True（raw 写权限大）。
    内置护栏（对应 AGENTS.md 铁律2/3 与安全红线）：
    1) 复位/存储覆写类（*RST/*SAV/*RCL/:SYST:RES|FACT|PRES，长短形式及中间缩写均拦）
       一律拒绝（error_type=forbidden，confirm 也不放行）；
    2) 写前 drain 错误队列、写后逐条排空 SYST:ERR?，返回 syst_errors；
    3) readback_cmd 给定时自动回读（铁律3），如写 'VOLT 1' 后传 'VOLT?'；
       readback_cmd 同样受黑名单约束且必须是**纯查询消息**（防从回读口偷发写命令）；
    4) 每次调用（含被拒绝的）落盘 TEST_DATA/common/mcp_scpi_audit_*.jsonl；
       看门狗超时记 executed="unknown"（命令可能已送达，须回读确认）；
    5) 离线/挂起资源硬超时看门狗，不会冻结 MCP。
    返回 result: {written, pre_errors, syst_errors, readback}。"""
    if _is_forbidden(cmd):
        _audit_scpi("instr_write", resource, cmd, refused="forbidden")
        return _err("forbidden", f"复位/存储覆写类命令禁止经 MCP 下发: {cmd!r}",
                    "instruments", resource)
    if not confirm:
        _audit_scpi("instr_write", resource, cmd, refused="confirm_required")
        return _err("confirm_required", "通用写需 confirm=True（raw SCPI 写权限）",
                    "instruments", resource)
    if readback_cmd and "?" not in readback_cmd:
        return _err("param_validation",
                    f"readback_cmd 是回读查询，必须含 '?': {readback_cmd!r}",
                    "instruments", resource)
    # 回读命令走的是 query()（同样会真的下发）——必须与 cmd 同受黑名单/纯查询约束，
    # 否则 "*RST;*IDN?" 可以从 readback_cmd 溜进去（历史缺陷）。
    if readback_cmd and (_is_forbidden(readback_cmd) or not _is_query_only(readback_cmd)):
        _audit_scpi("instr_write", resource, readback_cmd, refused="readback_multior_forbidden")
        return _err("forbidden",
                    f"readback_cmd 只接受纯查询消息且不得含复位/锁定类命令: {readback_cmd!r}",
                    "instruments", resource)
    _audit_scpi("instr_write", resource, cmd, refused=None, readback_cmd=readback_cmd)

    def fn(c):
        pre = _drain_errors(c)
        c.write(cmd)
        time.sleep(0.1)  # 设备解析入队延迟（串口/低速设备尤其需要）
        post = _drain_errors(c)
        rb = c.query(readback_cmd).strip() if readback_cmd else None
        return {"written": cmd, "pre_errors": pre or None, "syst_errors": post,
                "readback": {"cmd": readback_cmd, "response": rb}
                if readback_cmd else None}

    result = _guarded_call(resource, timeout_ms, fn)
    outcome = json.loads(result)
    # 看门狗超时只证明"没等到回包"，命令可能已送达并生效——审计必须记 unknown，
    # 否则事后无法区分"没执行"与"执行了没读到"（回读确认是第一手段）。
    _audit_scpi("instr_write", resource, cmd,
                executed="unknown" if outcome.get("error_type") == "timeout" else True,
                outcome=outcome)
    return result


# ============ SDS 示波器 ============

@mcp.tool()
def sds_status(resource: str | None = None) -> str:
    """SDS 示波器只读快照：IDN/采集/时基/触发/各通道档位耦合。"""
    return _call("SDS", lambda: _sds(resource), lambda s: s.snapshot())


@mcp.tool()
def sds_auto_scale(ch: int, use_autoset: bool = False, resource: str | None = None) -> str:
    """SDS 自动定标让通道 ch(1-4) 波形正确显示。
    use_autoset=True 为破坏性 :AUToset（重置所有通道档位/时基/触发），仅限
    简单周期信号且无其他已调好通道时显式启用；默认 SCPI 闭环只动目标通道。返回 actions/vpp/freq/adjusted。"""
    return _call("SDS", lambda: _sds(resource),
                 lambda s: s.auto_scale(ch, use_autoset=use_autoset))


@mcp.tool()
def sds_measure(item: str, ch: int = 4, resource: str | None = None) -> str:
    """SDS 单次测量（SIMPLE 模式，自动切模式+设信源）。ch=1-4。
    item 枚举（SIMPle:ITEM 表，51 项全支持）：PKPK/MAX/MIN/AMPL/TOP/BASE/
    LEVELX/CMEAN/MEAN/STDEV/VSTD/RMS/CRMS/MEDIAN/CMEDIAN/OVSN/FPRE/OVSP/
    RPRE/ULOWer/PER/FREQ/TMAX/TMIN/PWID/NWID/DUTY/NDUTY/WID/NBWID/DELAY/
    TIMEL/RISE/FALL/RISE20T90/FALL80T20/CCJ/PAREA/NAREA/AREA/ABSAREA/
    CYCLES/REDGES/FEDGES/EDGES/PPULSES/NPULSES/PACArea/NACArea/ACArea/ABSACArea。
    无有效读数（如无信号测频率）会在超时后返回 device_error。"""
    return _call("SDS", lambda: _sds(resource),
                 lambda s: s.measure_simple(item, f"C{ch}"))


@mcp.tool()
def sds_measure_phase(src_a: str = "C2", src_b: str = "C1",
                      resource: str | None = None) -> str:
    """SDS 双通道相位差（度）= B 相对 A 的相位（A/B 第一个上升沿中值点间）。
    用后自动关闭占用槽并恢复测量模式。用前请确认两通道完整周期在屏内
    （否则无有效值返回 device_error）。2026-09-08 实测：A=C2/B=C1 得 94.664°，
    交换后 265.218°（互补，符号约定验证通过）。"""
    def fn(s: SDS):
        prev_mode = s.meas_mode()
        slot = None
        try:
            r = s.measure_phase(src_a.upper(), src_b.upper())
            slot = r["slot"]
            return r
        finally:
            try:
                if slot is not None:
                    s.adv_slot(slot, False)
                if prev_mode:
                    s.meas_mode(prev_mode)
            except Exception:
                pass
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_meas_threshold(source: str | None = None, thr_type: str | None = None,
                       absolute: str | None = None, percent: str | None = None,
                       resource: str | None = None) -> str:
    """SDS 测量阈值配置/查询（手册 p.183-185）——所有边沿类测量的判据基础。

    source: 阈值源（C1-C4/F1/M1/REF A-D…）；thr_type: PERCent|ABSolute；
    absolute: "high,mid,low" 绝对阈值（V，如 "3,1,-1.5"）；
    percent: "high,mid,low" 百分比（整型，high∈[3,99]/mid∈[2,98]/low∈[1,97]）。
    全部省略 = 查询当前配置。绝对阈值取决于档位/位移/探头系数，设置前先设好。
    """
    def fn(s: SDS):
        out: dict = {}
        if source is not None:
            s.meas_threshold_source(source)
            out["source"] = s.meas_threshold_source()
        if thr_type is not None:
            s.meas_threshold_type(thr_type)
            out["type"] = s.meas_threshold_type()
        if absolute is not None:
            h, m, low = [float(x) for x in absolute.split(",")]
            s.meas_threshold_absolute(h, m, low)
            out["absolute"] = s.meas_threshold_absolute()
        if percent is not None:
            h, m, low = [int(x) for x in percent.split(",")]
            s.meas_threshold_percent(h, m, low)
            out["percent"] = s.meas_threshold_percent()
        if not out:
            out = {
                "source": s.meas_threshold_source(),
                "type": s.meas_threshold_type(),
                "absolute": s.meas_threshold_absolute(),
                "percent": s.meas_threshold_percent(),
            }
        return out
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_meas_gate(on: bool | None = None, ga: float | None = None,
                  gb: float | None = None, resource: str | None = None) -> str:
    """SDS 测量门限（手册 p.179-180）：只统计 GA~GB 窗口内的波形。

    on: 门限开关；ga/gb: 门限位置（秒，相对触发的水平位置，ga≤gb）。
    全部省略 = 查询当前门限开关与位置。
    """
    def fn(s: SDS):
        out: dict = {}
        if on is not None:
            s.meas_gate(on)
            out["gate_on"] = s.meas_gate()
        if ga is not None or gb is not None:
            s.meas_gate_pos(ga, gb)
            out["position"] = s.meas_gate_pos()
        if not out:
            out = {"gate_on": s.meas_gate(), "position": s.meas_gate_pos()}
        return out
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_meas_statistics(on: bool | None = None, max_count: int | None = None,
                        histogram: bool | None = None, reset: bool = False,
                        slot: int | None = None, which: str = "ALL",
                        resource: str | None = None) -> str:
    """SDS 高级测量统计（手册 p.166-174）。

    配置：on=统计开关；max_count=最大统计次数 [0,1024]（0=无限，有限制时
    历史统计才有效）；histogram=直方图开关；reset=True 重置统计结果。
    查询：给 slot（P1-P12）则返回该槽统计，which=ALL|CURRent|MEAN|MAXimum|
    MINimum|STDev|COUNt（ALL 返回完整串）。
    全省略 = 返回统计配置。
    """
    def fn(s: SDS):
        out: dict = {}
        if on is not None:
            s.meas_statistics(on)
            out["statistics_on"] = s.meas_statistics()
        if max_count is not None:
            s.meas_stat_max_count(max_count)
            out["max_count"] = s.meas_stat_max_count()
        if histogram is not None:
            s.meas_stat_histogram(histogram)
            out["histogram"] = s.meas_stat_histogram()
        if reset:
            s.meas_stat_reset()
            out["reset"] = True
        if slot is not None:
            out["slot"] = slot
            out["value"] = s.adv_statistics(slot, which)
        if not out:
            out = {
                "statistics_on": s.meas_statistics(),
                "max_count": s.meas_stat_max_count(),
                "histogram": s.meas_stat_histogram(),
            }
        return out
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_meas_dtime(index: int = 1, edge1: int | None = None,
                   edge2: int | None = None, slope1: str | None = None,
                   slope2: str | None = None, threshold1: float | None = None,
                   threshold2: float | None = None, resource: str | None = None) -> str:
    """SDS 延迟测量（ΔTime）配置/查询（手册 p.176-178）。index=1-4。

    edge1/edge2: 沿序号（-1=最后一个沿）；slope1/slope2: POSitive|NEGative；
    threshold1/threshold2: 沿阈值（V 或百分比，依测量阈值类型）。
    全省略 = 查询该 ΔTime 的六项配置。
    """
    def fn(s: SDS):
        kwargs = {}
        if edge1 is not None:
            kwargs["edge1"] = edge1
        if edge2 is not None:
            kwargs["edge2"] = edge2
        if slope1 is not None:
            kwargs["slope1"] = slope1
        if slope2 is not None:
            kwargs["slope2"] = slope2
        if threshold1 is not None:
            kwargs["threshold1"] = threshold1
        if threshold2 is not None:
            kwargs["threshold2"] = threshold2
        return s.dtime_config(index, **kwargs)
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_meas_display(rdisplay: str | None = None, style: str | None = None,
                     linenumber: int | None = None, strategy: str | None = None,
                     astra_base: str | None = None, astra_top: str | None = None,
                     resource: str | None = None) -> str:
    """SDS 测量显示与幅值策略（手册 p.174-181）。

    rdisplay: 结果显示样式 EMBedded（内嵌压缩波形）|FLOating（悬浮）；
    style: 统计显示模式 M1（垂直，含直方图）|M2（水平）；
    linenumber: M2 模式显示测量项总数 [1,12]；
    strategy: 幅值计算策略 AUTO|MANual；
    astra_base/astra_top: 手动策略的底端/顶端方式 HISTogram|MAX。
    全省略 = 查询当前全部设置。
    """
    def fn(s: SDS):
        out: dict = {}
        if rdisplay is not None:
            s.meas_result_display(rdisplay)
            out["rdisplay"] = s.meas_result_display()
        if style is not None:
            s.adv_style(style)
            out["style"] = s.adv_style()
        if linenumber is not None:
            s.adv_line_number(linenumber)
            out["linenumber"] = s.adv_line_number()
        if strategy is not None:
            s.amp_strategy(strategy)
            out["strategy"] = s.amp_strategy()
        if astra_base is not None or astra_top is not None:
            s.amp_strategy_base_top(astra_base, astra_top)
            out["base_top"] = s.amp_strategy_base_top()
        if not out:
            out = {
                "rdisplay": s.meas_result_display(),
                "style": s.adv_style(),
                "linenumber": s.adv_line_number(),
                "strategy": s.amp_strategy(),
                "base_top": s.amp_strategy_base_top(),
            }
        return out
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_get_waveform(ch: int = 2, points: int = 50000, save_csv: bool = False,
                     resource: str | None = None) -> str:
    """SDS 读取通道波形数据（电压 + 时间轴，2026-09-09 经 FFT 交叉验证可信）。

    ch=1-4；points 读取点数（默认 50000，受设备 ACQ:POIN? 上限约束；过大很慢）。
    save_csv=True 时存 CSV 到 TEST_DATA/common/ 并返回路径。
    为避免上下文爆炸，返回**摘要**（点数/时间窗/Vpp/interval/档位）+ 可选 CSV 路径，
    不返回完整数组；需要逐点数据请开 save_csv。

    时间轴可信性依据：interval 与 ACQ:SRAT? 一致，FFT 主频与设备硬件测量吻合
    （注意：分析频率请用 FFT，朴素过零对调幅信号会误判）。
    """
    def fn(s: SDS):
        wf = s.get_waveform(ch, points=points)
        vs = wf["v"]
        out = {
            "ch": ch,
            "points": wf["points"],
            "interval_s": wf["interval_s"],
            "vdiv_v": wf["vdiv_v"],
            "adc_bit": wf["adc_bit"],
            "v_min": min(vs),
            "v_max": max(vs),
            "vpp": max(vs) - min(vs),
            "t_start_s": wf["t"][0],
            "t_end_s": wf["t"][-1],
        }
        if save_csv:
            from datetime import datetime
            p = Path(ROOT) / "TEST_DATA" / "common" / (
                f"mcp_sds_wave_ch{ch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["time_s", "voltage_v"])
                w.writerows(zip(wf["t"], wf["v"]))
            out["csv"] = str(p)
        return out
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_screenshot(resource: str | None = None) -> str:
    """SDS 截屏并保存 PNG，返回文件路径——**该 PNG 可直接用 Read 工具查看**（AI
    视觉判断波形形态/削顶/居中/菜单状态/光标/测量栏）。2026-09-09 修复
    BMP alpha=0 致全透明问题（存前 convert('RGB')）。

    用途：设备测量值超屏时被钳制在屏界不可信，截图是"有无波形/是否削顶"的
    物理真相；也可核对面板菜单/光标/测量栏等 SCPI 不便读取的信息。
    无视觉能力时用库的 analyze_screen() 做像素分析兜底。"""
    def fn(s: SDS):
        from datetime import datetime
        p = Path(ROOT) / "TEST_DATA" / "common" / (
            f"mcp_sds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        saved = s.screenshot_png(p)
        return {"png": str(saved), "hint": "直接 Read 该 PNG 即可看图"}
    return _call("SDS", lambda: _sds(resource), fn)


@mcp.tool()
def sds_diagnose(resource: str | None = None) -> str:
    """SDS 触发链路诊断：模式/状态/源/电平/时基（无波形时第一步）。"""
    return _call("SDS", lambda: _sds(resource), lambda s: s.diagnose_trigger())


@mcp.tool()
def sds_shutdown(confirm: bool, resource: str | None = None) -> str:
    """SDS 远程关机。⚠ 破坏性：设备离线需面板手动开机。必须 confirm=True。"""
    if not confirm:
        return _err("confirm_required", "关机需 confirm=True（设备将离线，需手动开机）", "SDS")

    def fn(s: SDS):
        # 设备可能立即断开导致 write 抛 VisaIOError，但关机已生效——区分记录
        try:
            s.shutdown(confirm=True)
            return {"sent": True, "delivered": True, "note": "命令已确认送达"}
        except Exception as e:
            # 断开类异常（写后连接断）视为已送达；其他异常标记未确认
            return {"sent": True, "delivered": False,
                    "note": f"命令已发送但结果未确认: {type(e).__name__}"}

    # 关闭走 _call 默认路径（finally 已 try/except 兜底，关机后断连的 close 异常被吞）
    return _call("SDS", lambda: _sds(resource), fn)


# ============ SDG 信号源 ============

@mcp.tool()
def sdg_status(resource: str | None = None) -> str:
    """SDG 信号源快照：输出状态/波形参数/调制（两通道）。"""
    return _call("SDG", lambda: _sdg(resource), lambda g: g.snapshot())


@mcp.tool()
def sdg_set_wave(ch: int, wvtp: str, freq_hz: float, amp_v: float,
                 offset_v: float = 0.0, resource: str | None = None) -> str:
    """SDG 设置通道 ch(1-2) 波形参数。wvtp: SINE/SQUARE/RAMP/PULSE/NOISE/DC；
    freq_hz 单位 Hz；amp_v 单位 V（高阻负载下即 Vpp）；offset_v 单位 V。
    注意：不改变输出开关状态；输出开启时参数实时生效。返回含设备回读。"""
    def fn(g: SDG):
        r = g.set_basic_wave(
            ch, WVTP=wvtp.upper(), FRQ=f"{freq_hz:g}HZ",
            AMP=f"{amp_v:g}V", OFST=f"{offset_v:g}V",
        )
        time.sleep(0.2)
        err = g.system_error()
        return {"set": True, "error": err, "readback": g.basic_wave(ch)}
    return _call("SDG", lambda: _sdg(resource), fn)


@mcp.tool()
def sdg_counter(on: bool | None = None, resource: str | None = None) -> str:
    """SDG 内置频率计（FCNT，手册 §3.24）。on=None 仅查询；True/False 先开关再查。

    返回 STATE/FRQ/PW/NW/DUTY/FRQDEV/REFQ/TRG/MODE/HFR/TYPE。
    ⚠ 命令集因系列而异：SDG2000X 用 FCNT（本机实测），SDG7000A 才用
    `:SENSe:COUNTer:*`。输入口无信号时 FRQ=0HZ（正常）。
    """
    return _call("SDG", lambda: _sdg(resource), lambda g: g.counter(on))


@mcp.tool()
def sdg_output(ch: int, on: bool, expect_load: str, confirm: bool = False,
               resource: str | None = None) -> str:
    """SDG 开关通道 ch(1-2) 输出。⚠ 开/关都需 confirm=True（关闭可能打断
    正在进行的测试或他人实验，同样是状态变更）。

    **expect_load 必填**：调用方声明的当前负载设置（HZ=高阻 / 50=50Ω），
    仅校验不设置——与实际不符立即拒绝并回传实际值。SDG 的 AMP 设定与负载
    强相关（HZ 下即 Vpp，50Ω 下实际幅度减半），输出前必须声明避免误判。
    建议先 sdg_status 查看。
    """
    if not confirm:
        return _err("confirm_required",
                    f"输出开关（{'ON' if on else 'OFF'}）需 confirm=True——"
                    f"关闭同样可能打断正在进行的测试/实验", "SDG")

    def fn(g: SDG):
        g.set_output(ch, on, expect_load)
        time.sleep(0.3)
        return g.output_state(ch)

    return _call("SDG", lambda: _sdg(resource), fn)


# ============ Keysight 34465A ============

@mcp.tool()
def dmm_measure(function: str, resource: str | None = None) -> str:
    """34465A 单次测量。function: volt_dc/volt_ac/curr_dc/curr_ac/res/fres/
    cont/cap/diod/freq。"""
    return _call("DMM", lambda: _dmm(resource), lambda d: d.measure(function))


@mcp.tool()
def dmm_status(resource: str | None = None) -> str:
    """34465A 快照：IDN/选件/配置/最近读数。"""
    return _call("DMM", lambda: _dmm(resource), lambda d: d.snapshot())


@mcp.tool()
def dmm_configure(function: str, range_v: float | None = None,
                  resolution: float | None = None,
                  resource: str | None = None) -> str:
    """34465A 配置测量功能/量程/分辨率（不触发测量）。function: volt_dc/
    volt_ac/curr_dc/curr_ac/res/fres/cap/freq；range_v/resolution 可选。
    注意 :CONF? 回读有滞后一拍特性，以实测值为准。"""
    return _call("DMM", lambda: _dmm(resource),
                 lambda d: (d.configure(function, range_v, resolution),
                            d.configuration())[1])


@mcp.tool()
def dmm_nplc(value: float | None = None, resource: str | None = None) -> str:
    """34465A 电压 DC 积分时间 NPLC（手册 [SENSe:]VOLTage[:DC]:NPLC）。

    value=None 查询；给出则设置后回读。取值 0.02/0.2/1/10/100（默认 10）——
    越大越准越慢。注意：NPLC 与 APERture 互斥（设孔径会把 NPLC 置 0）。
    """
    def fn(d):
        if value is None:
            return {"nplc": d.get_nplc()}
        d.set_nplc(value)
        time.sleep(0.2)
        return {"nplc": d.get_nplc()}
    return _call("DMM", lambda: _dmm(resource), fn)


# ============ DHO 示波器 ============

@mcp.tool()
def dho_status(resource: str | None = None) -> str:
    """DHO 示波器只读快照（通道/时基/触发/采集）。"""
    return _call("DHO", lambda: _dho(resource), lambda s: s.snapshot())


@mcp.tool()
def dho_measure_item(item: str, ch: int = 1, resource: str | None = None) -> str:
    """DHO 单次测量查询。item 枚举（RIGOL 表）: VPP/VMAX/VMIN/VAMP/VAVG/VRMS/
    PERiod/FREQuency/PWIDth/NWIDth/PDUTy/RTIMe/FTIMe 等；ch=1-4。
    无有效测量（如通道无信号）报 param_validation 错误，文案含 9.9E37。"""
    return _call("DHO", lambda: _dho(resource), lambda s: s.measure_item(item, ch))


# ============ MHO 示波器（RIGOL MHO900 系列，实测基准 MHO984D） ============

@mcp.tool()
def mho_status(resource: str | None = None) -> str:
    """MHO 示波器只读快照：IDN/SCPI 版本/触发状态与类型/采集方式/存储深度/采样率/
    时基/边沿触发源与电平/CH1-4 开关·耦合·档位·偏移·探头比。
    注意本系列采样率随开启通道数下降（1~2ch 4GSa/s、3~4ch 1GSa/s）。"""
    return _call("MHO", lambda: _mho(resource), lambda s: s.snapshot())


@mcp.tool()
def mho_measure_item(item: str, ch: int = 1, ch2: int | None = None,
                     resource: str | None = None) -> str:
    """MHO 单次测量查询（手册 3.17.2 参数表）。

    单信源 item: VMAX/VMIN/VPP/VTOP/VBASe/VAMP/VAVG/VRMS/OVERshoot/PREShoot/
    MARea/MPARea/PERiod/FREQuency/RTIMe/FTIMe/PWIDth/NWIDth/PDUTy/NDUTy/
    TVMAX/TVMIN/PSLewrate/NSLewrate/VUPPer/VMID/VLOWer/PVRMs/PPULses/NPULses/
    PEDGes/NEDGes/ACRMs；ch=1-4。
    双信源 item（需同时给 ch2）: RRDelay/RFDelay/FRDelay/FFDelay（延迟）、
    RRPHase/RFPHase/FRPHase/FFPHase（相位，四组合=先 A 后 B 的沿型）。
    无有效读数（如无信号测周期）报 device_error/param_validation，文案含 9.9E37。
    ⚠ 信号超屏时读数被钳制在屏界不可信——形态判断请用 mho_screenshot 看图。"""
    return _call("MHO", lambda: _mho(resource),
                 lambda s: {"item": item, "value": s.measure_item(item, ch, ch2)})


@mcp.tool()
def mho_screenshot(resource: str | None = None) -> str:
    """MHO 截屏并保存 PNG，返回文件路径——**该 PNG 可直接用 Read 工具查看**
    （波形形态/有无信号/削顶/居中/菜单/测量栏/网络配置）。

    RIGOL 原生回 PNG 位图流（`:DISPlay:DATA? PNG`），无需像 SDS 那样解析 BMP。
    设备测量值超屏时被钳制不可信，截图才是物理真相（AGENTS.md 铁律#9）。"""
    def fn(s: MHO):
        p = Path(ROOT) / "TEST_DATA" / "mho" / (
            f"mcp_mho_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        saved = s.screenshot_png(p)
        return {"png": str(saved), "hint": "直接 Read 该 PNG 即可看图"}
    return _call("MHO", lambda: _mho(resource), fn)


@mcp.tool()
def mho_get_waveform(ch: int = 1, points: int = 1000, mode: str = "NORMal",
                     fmt: str = "BYTE", save_csv: bool = False,
                     resource: str | None = None) -> str:
    """MHO 读取通道波形（电压 + 时间轴），返回**摘要** + 可选 CSV 路径。

    mode: NORMal=屏幕波形（**1~1000 点**，手册 3.28.4）/ MAXimum / RAW=内存波形
    （RAW 要求示波器处于 STOP 态，否则报 device_error 并提示先 mho_acquisition("stop")）；
    fmt: BYTE(8bit)/WORD(16bit)/ASCii；points 受模式上限约束（超限报 param_validation）。
    save_csv=True 存 CSV 到 TEST_DATA/mho/ 并返回路径（不返回完整数组防上下文爆炸）。
    电压换算 (raw-YORigin-YREFerence)*YINCrement，时间轴 xorigin+i*xincrement，
    与 :MEASure:ITEM? 交叉验证一致；分析频率请用 FFT（朴素过零对调幅信号会误判）。"""
    def fn(s: MHO):
        wf = s.get_waveform(ch, mode=mode, fmt=fmt, points=points)
        vs = wf["v"]
        out = {
            "ch": ch, "mode": wf["mode"], "format": wf["format"],
            "points": wf["points"], "xinc_s": wf["xinc"], "xorigin_s": wf["xorigin"],
            "v_min": min(vs), "v_max": max(vs), "vpp": max(vs) - min(vs),
            "t_start_s": wf["t"][0], "t_end_s": wf["t"][-1],
        }
        if save_csv:
            p = Path(ROOT) / "TEST_DATA" / "mho" / (
                f"mcp_mho_wave_ch{ch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["time_s", "voltage_v"])
                w.writerows(zip(wf["t"], wf["v"]))
            out["csv"] = str(p)
        return out
    return _call("MHO", lambda: _mho(resource), fn)


@mcp.tool()
def mho_acquisition(action: str, resource: str | None = None) -> str:
    """MHO 采集控制：action ∈ run（连续采集）/ stop（冻结，**RAW 读内存波形前必须**）/
    single（单次触发）/ force（强制触发一次）。

    ⚠ stop 会冻结当前采集——共享实验台上可能打断他人的观察；run/single/force 同理
    会改变采集状态。仅改采集状态，不动通道档位/时基/触发配置。
    返回 {"action", "trigger_status"}（设备回读）。"""
    act = action.strip().lower()
    if act not in ("run", "stop", "single", "force"):
        return _err("param_validation",
                    f"未知 action {action!r}（run|stop|single|force）", "MHO")

    def fn(s: MHO):
        {"run": s.run, "stop": s.stop,
         "single": s.single, "force": s.force_trigger}[act]()
        time.sleep(0.3)
        return {"action": act, "trigger_status": s.trigger_status()}
    return _call("MHO", lambda: _mho(resource), fn)


@mcp.tool()
def mho_autoset(confirm: bool = False, resource: str | None = None) -> str:
    """MHO 一键自动设置 `:AUToset`（手册 3.2.1）。⚠ **全局破坏性**：会重新调整
    **所有**通道的垂直档位、水平时基与触发配置——多信号实验台上会毁掉别人已调好的
    通道。必须 confirm=True；且确认"信号简单周期性 + 无其他在用通道"再用。
    无波形时的推荐顺序：先 mho_status / mho_screenshot 看真相，再决定是否 autoset。"""
    if not confirm:
        return _err("confirm_required",
                    ":AUToset 会重置所有通道档位/时基/触发（全局破坏性），需 confirm=True",
                    "MHO")

    def fn(s: MHO):
        s.autoset()
        time.sleep(2.5)
        return {"autoset": True, "trigger_status": s.trigger_status(),
                "timebase_s_div": s.timebase_scale()}
    return _call("MHO", lambda: _mho(resource), fn)


# ============ DG832 信号源（RIGOL DG800 系列；2026-09-15 由独立 instrument 服务器并入） ============
#
# 库：dg832_control（唯一维护点）。该库自带两套**硬件保护**，并入时原样保留：
#   ① protect 联锁：设幅度/偏移或开输出前必须已开启有效电压保护，否则 protect_required；
#   ② DC 切换快照：set_dc_only 返回切换前配置，切回时要求显式传参（不做隐式恢复）。
# 仓库侧新增的只有 dg_output 的 confirm 门（AGENTS.md 红线：开关输出需授权）。

@mcp.tool()
def dg_status(model: str | None = None, resource: str | None = None) -> str:
    """DG832 快照：设备信息（型号/序列号/固件）+ CH1/CH2 当前波形配置（波形/频率/
    幅度/偏移/相位）、输出开关、负载。**动这台之前先查它**。

    model: 同族型号可选（DG811/812/821/822/831/832 同命令集，省略默认 DG832；
    未登记型号返回 model_unsupported）。"""
    return _call("DG832", lambda: _dg(resource, model), lambda g: g.status())


@mcp.tool()
def dg_protect(ch: int, high: float | None = None, low: float | None = None,
               state: bool | None = None, model: str | None = None,
               resource: str | None = None) -> str:
    """DG832 输出电压保护（防超压）：设上限/下限（V）与开关。

    ⚠ **强制流程**：设置幅度/偏移（`dg_set_wave`/`dg_set_param` 的 amp/offset）或打开输出
    （`dg_output` on）之前，必须先用本工具开启有效保护（`state=True` 且 `high>low`），
    否则返回 `protect_required` 被拒；保护开启后越界设置返回 `protect_range`，
    不会静默超压。省略的参数保持当前值；全省略 = 仅查询。
    """
    return _call("DG832", lambda: _dg(resource, model),
                 lambda g: g.set_voltage_limit(ch, high=high, low=low, state=state))


@mcp.tool()
def dg_get_protect(ch: int, model: str | None = None,
                   resource: str | None = None) -> str:
    """DG832 查询指定通道的电压保护配置（开关/上限/下限）。"""
    return _call("DG832", lambda: _dg(resource, model),
                 lambda g: g.get_voltage_limit(ch))


@mcp.tool()
def dg_set_wave(ch: int, shape: str, freq: float | None = None, amp: float | None = None,
                offset: float | None = None, phase: float | None = None,
                sample_rate: float | None = None, model: str | None = None,
                resource: str | None = None) -> str:
    """DG832 快速设置波形（多参数一条 `:APPL` 命令）。ch=1-2。

    shape: sine/square/ramp/pulse/dc/noise/prbs/user(任意波)/harmonic/dualtone/rs232/sequence；
    freq(Hz) / amp(Vpp) / offset(Vdc) / phase(°0-360)；sequence 波首个参数是采样率 sample_rate。
    省略的参数**保持当前值**（先读当前配置填充，不会重置为默认）。
    ⚠ 设 amp/offset 前需已开保护（见 dg_protect），否则 protect_required。
    本工具**不改变输出开关状态**。"""
    return _call("DG832", lambda: _dg(resource, model),
                 lambda g: g.set_wave(ch, shape, freq, amp, offset, phase, sample_rate))


@mcp.tool()
def dg_set_param(ch: int, param: str, value: str, model: str | None = None,
                 resource: str | None = None) -> str:
    """DG832 单参数设置并读回。param: freq(Hz)/amp(Vpp)/offset(Vdc)/phase(°)/load(Ω，inf=高阻)。
    amp/offset 会做电压保护范围校验（需先开保护）。设备静默钳制时返回体 note 会提示。"""
    def fn(g):
        p = param.strip().lower()
        if p == "freq":
            return g.set_freq(ch, float(value))
        if p == "amp":
            return g.set_amp(ch, float(value))
        if p == "offset":
            return g.set_offset(ch, float(value))
        if p == "phase":
            return g.set_phase(ch, float(value))
        if p == "load":
            return g.set_load(ch, value if value.strip().lower() == "inf" else float(value))
        raise ValueError("param 必须是 freq/amp/offset/phase/load")
    return _call("DG832", lambda: _dg(resource, model), fn)


@mcp.tool()
def dg_set_dc(ch: int, level: float, model: str | None = None,
              resource: str | None = None) -> str:
    """DG832 DC 专用切换：设直流电平（V）并返回切换前配置快照（restore: shape/freq/amp/
    offset/phase）。已在 DC 时只改电平、restore 为 None。
    切回非 DC 时请用 restore 值**显式**传参（库不做隐式恢复，避免非预期写入）。"""
    return _call("DG832", lambda: _dg(resource, model),
                 lambda g: g.set_dc_only(ch, level))


@mcp.tool()
def dg_sweep(ch: int, start: float | None = None, stop: float | None = None,
             time: float | None = None, spacing: str | None = None,
             step: int | None = None, htime_start: float | None = None,
             htime_stop: float | None = None, rtime: float | None = None,
             trig_source: str | None = None, state: bool | None = None,
             model: str | None = None, resource: str | None = None) -> str:
    """DG832 频率扫频配置/开关/查询。全省略且 state=None = 仅查询当前配置。

    start/stop(Hz，双向皆可，须在当前波形频率上限内)；time(s，1ms~500s)；
    spacing: lin/log/step；step(2~1024，仅 step 间隔)；
    htime_start/htime_stop/rtime(s)；trig_source: int/ext/man；
    state: True=开启（设备会自动关闭调制/脉冲串）/False=关闭/None=不改。
    仅 sine/square/ramp/user 支持扫频。"""
    return _call("DG832", lambda: _dg(resource, model),
                 lambda g: g.set_sweep(ch, start, stop, time, spacing, step,
                                       htime_start, htime_stop, rtime, trig_source, state))


@mcp.tool()
def dg_sweep_trigger(ch: int, model: str | None = None,
                     resource: str | None = None) -> str:
    """DG832 手动触发一次扫频（需触发源为 manual 且该通道输出已打开）。"""
    return _call("DG832", lambda: _dg(resource, model), lambda g: g.sweep_trigger(ch))


@mcp.tool()
def dg_output(ch: int, on: bool, confirm: bool = False, model: str | None = None,
              resource: str | None = None) -> str:
    """DG832 开关通道 ch(1-2) 输出。⚠ **开/关都需 confirm=True**——关断同样可能打断
    正在进行的测试或他人实验（授权语义与 `sdg_output`/`psu_output` 一致）。

    打开前需已开启有效电压保护（见 `dg_protect`），否则被拒（库内联锁）。
    建议先 `dg_status` 查当前输出状态与负载。"""
    if not confirm:
        return _err("confirm_required",
                    f"输出开关（{'ON' if on else 'OFF'}）需 confirm=True——"
                    f"关闭同样可能打断正在进行的测试/实验", "DG832")
    return _call("DG832", lambda: _dg(resource, model), lambda g: g.output(ch, on))


@mcp.tool()
def dg_counter(model: str | None = None, resource: str | None = None) -> str:
    """DG832 内置频率计测量（面板 [Counter] 输入口信号），返回频率等读数。"""
    def fn(g):
        g.counter_on(True)
        return g.counter_measure(timeout=2.0)
    return _call("DG832", lambda: _dg(resource, model), fn)


@mcp.tool()
def dg_query(scpi: str, model: str | None = None, resource: str | None = None) -> str:
    """DG832 只读 SCPI 查询（如 `:SOUR1:APPL?`、`:OUTP1?`、`:MEASure:ITEM? VPP,CHANnel1`）。
    整条必须是纯查询——判据同 instr_query：每条 `;` 分段的**命令头带 '?'** 即可，
    **问号后允许带参数**；写命令（头里无 '?'）与复位/锁定类一律拒绝。"""
    cmd = scpi.strip()
    if not _is_query_only(cmd) or _is_forbidden(cmd):
        return _err("param_validation" if "?" not in cmd else "forbidden",
                    f"dg_query 只接受纯查询消息（问号后可以带参数；不得含写命令/复位/锁定类）: {scpi!r}",
                    "DG832")
    return _call("DG832", lambda: _dg(resource, model), lambda g: g.query(cmd))


@mcp.tool()
def dg_check_error(model: str | None = None, resource: str | None = None) -> str:
    """DG832 查询并清空设备错误队列（空列表 = 正常）。命令疑似被拒后用它诊断。"""
    def fn(g):
        errs = g.check_error()
        return errs or []
    return _call("DG832", lambda: _dg(resource, model), fn)


# ============ DH1766 电源 ============

@mcp.tool()
def psu_status(resource: str | None = None) -> str:
    """DH1766 只读状态总览（**操作电源前先调这个**）：三路(CH1-3)电压/电流/功率/
    设定值/OVP/OCP/输出状态/**输出模式**/耦合，并附**安全检查**：
    safe + warnings（TRAC 负压跟随 / OVP·OCP ≤ 设定值 / 已有通道带电 /
    QUES 寄存器告警 / 通道耦合）。
    （原 psu_measure 的电压电流读数已并入本工具，原 psu_pre_check 的安全判断
    亦并入 warnings。）"""
    def fn(p):
        snap = p.snapshot()
        check = p.pre_power_check()
        return {"state": snap, "safe": check["safe"], "warnings": check["warnings"]}
    return _call("DH1766", lambda: _psu_connect(resource), fn, close_fn=_psu_close)


@mcp.tool()
def psu_mode(resource: str | None = None) -> str:
    """DH1766 输出模式查询（只读，轻量）：NORM（正常三路独立）/TRAC（跟踪：
    CH2 跟随 CH1 输出同等值负电压）/SERI（串联）/PARA（并联）。
    操作电源前先查模式——CH2 负压是跟踪模式跟随，不是固定负轨（手册§3.8）。
    需要完整状态用 psu_status。"""
    return _call("DH1766", lambda: _psu_connect(resource),
                 lambda p: {"output_mode": p.output_mode()},
                 close_fn=_psu_close)


@mcp.tool()
def psu_output(ch: int, on: bool, expect_mode: str, confirm: bool = False,
               resource: str | None = None) -> str:
    """DH1766 单通道输出开关。⚠ 开/关都需 confirm=True（关闭可能中断供电，
    影响被测电路/他人实验，同样是状态变更）。

    **expect_mode 必填**：调用方声明的当前工作模式（NORM/TRAC/SERI/PARA），
    仅校验不设置——与实际不符立即拒绝并回传当前模式（防拓扑误判：TRAC 下
    CH2 跟随 CH1 输出负压、SERI/PARA 通道合并）。建议先调 psu_status。
    """
    if not confirm:
        return _err("confirm_required",
                    f"输出开关（{'ON' if on else 'OFF'}）需 confirm=True——"
                    f"关闭可能中断供电影响被测电路", "DH1766")

    def fn(p):
        p.set_output(ch, on, expect_mode)
        time.sleep(0.3)
        return {"output_on": p.get_output_state(), "output_mode": p.output_mode()}

    return _call("DH1766", lambda: _psu_connect(resource), fn,
                 close_fn=_psu_close)


@mcp.tool()
def psu_set_mode(mode: str, resource: str | None = None) -> str:
    """DH1766 设置输出模式：NORM/TRAC/SERI/PARA（写后回读比对）。
    ⚠ 继电器联动拓扑变化：输出必须全关，否则直接拒绝（库内无条件强制）。
    切换范例：跟踪 ±12V 供电用 TRAC；单路独立用 NORM。"""
    def fn(p):
        p.set_output_mode(mode)
        return {"output_mode": p.output_mode()}
    return _call("DH1766", lambda: _psu_connect(resource), fn,
                 close_fn=_psu_close)


@mcp.tool()
def psu_power_cycle(ch: int, expect_mode: str, cycles: int = 1,
                    off_delay_s: float = 1.0, on_delay_s: float = 1.0,
                    confirm: bool = False, resource: str | None = None) -> str:
    """DH1766 上下电循环：关断→延迟→开启→延迟，重复 cycles 次。

    ⚠ **需 confirm=True**——授权同 psu_output：① 用户本轮明确要求做上下电/循环，
    或 ② 用户明确声明独占使用；否则先向用户确认（可能打断他人实验/板子供电）。

    **expect_mode 必填**（仅校验，不符拒绝）。
    off_delay_s 默认 1s（需保证下电放电时调大，如实测电容残留需 ≥6s）；
    on_delay_s 默认 1s；cycles 默认 1。延迟由主机 sleep 控制，不精准，
    用于保证放电/上电时序（非精密时序）。
    返回 {"cycles","records":[每次循环延迟与电压],"after"}。
    """
    if not confirm:
        return _err("confirm_required",
                    "上下电循环需 confirm=True——授权来源：用户明确要求做上下电循环，"
                    "或用户声明独占使用；否则先确认（可能打断他人实验/板子供电）",
                    "DH1766")

    def fn(p):
        return p.power_cycle(ch, expect_mode, off_delay_s=off_delay_s,
                             on_delay_s=on_delay_s, cycles=cycles)

    return _call("DH1766", lambda: _psu_connect(resource), fn,
                 close_fn=_psu_close)


def _prewarm_visa_rm() -> None:
    """后台预热 VISA 运行时（visa32.dll 加载），历史上实测可 20s+。

    ⚠ 本线程内禁止任何 Python import（实测 2026-09-03：mcp.run() 事件循环与
    后台线程 import pyvisa 互卡死锁——线程永远停在 import 上，首个设备工具
    调用连锁冻结）。因此 import 一律在主线程模块加载期同步完成（实测 <1s），
    线程只做 ResourceManager 初始化这个纯 DLL 调用。
    """
    try:
        rm = pyvisa.ResourceManager()
        try:
            rm.close()
        except Exception:
            pass
    except Exception:
        pass
    _PREWARM_DONE.set()


# 主线程同步预热：pyvisa + 五设备库（含 numpy 等重依赖）。
# 必须先于 prewarm 线程与 mcp.run()——见 _prewarm_visa_rm 死锁注记。
import pyvisa  # noqa: E402
from common.visa_client import VisaClient  # noqa: E402
import sds_control  # noqa: E402,F401
import sdg_control  # noqa: E402,F401
import keysight_3446x  # noqa: E402,F401
import dho_control  # noqa: E402,F401
import mho_control  # noqa: E402,F401
import dg832_control  # noqa: E402,F401

threading.Thread(target=_prewarm_visa_rm, daemon=True).start()


if __name__ == "__main__":
    mcp.run()
