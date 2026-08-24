# -*- coding: utf-8 -*-
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
import sys
import json
import time
import threading
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for sub in ("dh1766_control/src",):
    sys.path.insert(0, os.path.join(ROOT, sub))

from mcp.server.fastmcp import FastMCP

from common.discovery import find_device, identify_lan, detect_cidr, probe_alive
from sds_control import SDS
from sdg_control import SDG
from keysight_3446x import DMM
from dho_control import DHO
from dh1766_control import DH1766
from dh1766_control.visa import VisaClient

mcp = FastMCP("instruments")

_DEVICE_LOCK = threading.Lock()

SDS_RES = "TCPIP0::192.168.31.220::inst0::INSTR"
SDG_RES = "TCPIP0::192.168.31.206::inst0::INSTR"
DMM_RES = "TCPIP0::192.168.31.123::inst0::INSTR"
DHO_RES = "TCPIP0::192.168.31.146::5555::SOCKET"
PSU_RES = "TCPIP0::192.168.31.144::5025::SOCKET"


def _ok(model, result):
    return json.dumps({"ok": True, "model": model, "result": result},
                      ensure_ascii=False, default=str)


def _err(error_type, msg, model=None):
    d = {"ok": False, "error_type": error_type, "error": msg}
    if model:
        d["model"] = model
    return json.dumps(d, ensure_ascii=False, default=str)


def _call(model_name, connect_fn, fn, close_fn=None):
    """统一执行：连接→操作→关闭，错误分类，全局锁串行化。

    close_fn 缺省时调 dev.close()（DH1766 无该方法，须显式传 _psu_close）。
    """
    with _DEVICE_LOCK:
        try:
            dev = connect_fn()
        except Exception as e:
            return _err("connection", f"{type(e).__name__}: {e}", model_name)
        try:
            return _ok(model_name, fn(dev))
        except ValueError as e:
            return _err("param_validation", str(e), model_name)
        except RuntimeError as e:
            return _err("device_error", str(e), model_name)
        except Exception as e:
            return _err("communication", f"{type(e).__name__}: {e}", model_name)
        finally:
            try:
                if close_fn is not None:
                    close_fn(dev)
                elif hasattr(dev, "close"):
                    dev.close()
            except Exception:
                pass



def _sds(resource: str = SDS_RES) -> SDS:
    s = SDS(resource)
    s.connect()
    return s


def _sdg(resource: str = SDG_RES) -> SDG:
    g = SDG(resource)
    g.connect()
    return g


def _dmm(resource: str = DMM_RES) -> DMM:
    d = DMM(resource)
    d.connect()
    return d


def _dho(resource: str = DHO_RES) -> DHO:
    h = DHO(resource)
    h.connect()
    return h

def _psu_connect(resource: str = PSU_RES) -> DH1766:
    """DH1766 连接（DH1766 类无 close，退出经 _psu_close 关 client）。"""
    return DH1766(VisaClient(resource, timeout_ms=5000))


def _psu_close(p: DH1766) -> None:
    if p.client is not None:
        p.client.close()


# ============ 发现 ============

@mcp.tool()
def instr_discover(cidr: str | None = None) -> str:
    """发现本机所有仪器：LAN 端口预筛 + 多协议 *IDN?。
    cidr 可选（如 '192.168.31.0/24'），默认自动探测本机 /24。"""
    import ipaddress
    import concurrent.futures as cf

    def fn(_):
        seg = cidr or detect_cidr()
        addrs = [str(h) for h in ipaddress.ip_network(seg, strict=False).hosts()]
        with cf.ThreadPoolExecutor(max_workers=128) as pool:
            alive = [a for a, ok in zip(addrs, pool.map(probe_alive, addrs)) if ok]
        lan = {}
        with cf.ThreadPoolExecutor(max_workers=32) as pool:
            for a, r in pool.map(lambda x: (x, identify_lan(x)), alive):
                if r:
                    lan[r[0]] = r[1]
        return {"cidr": seg, "candidates": alive, "instruments": lan}

    return _call("discovery", lambda: None, fn, close_fn=lambda _: None)


# ============ SDS 示波器 ============

@mcp.tool()
def sds_status(resource: str = SDS_RES) -> str:
    """SDS 示波器只读快照：IDN/采集/时基/触发/各通道档位耦合。"""
    return _call("SDS", lambda: _sds(resource), lambda s: s.snapshot())


@mcp.tool()
def sds_auto_scale(ch: int, use_autoset: bool = False, resource: str = SDS_RES) -> str:
    """SDS 自动定标让通道波形正确显示。
    use_autoset=True 为破坏性 :AUToset（重置所有通道），仅限简单周期信号且
    无其他已调好通道时显式启用；默认 SCPI 闭环只动目标通道。"""
    return _call("SDS", lambda: _sds(resource),
                 lambda s: s.auto_scale(ch, use_autoset=use_autoset))


@mcp.tool()
def sds_measure(item: str, ch: int = 4, resource: str = SDS_RES) -> str:
    """SDS 单次测量（SIMPLE 模式）。item: PKPK/MAX/MIN/RMS/FREQ/PER/PWID/DUTY 等。"""
    return _call("SDS", lambda: _sds(resource),
                 lambda s: s.measure_simple(item, f"C{ch}"))


@mcp.tool()
def sds_screenshot(resource: str = SDS_RES) -> str:
    """SDS 截屏并保存 PNG，返回路径（削顶/居中/有无波形的唯一物理真相）。"""
    def fn(s: SDS):
        from datetime import datetime
        p = Path(ROOT) / "TEST_DATA" / "common" / (
            f"mcp_sds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        saved = s.screenshot_png(p)
        return {"png": str(saved)}
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
        # 设备可能立即断开导致 write 抛 VisaIOError，但关机已生效——不视为失败
        try:
            s.shutdown(confirm=True)
            return {"sent": True, "note": "命令已确认送达"}
        except Exception as e:
            return {"sent": True, "note": f"命令已发送（设备断开: {type(e).__name__}）"}

    def close_quiet(s: SDS):
        try:
            s.close()
        except Exception:
            pass

    return _call("SDS", lambda: _sds(resource), fn, close_fn=close_quiet)


# ============ SDG 信号源 ============

@mcp.tool()
def sdg_status(resource: str = SDG_RES) -> str:
    """SDG 信号源快照：输出状态/波形参数/调制（两通道）。"""
    return _call("SDG", lambda: _sdg(resource), lambda g: g.snapshot())


@mcp.tool()
def sdg_set_wave(ch: int, wvtp: str, freq_hz: float, amp_v: float,
                 offset_v: float = 0.0, resource: str = SDG_RES) -> str:
    """SDG 设置通道波形参数（SINE/SQUARE/RAMP/PULSE/NOISE/DC）。
    注意：不改变输出开关状态；输出开启时参数实时生效。"""
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
def sdg_output(ch: int, on: bool, confirm: bool = False,
               resource: str = SDG_RES) -> str:
    """SDG 开关通道输出。⚠ on=True 输出真实信号，需 confirm=True。"""
    if on and not confirm:
        return _err("confirm_required", "开启输出需 confirm=True（真实信号输出）", "SDG")

    def fn(g: SDG):
        g.set_output(ch, on)
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
    """34465A 配置测量功能/量程/分辨率（不触发测量）。"""
    return _call("DMM", lambda: _dmm(resource),
                 lambda d: (d.configure(function, range_v, resolution),
                            d.configuration())[1])


# ============ DHO 示波器 ============

@mcp.tool()
def dho_status(resource: str = DHO_RES) -> str:
    """DHO 示波器只读快照（通道/时基/触发/采集）。"""
    return _call("DHO", lambda: _dho(resource), lambda s: s.snapshot())


@mcp.tool()
def dho_measure_item(item: str, ch: int = 1, resource: str = DHO_RES) -> str:
    """DHO 单次测量查询（:MEASure:ITEM?，34 种 item 如 VPP/FREQ/VAVG）。"""
    return _call("DHO", lambda: _dho(resource), lambda s: s.measure_item(item, ch))


# ============ DH1766 电源 ============

@mcp.tool()
def psu_status(resource: str = PSU_RES) -> str:
    """DH1766 电源只读快照：三路电压/电流/功率/设定/OVP/OCP/输出状态。"""
    return _call("DH1766", lambda: _psu_connect(resource),
                 lambda p: p.snapshot(), close_fn=_psu_close)


@mcp.tool()
def psu_measure(resource: str = PSU_RES) -> str:
    """DH1766 三路输出电压/电流回读。"""
    return _call("DH1766", lambda: _psu_connect(resource),
                 lambda p: {"voltage_v": p.measure_voltage_all(),
                            "current_a": p.measure_current_all()},
                 close_fn=_psu_close)


if __name__ == "__main__":
    mcp.run()
