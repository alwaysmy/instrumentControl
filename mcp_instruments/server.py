# -*- coding: utf-8 -*-
from __future__ import annotations

"""
instrument MCP Server — 五台仪器的统一 MCP 接口。

设备库：sds_control(示波器) / sdg_control(信号源) / keysight_3446x(万用表) /
dho_control(示波器) / dh1766_control(电源)，经 common 统一发现层。

启动: python mcp_instruments/server.py
安全约定：
    - 复位类命令不暴露；
    - 关机/输出类工具需显式 confirm=True；
    - 每次调用连接→操作→关闭（无状态）+ 全局设备锁串行化。
"""
import os
import re
import sys
import json
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

SDS_RES = "TCPIP0::192.168.31.220::inst0::INSTR"
SDG_RES = "TCPIP0::192.168.31.206::inst0::INSTR"
DMM_RES = "TCPIP0::192.168.31.123::inst0::INSTR"
DHO_RES = "TCPIP0::192.168.31.146::5555::SOCKET"
PSU_RES = "TCPIP0::192.168.31.144::5025::SOCKET"


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


def _call(model_name, connect_fn, fn, close_fn=None, resource=None):
    """统一执行：连接→操作→关闭，错误分类，全局锁串行化。

    close_fn 缺省时调 dev.close()（DH1766 无该方法，须显式传 _psu_close）。
    resource 仅通用工具传（用于错误结构区分设备模型与资源串）。
    """
    with _DEVICE_LOCK:
        try:
            dev = connect_fn()
        except Exception as e:
            return _err("connection", f"{type(e).__name__}: {e}", model_name, resource)
        try:
            return _ok(model_name, fn(dev), resource)
        except ValueError as e:
            return _err("param_validation", str(e), model_name, resource)
        except RuntimeError as e:
            return _err("device_error", str(e), model_name, resource)
        except Exception as e:
            return _err("communication", f"{type(e).__name__}: {e}", model_name, resource)
        finally:
            try:
                if close_fn is not None:
                    close_fn(dev)
                elif hasattr(dev, "close"):
                    dev.close()
            except Exception:
                pass



def _sds(resource: str = SDS_RES) -> SDS:
    from sds_control import SDS
    s = SDS(resource)
    s.connect()
    return s


def _sdg(resource: str = SDG_RES) -> SDG:
    from sdg_control import SDG
    g = SDG(resource)
    g.connect()
    return g


def _dmm(resource: str = DMM_RES) -> DMM:
    from keysight_3446x import DMM
    d = DMM(resource)
    d.connect()
    return d


def _dho(resource: str = DHO_RES) -> DHO:
    from dho_control import DHO
    h = DHO(resource)
    h.connect()
    return h

def _psu_connect(resource: str = PSU_RES) -> DH1766:
    """DH1766 连接（DH1766 类无 close，退出经 _psu_close 关 client）。"""
    from dh1766_control import DH1766
    from dh1766_control.visa import VisaClient
    return DH1766(VisaClient(resource, timeout_ms=5000))


def _psu_close(p: DH1766) -> None:
    if p.client is not None:
        p.client.close()


# ============ 发现 ============

@mcp.tool()
def instr_discover(cidr: str | None = None) -> str:
    """发现本机所有仪器。返回三部分：
    lan: 网段扫描（TCP 预筛 + 多协议 *IDN?，键=资源串 值=IDN）；
    visa: VISA 资源列表——USB/GPIB/串口均自动探测 *IDN?（串口被占用时
    返回占用提示，空闲则探测后立即断开，约 2s/口）；
    cidr: 实际使用的网段。cidr 参数可选（如 '192.168.31.0/24'），
    默认自动探测本机 /24（代理虚拟网卡环境需显式传）。"""
    import ipaddress
    import concurrent.futures as cf
    from common.discovery import (
        detect_cidr,
        identify,
        identify_lan,
        list_resources,
        probe_alive,
    )

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

        def probe_serial(r: str, rm, timeout_s: float = 6.0):
            """串口探测：被占用给提示；空闲则 *IDN? 后立即断开。

            驱动层 open 可能无限挂起（open_timeout 管不到），故串口不进并行池
            （会拖死全部 worker），单独线程 join 硬超时；挂起线程为 daemon
            随进程退出。RM 由调用方共享单例传入——每探测各建 RM 曾致原生层
            崩溃（8 串口实测 2026-09-03，进程直接死亡）。
            """
            result: dict = {}

            def work():
                try:
                    inst = rm.open_resource(r, open_timeout=2000)
                    inst.timeout = 1500
                    inst.write_termination = "\n"
                    inst.read_termination = "\n"
                    try:
                        idn = inst.query("*IDN?").strip()
                        if idn:
                            result.update(online=True, idn=idn)
                        else:
                            result.update(
                                online=False,
                                note="打开成功但无 *IDN? 响应（非 SCPI 设备或波特率不匹配）",
                            )
                    finally:
                        inst.close()
                except Exception as e:
                    if "BUSY" in str(e).upper() or getattr(e, "error_code", 0) == -1073807346:
                        result.update(online=None, note="串口被占用（其他程序打开中）")
                    else:
                        result.update(online=None, note=f"打开失败: {type(e).__name__}")

            t = threading.Thread(target=work, daemon=True)
            t.start()
            t.join(timeout_s)
            if t.is_alive():
                return {"online": None, "note": f"探测超时({timeout_s:.0f}s，驱动挂起，疑似被占用)"}
            return result

        resources = list_resources()
        non_serial = [r for r in resources if not r.upper().startswith("ASRL")]
        serial_res = [r for r in resources if r.upper().startswith("ASRL")]
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            visa = list(pool.map(probe_visa, non_serial))
        rm_serial = pyvisa.ResourceManager()
        try:
            for r in serial_res:
                entry = {"resource": r, "kind": "serial"}
                entry.update(probe_serial(r, rm_serial))
                visa.append(entry)
        finally:
            try:
                rm_serial.close()
            except Exception:
                pass

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
        out = {"cidr": seg, "lan": lan, "visa": visa}
        if warn:
            out["warning"] = warn
        return out

    return _call("discovery", lambda: None, fn, close_fn=lambda _: None)


# ============ 通用护栏 SCPI（新设备零代码接入） ============
#
# 设计取舍：不做多设备接口统一——各库专用工具承载人工筛选的语义与安全门；
# 通用工具只提供"对照手册直发命令"的护栏通道，设备用出价值后再补专用库。

# 复位/存储覆写类黑名单（AGENTS.md 安全红线）：confirm=True 也不放行——
# 需显式授权的复位场景走测试脚本（如 dh1766 --allow-rst），不经 MCP。
_FORBIDDEN_RE = re.compile(
    r"\*(RST|SAV|RCL)"  # *RST / *SAV n / *RCL n（含带参写法）
    r"|:?(SYST|SYSTEM):(RESET|RES|FACTORY|FACT|PRESET|PRES)(:|\?|$)"
    # 远程锁定类：SDS :SYSTem:REMote ON 会禁用触摸屏/面板按键（界面显示 Remote），
    # 影响人工操作——自动化一律禁止（skill instrument-mcp 明文约定）。
    # 注意：_is_forbidden 先做空白归一（"SYST:REM ON"→"SYST:REMON"），
    # 故此处不能用结尾断言，前缀匹配即可（REM 开头的 SYSTem 子命令仅远程锁定类）。
    r"|:?(SYST|SYSTEM):(REMOTE|REM|LOCK|LOCKED)"
)


def _is_forbidden(cmd: str) -> bool:
    """空白归一后匹配黑名单（兼容 SCPI 长短形式与大小写）。"""
    return bool(_FORBIDDEN_RE.search(re.sub(r"\s+", "", cmd).upper()))


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
    """带硬超时看门狗的 _call（通用工具专用）。

    实测（2026-09-03）：DMM 离线时 VXI-11 open 无视 open_timeout 挂起 2min+，
    而 VISA 全局锁会让全部后续工具连锁冻结。通用工具会指向任意发现地址
    （含离线），必须在 MCP 层兜底：connect+fn 跑 daemon 线程，join 硬超时。
    超时后挂起线程仍占用 _DEVICE_LOCK，后续调用会继续超时直至 MCP 重启——
    宁可报错也不冻死服务器。
    看门狗预算 = max(30, 12+timeout_ms)；若预热未完成（VISA 冷启动实测 30-40s，
    且工作线程 import 会被预热线程的 import 锁串行阻塞）再放宽 90s，防误杀首调用。
    """
    budget = max(30.0, 12.0 + timeout_ms / 1000.0)
    if not _PREWARM_DONE.is_set():
        budget += 90.0
    holder: dict = {}

    def work():
        holder["r"] = _call("instruments", lambda: _visa(resource, timeout_ms), fn,
                            resource=resource)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(budget)
    if t.is_alive():
        return _err("timeout",
                    f"设备 {resource} 无响应超过 {budget:.0f}s（离线/总线挂起），"
                    "已放弃本次调用；后续调用可能仍超时（挂起线程占用设备锁）",
                    "instruments", resource)
    return holder.get("r") or _err("internal", "worker 未返回结果", "instruments", resource)


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
    设备无响应有硬超时看门狗（下限 30s，覆盖 VISA 冷启动），离线资源不会冻结 MCP。"""
    if "?" not in cmd:
        return _err("param_validation", f"查询命令必须含 '?': {cmd!r}",
                    "instruments", resource)

    def fn(c):
        return {"response": c.query(cmd)}

    return _guarded_call(resource, timeout_ms, fn)


@mcp.tool()
def instr_write(resource: str, cmd: str, readback_cmd: str | None = None,
                confirm: bool = False, timeout_ms: int = 5000) -> str:
    """通用 SCPI 写——新设备零代码接入。⚠ 必须 confirm=True（raw 写权限大）。
    内置护栏（对应 AGENTS.md 铁律2/3 与安全红线）：
    1) 复位/存储覆写类（*RST/*SAV/*RCL/:SYST:RES|FACT|PRES，长短形式均拦）
       一律拒绝（error_type=forbidden，confirm 也不放行）；
    2) 写前 drain 错误队列、写后逐条排空 SYST:ERR?，返回 syst_errors；
    3) readback_cmd 给定时自动回读（铁律3），如写 'VOLT 1' 后传 'VOLT?'；
    4) 每次调用（含被拒绝的）落盘 TEST_DATA/common/mcp_scpi_audit_*.jsonl；
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
    _audit_scpi("instr_write", resource, cmd, refused=None)

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
    _audit_scpi("instr_write", resource, cmd, executed=True,
                outcome=json.loads(result))
    return result


# ============ SDS 示波器 ============

@mcp.tool()
def sds_status(resource: str = SDS_RES) -> str:
    """SDS 示波器只读快照：IDN/采集/时基/触发/各通道档位耦合。"""
    return _call("SDS", lambda: _sds(resource), lambda s: s.snapshot())


@mcp.tool()
def sds_auto_scale(ch: int, use_autoset: bool = False, resource: str = SDS_RES) -> str:
    """SDS 自动定标让通道 ch(1-4) 波形正确显示。
    use_autoset=True 为破坏性 :AUToset（重置所有通道档位/时基/触发），仅限
    简单周期信号且无其他已调好通道时显式启用；默认 SCPI 闭环只动目标通道。返回 actions/vpp/freq/adjusted。"""
    return _call("SDS", lambda: _sds(resource),
                 lambda s: s.auto_scale(ch, use_autoset=use_autoset))


@mcp.tool()
def sds_measure(item: str, ch: int = 4, resource: str = SDS_RES) -> str:
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
                      resource: str = SDS_RES) -> str:
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
                       resource: str = SDS_RES) -> str:
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
                  gb: float | None = None, resource: str = SDS_RES) -> str:
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
                        resource: str = SDS_RES) -> str:
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
                   threshold2: float | None = None, resource: str = SDS_RES) -> str:
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
                     resource: str = SDS_RES) -> str:
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
def sds_screenshot(resource: str = SDS_RES) -> str:
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
def sds_diagnose(resource: str = SDS_RES) -> str:
    """SDS 触发链路诊断：模式/状态/源/电平/时基（无波形时第一步）。"""
    return _call("SDS", lambda: _sds(resource), lambda s: s.diagnose_trigger())


@mcp.tool()
def sds_shutdown(confirm: bool, resource: str = SDS_RES) -> str:
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
def sdg_status(resource: str = SDG_RES) -> str:
    """SDG 信号源快照：输出状态/波形参数/调制（两通道）。"""
    return _call("SDG", lambda: _sdg(resource), lambda g: g.snapshot())


@mcp.tool()
def sdg_set_wave(ch: int, wvtp: str, freq_hz: float, amp_v: float,
                 offset_v: float = 0.0, resource: str = SDG_RES) -> str:
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
def sdg_counter(on: bool | None = None, resource: str = SDG_RES) -> str:
    """SDG 内置频率计（FCNT，手册 §3.24）。on=None 仅查询；True/False 先开关再查。

    返回 STATE/FRQ/PW/NW/DUTY/FRQDEV/REFQ/TRG/MODE/HFR/TYPE。
    ⚠ 命令集因系列而异：SDG2000X 用 FCNT（本机实测），SDG7000A 才用
    `:SENSe:COUNTer:*`。输入口无信号时 FRQ=0HZ（正常）。
    """
    return _call("SDG", lambda: _sdg(resource), lambda g: g.counter(on))


@mcp.tool()
def sdg_output(ch: int, on: bool, expect_load: str, confirm: bool = False,
               resource: str = SDG_RES) -> str:
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
def dmm_measure(function: str, resource: str = DMM_RES) -> str:
    """34465A 单次测量。function: volt_dc/volt_ac/curr_dc/curr_ac/res/fres/
    cont/cap/diod/freq。"""
    return _call("DMM", lambda: _dmm(resource), lambda d: d.measure(function))


@mcp.tool()
def dmm_status(resource: str = DMM_RES) -> str:
    """34465A 快照：IDN/选件/配置/最近读数。"""
    return _call("DMM", lambda: _dmm(resource), lambda d: d.snapshot())


@mcp.tool()
def dmm_configure(function: str, range_v: float | None = None,
                  resolution: float | None = None,
                  resource: str = DMM_RES) -> str:
    """34465A 配置测量功能/量程/分辨率（不触发测量）。function: volt_dc/
    volt_ac/curr_dc/curr_ac/res/fres/cap/freq；range_v/resolution 可选。
    注意 :CONF? 回读有滞后一拍特性，以实测值为准。"""
    return _call("DMM", lambda: _dmm(resource),
                 lambda d: (d.configure(function, range_v, resolution),
                            d.configuration())[1])


@mcp.tool()
def dmm_nplc(value: float | None = None, resource: str = DMM_RES) -> str:
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
def dho_status(resource: str = DHO_RES) -> str:
    """DHO 示波器只读快照（通道/时基/触发/采集）。"""
    return _call("DHO", lambda: _dho(resource), lambda s: s.snapshot())


@mcp.tool()
def dho_measure_item(item: str, ch: int = 1, resource: str = DHO_RES) -> str:
    """DHO 单次测量查询。item 枚举（RIGOL 表）: VPP/VMAX/VMIN/VAMP/VAVG/VRMS/
    PERiod/FREQuency/PWIDth/NWIDth/PDUTy/RTIMe/FTIMe 等；ch=1-4。
    无有效测量（如通道无信号）报 param_validation 错误，文案含 9.9E37。"""
    return _call("DHO", lambda: _dho(resource), lambda s: s.measure_item(item, ch))


# ============ DH1766 电源 ============

@mcp.tool()
def psu_status(resource: str = PSU_RES) -> str:
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
def psu_mode(resource: str = PSU_RES) -> str:
    """DH1766 输出模式查询（只读，轻量）：NORM（正常三路独立）/TRAC（跟踪：
    CH2 跟随 CH1 输出同等值负电压）/SERI（串联）/PARA（并联）。
    操作电源前先查模式——CH2 负压是跟踪模式跟随，不是固定负轨（手册§3.8）。
    需要完整状态用 psu_status。"""
    return _call("DH1766", lambda: _psu_connect(resource),
                 lambda p: {"output_mode": p.output_mode()},
                 close_fn=_psu_close)


@mcp.tool()
def psu_output(ch: int, on: bool, expect_mode: str, confirm: bool = False,
               resource: str = PSU_RES) -> str:
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
def psu_set_mode(mode: str, resource: str = PSU_RES) -> str:
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
                    confirm: bool = False, resource: str = PSU_RES) -> str:
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

threading.Thread(target=_prewarm_visa_rm, daemon=True).start()


if __name__ == "__main__":
    mcp.run()
