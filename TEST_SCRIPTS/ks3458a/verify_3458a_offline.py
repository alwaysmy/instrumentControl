"""3458A 专用库**离线**自测——用假传输跑驱动，**不打开任何真实仪器**。

    python TEST_SCRIPTS/ks3458a/verify_3458a_offline.py

为什么必须离线能跑：3458A 设备当前**不可达**（远端 VISA server 返回 NPERMISSION、
本机无可用 GPIB 接口库），真机验证要等设备回来（清单见
`docs/3458a_integration_20260922.md` §真机验证清单）。在此之前，所有"能离线证明"
的行为必须被断言锁住——尤其是那些**一旦写错就会静默给出错位数据**的：

    ① 通路选型（sicl:/gpib0,9 ↔ GPIB0::9::INSTR / visa://）
    ② **LF 终止符**（CRLF 会让 3458A 不应答；用假 pyvisa 断言设置结果，不开真会话）
    ③ `TARM SGL,1` 单次读数解析 / 非数值报错（**不返回 0 兜底**）
    ④ 换档/换配置后**丢弃第一次读数**（建立时间 + 自校准）
    ⑤ 档位选择 range_for（含 10V 档 20% 超量程的保守边界）
    ⑥ 二进制突发解析（2n+2 字节、2 字节大端有符号 × ISCALE、含负值与极值）
    ⑦ `ID?` 身份校验（3458A 没有 *IDN?）
    ⑧ `RESET` + `END ALWAYS` + `INBUF ON` 的写序列
    ⑨ free-run 恢复的调用顺序（IFC/clear → 有限 drain → TARM HOLD/TRIG HOLD）

留痕：`TEST_DATA/ks3458a/verify_3458a_offline_<时间戳>.json`
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from keysight_3458a import (  # noqa: E402
    DMM3458A,
    PyVisaTransport,
    SiclTransport,
    TransportError,
    candidate_resources,
    is_error_clear,
    is_sicl_resource,
    make_transport,
    parse_sicl_addr,
)
from keysight_3458a import commands as C  # noqa: E402
from keysight_3458a.transport import tmc_body, tmc_split  # noqa: E402

fails: list[str] = []
checks: list[dict] = []


def _ascii(text) -> str:
    """Force ASCII output so the console code page never matters."""
    return str(text).encode("ascii", "replace").decode("ascii")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {_ascii(name):62s} {str(detail)[:96]}", flush=True)
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------------------
# 假传输：实现与 transport.Transport 同一套接口，**不碰任何真实设备**
# ---------------------------------------------------------------------------
class FakeTransport:
    """`readings` 依次应答 `TARM SGL,1`；`responses` 按命令文本应答其它查询。

    `calls` 记录全部调用（method, arg）——顺序类断言用它，这样"先清后读"这类
    顺序错误能被抓到，而不只是看最终值对不对。
    """

    def __init__(self, readings=None, responses=None, block=None,
                 fail_writes: int = 0, fail_read_bytes: bool = False):
        self.resource = "fake:3458a"
        self.calls: list[tuple[str, object]] = []
        self.writes: list[str] = []
        self.timeout_s = 30.0
        self.opened = False
        self.closed = False
        self._readings = list(readings or [])
        self._responses = dict(responses or {})
        self._block = bytes(block or b"")
        self._fail_writes = int(fail_writes)     # 前 K 次 write 抛 TransportError（模拟"表还在流数据"）
        self._fail_read_bytes = bool(fail_read_bytes)   # read_bytes 抛错（模拟突发回读失败）

    # -- 接口 --
    def open(self):
        self.opened = True
        self.calls.append(("open", None))
        return self

    def close(self):
        self.closed = True
        self.calls.append(("close", None))

    def write(self, cmd):
        if self._fail_writes > 0:
            self._fail_writes -= 1
            self.calls.append(("write", f"FAIL:{cmd}"))
            raise TransportError(f"模拟写超时（表可能还在流数据）: {cmd}")
        self.calls.append(("write", cmd))
        self.writes.append(cmd)

    def read(self, timeout_s=None):
        self.calls.append(("read", timeout_s))
        return self._readings.pop(0) if self._readings else ""

    def read_bytes(self, count, timeout_s=None):
        self.calls.append(("read_bytes", (count, timeout_s)))
        if self._fail_read_bytes:
            raise TransportError(f"模拟突发回读失败（期望 {count} 字节）")
        return self._block[:count]

    def query(self, cmd, timeout_s=None):
        self.calls.append(("query", cmd))
        if cmd == C.TARM_SGL_1 and self._readings:
            return self._readings.pop(0)
        return self._responses.get(cmd, "")

    def clear(self):
        self.calls.append(("clear", None))

    def drain(self, max_rounds=6, timeout_ms=250):
        self.calls.append(("drain", (max_rounds, timeout_ms)))
        return 0

    def set_timeout(self, seconds):
        self.timeout_s = float(seconds)

    def ifc(self):
        self.calls.append(("ifc", None))

    # -- 断言辅助 --
    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def count(self, method: str, arg=None) -> int:
        return sum(1 for name, value in self.calls
                   if name == method and (arg is None or value == arg))


def connected(readings=None, responses=None, block=None) -> tuple[DMM3458A, FakeTransport]:
    """建一个"已连接但不做恢复"的会话（恢复单独在 §10 测）。"""
    transport = FakeTransport(readings=readings, responses=responses, block=block)
    dmm = DMM3458A(transport=transport)
    dmm.connect(recover=False)
    return dmm, transport


# ---------------------------------------------------------------------------
# 假 pyvisa：只为断言 PyVisaTransport 的设置结果，**不产生任何设备 I/O**
# ---------------------------------------------------------------------------
class _FakeInst:
    def __init__(self):
        self.timeout = 0
        self.write_termination = None
        self.read_termination = None
        self.chunk_size = 0
        self.clear_count = 0
        self.closed = False

    def clear(self):
        self.clear_count += 1

    def close(self):
        self.closed = True


class _FakeRM:
    def __init__(self):
        self.inst = _FakeInst()
        self.open_kwargs: dict = {}
        self.closed = False

    def open_resource(self, resource, **kwargs):
        self.resource = resource
        self.open_kwargs = kwargs
        return self.inst

    def close(self):
        self.closed = True


class _FakePyVisa:
    def __init__(self):
        self.rms: list[_FakeRM] = []
        self.requested_visalib: list = []       # 记录代码请求的 VISA 实现（用于断言选型）

    def ResourceManager(self, visalib=None):
        # 真代码在 GPIB 资源上会指定 Keysight VISA（ktvisa\ktbin\visa32.dll）；
        # 假实现只记录、不加载任何 DLL（离线测试绝不碰真实仪器）。
        self.requested_visalib.append(visalib)
        rm = _FakeRM()
        self.rms.append(rm)
        return rm


def main() -> int:
    print("S1 transport selection (pure functions, no device opened)", flush=True)
    check("sicl: prefix -> SICL", is_sicl_resource("sicl:gpib0,9"))
    check("gpib0,9 short form -> SICL", is_sicl_resource("gpib0,9"))
    check("GPIB0::9::INSTR -> VISA", not is_sicl_resource("GPIB0::9::INSTR"))
    check("visa://<host>/... -> VISA", not is_sicl_resource("visa://10.0.0.5/GPIB0::9::INSTR"))
    check("parse_sicl_addr handles three forms",
          parse_sicl_addr("sicl:gpib0,9") == 9
          and parse_sicl_addr("gpib0,12") == 12
          and parse_sicl_addr("GPIB0::9::INSTR") == 9,
          f"{parse_sicl_addr('sicl:gpib0,9')}/{parse_sicl_addr('gpib0,12')}"
          f"/{parse_sicl_addr('GPIB0::9::INSTR')}")
    check("make_transport picks the right backend",
          isinstance(make_transport("sicl:gpib0,9"), SiclTransport)
          and isinstance(make_transport("visa://h/GPIB0::9::INSTR"), PyVisaTransport))
    # Windows + 本机装了 Keysight VISA 时，GPIB 资源应选 KeysightVisaTransport（2026-09-23 实测）；
    # 显式关掉偏好后必须回到 pyvisa 通路。
    from keysight_3458a.transport import (KeysightVisaTransport,  # noqa: E402
                                         keysight_visa_core)
    if keysight_visa_core():
        check("GPIB 资源默认选 Keysight VISA 通路",
              isinstance(make_transport("GPIB0::9::INSTR"), KeysightVisaTransport))
        check("显式 prefer_keysight_visa=False -> PyVisaTransport",
              isinstance(make_transport("GPIB0::9::INSTR", prefer_keysight_visa=False),
                         PyVisaTransport))
    else:
        check("无 Keysight VISA 时 GPIB 回落 pyvisa（本机未装，跳过正向断言）",
              isinstance(make_transport("GPIB0::9::INSTR"), PyVisaTransport),
              "keysight_visa_core() = None")

    print("\nS2 pyvisa path: LF terminator and session setup (fake pyvisa)", flush=True)
    fake_pyvisa = _FakePyVisa()
    real_pyvisa = sys.modules.get("pyvisa")
    sys.modules["pyvisa"] = fake_pyvisa          # type: ignore[assignment]
    try:
        transport = PyVisaTransport("GPIB0::9::INSTR", timeout_s=12.0)
        transport.open()
        inst = fake_pyvisa.rms[0].inst
        check("write_termination == '\\n' (CRLF makes the 3458A mute)",
              inst.write_termination == "\n", repr(inst.write_termination))
        check("read_termination == '\\n'", inst.read_termination == "\n",
              repr(inst.read_termination))
        check("timeout converted seconds -> ms", inst.timeout == 12000, inst.timeout)
        check("clear() called once after open", inst.clear_count == 1, inst.clear_count)
        check("resource handed to pyvisa verbatim",
              fake_pyvisa.rms[0].resource == "GPIB0::9::INSTR",
              fake_pyvisa.rms[0].resource)
        transport.close()
        check("close() tears down session and RM",
              inst.closed and fake_pyvisa.rms[0].closed)
    finally:
        if real_pyvisa is not None:
            sys.modules["pyvisa"] = real_pyvisa
        else:
            sys.modules.pop("pyvisa", None)

    print("\nS3 TARM SGL,1 single-reading parsing", flush=True)
    dmm, transport = connected(readings=["+1.23456789E-03"])
    value = dmm.read_dcv()
    check("reading parsed as float", value == 1.23456789e-03, repr(value))
    check("TARM SGL,1 actually used", transport.count("query", C.TARM_SGL_1) == 1)
    dmm.close()
    check("TARM HOLD sent before close",
          transport.writes[-1] == C.TARM_HOLD, transport.writes[-1:])

    # 参考实现的语义（[SICL] L371-376）：取**最后一个** token，容忍前面的残留响应
    # （残留/错位是 3458A 现场已知问题）。3458A 的 TARM SGL,1 本身回纯数值、不带单位；
    # 真出现带单位的多 token 响应会落到§4 的"非法读数报错"分支，不静默猜值。
    dmm, _ = connected(readings=["STALE-READING 1.5"])
    check("last token wins on leftovers", dmm.read_dcv() == 1.5)
    dmm.close()

    print("\nS4 non-numeric reading must raise (no zero fallback)", flush=True)
    dmm, _ = connected(readings=["NO DATA"])
    try:
        dmm.read_dcv()
        check("non-numeric response raises", False, "no exception raised")
    except TransportError as exc:
        check("non-numeric response raises", True, str(exc)[:60])
    dmm.close()
    dmm, _ = connected(readings=[""])
    try:
        dmm.read_dcv()
        check("empty response raises", False, "no exception raised")
    except TransportError:
        check("empty response raises", True)
    dmm.close()

    print("\nS5 discard the first reading after a range/config change", flush=True)
    dmm, transport = connected(readings=["1.0", "2.0", "3.0"])
    transport.calls.clear()
    transport.writes.clear()
    dmm.configure_dcv(1.0, 10.0)
    check("config write order = DCV <range> / NPLC <n>", transport.writes == ["DCV 1", "NPLC 10"],
          transport.writes)
    check("one reading consumed and discarded after config change",
          transport.count("query", C.TARM_SGL_1) == 1)
    check("the discarded value was the first reading", dmm.read_dcv() == 2.0)
    transport.calls.clear()
    transport.writes.clear()
    dmm.set_range(1.0)
    check("no DCV re-send when the range is unchanged", transport.writes == [],
          transport.writes)
    dmm.set_range(10.0)
    check("range change writes DCV and discards first reading",
          transport.writes == ["DCV 10"] and transport.count("query", C.TARM_SGL_1) == 1,
          transport.writes)
    dmm.close()

    print("\nS6 range selection (conservative 10V overrange boundary)", flush=True)
    expect_ranges = {0.05: 0.1, 0.09: 0.1, 0.5: 1.0, 0.9: 1.0, 5.0: 10.0,
                     9.0: 10.0, 9.5: 100.0, 11.0: 100.0, 2000.0: 1000.0,
                     -5.0: 10.0}
    bad = {v: DMM3458A.range_for(v) for v, want in expect_ranges.items()
           if DMM3458A.range_for(v) != want}
    check("range_for keeps 1.1x headroom (abs of negatives)", not bad, bad or "all 10 points ok")
    check("range set = (0.1, 1, 10, 100, 1000)",
          tuple(C.DCV_RANGES) == (0.1, 1.0, 10.0, 100.0, 1000.0), str(C.DCV_RANGES))
    check("10V overrange constant = 12V (selection stays conservative)",
          C.DCV_10V_OVERLOAD_V == 12.0, C.DCV_10V_OVERLOAD_V)
    dmm, _ = connected()
    try:
        dmm.configure_dcv(3.0, 10.0)
        check("invalid range raises ValueError", False, "no exception raised")
    except ValueError as exc:
        check("invalid range raises ValueError", True, str(exc)[:60])
    try:
        dmm.configure_dcv(10.0, 0)
        check("NPLC <= 0 raises ValueError", False, "no exception raised")
    except ValueError:
        check("NPLC <= 0 raises ValueError", True)
    dmm.close()

    print("\nS7 binary burst parsing (2n+2 bytes / big-endian / x ISCALE)", flush=True)
    raw_values = [1, -2, 32767, -32768, 0, -1]
    iscale = 1.0e-07
    block = (b"".join(int(v).to_bytes(2, "big", signed=True) for v in raw_values)
             + b"\r\n")                       # 样例固定多读的 2 字节尾巴
    dmm, transport = connected(responses={C.ISCALE_Q: "1.000000E-07"}, block=block)
    result = dmm.read_burst(len(raw_values), sample_interval_s=C.DEFAULT_SAMPLE_INTERVAL_S,
                            dcv_range=10.0, aperture_s=C.DEFAULT_APERTURE_S)
    check("value = int x ISCALE (negatives, int16 extremes)",
          result["values"] == [v * iscale for v in raw_values], result["values"])
    check("summary stats correct (n/min/max/mean)",
          result["summary"]["n"] == len(raw_values)
          and result["summary"]["min"] == -32768 * iscale
          and result["summary"]["max"] == 32767 * iscale
          and abs(result["summary"]["mean"]
                  - sum(raw_values) * iscale / len(raw_values)) < 1e-15,
          result["summary"])
    # 2026-09-23 起 connect() 会先做读前准备（prepare_for_read），写序列以这三条开头；
    # 突发自身在样例配方之后还会**收尾 + 恢复**（TARM/TRIG HOLD、PRESET NORM、读前准备），
    # 所以这里断言"前缀 = 样例配方"，并单独断言收尾/恢复确实发生。
    prep = [C.END_ALWAYS, C.INBUF_ON, C.TRIG_AUTO]
    expect_writes = prep + [C.PRESET_DIG, f"{C.DCV} 10", C.MFORMAT_SINT, C.OFORMAT_SINT,
                            f"{C.APER} 1.4E-6", f"{C.TIMER} 1E-5", C.MEM_OFF,
                            f"{C.NRDGS} {len(raw_values)}", C.TRIG_AUTO, C.TARM_SYN]
    tail = transport.writes[len(expect_writes):]
    check("burst recipe prefix matches the Keysight sample",
          transport.writes[:len(expect_writes)] == expect_writes,
          transport.writes[:len(expect_writes)])
    check("burst cleans up and restores (TARM/TRIG HOLD + PRESET NORM)",
          C.TARM_HOLD in tail and C.TRIG_HOLD in tail and C.PRESET_NORM in tail,
          f"tail={tail}")
    check("reads a 2n+2 byte block",
          any(name == "read_bytes" and arg[0] == 2 * len(raw_values) + 2
              for name, arg in transport.calls),
          [arg for name, arg in transport.calls if name == "read_bytes"])
    dmm.close()

    dmm, _ = connected(responses={C.ISCALE_Q: "1E-7"}, block=b"\x00" * 4)
    try:
        dmm.read_burst(6)
        check("short block raises a clear error", False, "no exception raised")
    except TransportError as exc:
        check("short block raises a clear error", True, str(exc)[:60])
    dmm.close()

    dmm, _ = connected(responses={C.ISCALE_Q: "NOT A NUMBER"}, block=b"\x00" * 12)
    try:
        dmm.read_burst(5)
        check("non-numeric ISCALE? raises", False, "no exception raised")
    except TransportError:
        check("non-numeric ISCALE? raises", True)
    dmm.close()

    print("\nS8 identity via ID? (the 3458A has no *IDN?)", flush=True)
    dmm, transport = connected(responses={C.ID: "HP3458A"})
    idn = dmm.idn()
    check("idn() reads identity via ID?", idn == "HP3458A" and transport.count("query", C.ID) == 1, idn)
    check("identity contains 3458 (server _verify_idn)", "3458" in idn.upper(), idn)
    dmm.close()

    print("\nS9 reset(): RESET + END ALWAYS + INBUF ON write order", flush=True)
    dmm, transport = connected()
    transport.calls.clear()
    transport.writes.clear()
    dmm.reset()
    check("write order: hold triggers -> RESET -> END ALWAYS -> INBUF ON",
          transport.writes == [C.TARM_HOLD, C.TRIG_HOLD, C.RESET,
                               C.END_ALWAYS, C.INBUF_ON],
          transport.writes)
    check("clear + bounded drain after RESET",
          transport.count("clear") >= 1 and transport.count("drain") >= 1,
          f"clear×{transport.count('clear')} drain×{transport.count('drain')}")
    check("tracked range reset to None after reset()",
          dmm.current_range is None, dmm.current_range)
    dmm.close()

    print("\nS10 free-run recovery (IFC/clear -> bounded drain -> TARM/TRIG HOLD)", flush=True)
    dmm, transport = connected()
    transport.calls.clear()
    transport.writes.clear()
    dmm.recover()
    expected = ["ifc", "drain", "write", "write", "drain"]
    check("recovery order = ifc -> drain -> TARM HOLD -> TRIG HOLD -> drain",
          transport.names() == expected, transport.names())
    check("holds issued: TARM HOLD + TRIG HOLD",
          transport.writes == [C.TARM_HOLD, C.TRIG_HOLD], transport.writes)
    check("drain capped (rounds<=6, timeout_ms<=250)",
          all(int(a[0]) <= 6 and int(a[1]) <= 250
              for name, a in transport.calls if name == "drain"),
          [a for name, a in transport.calls if name == "drain"])
    dmm.close()

    print("\nS11 candidate resource strings (no hard-coded host/IP)", flush=True)
    cands = candidate_resources(resource=None, addr=9, hosts=["fw-host"],
                                known="visa://gw/GPIB0::9::INSTR")
    check("order = known -> hosts -> local GPIB -> SICL",
          cands == ["visa://gw/GPIB0::9::INSTR", "visa://fw-host/GPIB0::9::INSTR",
                    "GPIB0::9::INSTR", "sicl:gpib0,9"], cands)
    check("explicit resource comes first",
          candidate_resources("GPIB0::3::INSTR", 9)[0] == "GPIB0::3::INSTR")
    check("without hosts/known only the two local candidates",
          candidate_resources(None, 9) == ["GPIB0::9::INSTR", "sicl:gpib0,9"],
          candidate_resources(None, 9))
    check("addr threaded through the candidates",
          candidate_resources(None, 22, ["h"]) ==
          ["visa://h/GPIB0::22::INSTR", "GPIB0::22::INSTR", "sicl:gpib0,22"])

    print("\nS11.5 resolver integration (common/resolver.py; offline)", flush=True)
    from common.resolver import DEVICE_KINDS, canonicalize, is_visa_resource

    check("resolver treats sicl: as a full resource string",
          is_visa_resource("sicl:gpib0,9") and not is_visa_resource("192.0.2.7")
          and is_visa_resource("GPIB0::9::INSTR") and is_visa_resource("visa://h/GPIB0::9::INSTR"))
    check("canonicalize returns sicl: unchanged",
          canonicalize("ks3458a", "sicl:gpib0,9") == "sicl:gpib0,9")
    check("DEVICE_KINDS[ks3458a] idn token = 3458",
          DEVICE_KINDS["ks3458a"][0] == "3458", DEVICE_KINDS["ks3458a"])
    check("env var name = INSTRUMENT_KS3458A_RES",
          DEVICE_KINDS["ks3458a"][2] == "INSTRUMENT_KS3458A_RES", DEVICE_KINDS["ks3458a"][2])

    print("\nS12 AC config / error string / number format / TMC header", flush=True)
    prep = [C.END_ALWAYS, C.INBUF_ON, C.TRIG_AUTO]     # connect() 的读前准备
    dmm, transport = connected(readings=["1.0"])
    dmm.configure_acv(10.0, band_lo=20.0, band_hi=100000.0, sync=True)
    check("ACV write order = ACV / SETACV SYNC / ACBAND",
          transport.writes == prep + [f"{C.ACV} 10", C.SETACV_SYNC,
                                      f"{C.ACBAND} 20,100000"], transport.writes)
    dmm.close()
    dmm, transport = connected(readings=["1.0"])
    dmm.configure_acv(10.0)
    check("sync=False -> SETACV ANA; no ACBAND when band omitted",
          transport.writes == prep + [f"{C.ACV} 10", C.SETACV_ANA], transport.writes)
    try:
        dmm.configure_acv(10.0, band_lo=20.0)
        check("half-specified ACBAND raises", False, "no exception raised")
    except ValueError:
        check("half-specified ACBAND raises", True)
    dmm.close()

    dmm, _ = connected(responses={C.ERRSTR: '0,"NO ERROR"'})
    check('ERRSTR? parse: 0,"NO ERROR" -> clear', is_error_clear(dmm.error_string()))
    dmm.close()
    dmm, _ = connected(responses={C.ERRSTR: '101,"SYNTAX ERROR"'})
    check("ERRSTR? parse: non-zero code -> error",
          not is_error_clear(dmm.error_string()) and "SYNTAX" in dmm.error_string())
    dmm.close()
    check("unparseable ERRSTR? reported as error (fail safe)",
          not is_error_clear("???"), is_error_clear("???"))

    check("fmt_num: uppercase E, no leading zeros ('TIMER 10E-6')",
          C.fmt_num(1.4e-6) == "1.4E-6" and C.fmt_num(10e-6) == "1E-5"
          and C.fmt_num(10.0) == "10" and C.fmt_num(100000.0) == "100000",
          [C.fmt_num(v) for v in (1.4e-6, 10e-6, 10.0, 100000.0)])

    sample = b"#14" + b"\x01\x02\xff\xff"   # '#' + 位数(1) + 长度(4) → 数据从第 3 字节起
    check("TMC header: #<digits><length> locates the body",
          tmc_split(sample) == (3, 7) and tmc_body(sample) == b"\x01\x02\xff\xff",
          tmc_split(sample))
    check("TMC header: #0 (unknown length) and headerless",
          tmc_split(b"#0abc") == (2, None) and tmc_body(b"#0abc") == b"abc"
          and tmc_split(b"1.5\n") == (0, None))

    print("\nS13 burst limits and parameter validation", flush=True)
    dmm, _ = connected()
    try:
        dmm.read_burst(0)
        check("n=0 raises ValueError", False, "no exception raised")
    except ValueError:
        check("n=0 raises ValueError", True)
    try:
        dmm.read_burst(C.BURST_MAX_READINGS + 1)
        check("n above cap raises ValueError", False, "no exception raised")
    except ValueError:
        check("n above cap raises ValueError", True)
    try:
        dmm.read_avg(0)
        check("read_avg(0) raises ValueError", False, "no exception raised")
    except ValueError:
        check("read_avg(0) raises ValueError", True)
    dmm.close()

    print("\nS14 driver pre-check and connection-failure hint (offline, monkeypatched)", flush=True)
    # 真实 preflight 会起 PowerShell 查 PnP；这里替换成"缺驱动"的假结论，只验证
    # MCP 是否把它作为 hint 回传（真机路径由 verify_3458a_live.py 覆盖）。
    import keysight_3458a.driver_check as dc
    real_check = dc.check_gpib_driver
    dc.check_gpib_driver = lambda *a, **k: {          # type: ignore[assignment]
        "ok": False, "verdict": "driver_missing",
        "message": "82357B 已插上但驱动异常——请安装 Keysight IO Libraries Suite",
        "devices": [{"instance_id": "USB\\VID_0957&PID_0718\\FAKE", "status": "Error",
                     "problem": 28}],
    }
    try:
        sys.path.insert(0, str(ROOT / "mcp_instruments"))
        import server                                  # noqa: PLC0415
        server._LAST_DRIVER_HINT.clear()
        resp = json.loads(server.ks3458a_read(resource="GPIB9::9::INSTR"))
        check("连接失败返回 hint（驱动预检查结论）",
              resp.get("ok") is False
              and (resp.get("hint") or {}).get("verdict") == "driver_missing",
              f"hint={(resp.get('hint') or {}).get('verdict')}")
        check("hint 里带可执行提示（提示装 IO Libraries Suite）",
              "IO Libraries Suite" in str((resp.get("hint") or {}).get("message", "")),
              str((resp.get("hint") or {}).get("message"))[:80])
    except Exception as exc:                            # noqa: BLE001
        check("连接失败返回 hint（驱动预检查结论）", False, f"{type(exc).__name__}: {exc}")
    finally:
        dc.check_gpib_driver = real_check               # type: ignore[assignment]

    total = len(checks)
    # 真实场景：同一台表被别的进程/MCP 会话占用 → 库必须**明确拒绝**而不是并发串台。
    # 这里把 session_lock.touch 换成"总是返回一个他人占用"，验证拒绝逻辑与提示文案。
    import common.session_lock as sl
    real_touch, real_release = sl.touch, sl.release
    sl.touch = lambda *a, **k: {"holders": [{"pid": 999999, "kind": "other-script",
                                             "host": "FAKE", "started": 1.0}]}
    sl.release = lambda *a, **k: None
    try:
        guarded = DMM3458A("GPIB0::9::INSTR", timeout_s=5.0)   # 不 open，只测 connect 前置检查
        try:
            guarded.connect()
            check("busy guard rejects concurrent session", False, "没有拒绝")
        except Exception as exc:                          # noqa: BLE001
            msg = str(exc)
            check("busy guard rejects concurrent session",
                  "占用" in msg and "force=True" in msg, msg[:110])
        check("busy guard exposes holders list",
              bool(guarded.holders) and guarded.holders[0].get("pid") == 999999,
              guarded.holders)
    finally:
        sl.touch, sl.release = real_touch, real_release

    print("\nS16 burst robustness (offline: fault injection, no device I/O)", flush=True)
    # 现场故障（2026-09-23）：MCP 里一次 burst 卡住 71s+ 并握着设备锁 → 后续调用全堵。
    # 三条防线各自要有用例：①写超时自动恢复重试 ②读失败也必须收尾+恢复 ③超时预算按 n×间隔算。
    block = b"\x00\x01" * 200      # 足够 n=100 的 SINT 块（2n+2 = 202 字节）
    t1 = FakeTransport(block=block, responses={C.ISCALE_Q: "1.0"}, fail_writes=1)
    d1 = DMM3458A(transport=t1)
    d1._connected = True
    res1 = d1.read_burst(5, sample_interval_s=1e-4, dcv_range=0.1)
    check("burst retries a timed-out write after recovery",
          len(res1["values"]) == 5 and any(name == "ifc" for name, _ in t1.calls),
          f"values={len(res1['values'])} ifc_called={any(n == 'ifc' for n, _ in t1.calls)}")

    t2 = FakeTransport(block=block, responses={C.ISCALE_Q: "1.0"}, fail_read_bytes=True)
    d2 = DMM3458A(transport=t2)
    d2._connected = True
    try:
        d2.read_burst(5, sample_interval_s=1e-4, dcv_range=0.1)
        check("failed burst still cleans up + restores (finally path)", False, "没有抛错")
    except Exception:                                     # noqa: BLE001
        check("failed burst still cleans up + restores (finally path)",
              C.TARM_HOLD in t2.writes and C.TRIG_HOLD in t2.writes
              and C.PRESET_NORM in t2.writes,
              [w for w in t2.writes if w in (C.TARM_HOLD, C.TRIG_HOLD, C.PRESET_NORM)])

    # ③ 超时预算 = clamp(10 + 3×n×间隔, 10, 180)：不再吃 120 s 通用默认
    t3 = FakeTransport(block=block, responses={C.ISCALE_Q: "1.0"})
    d3 = DMM3458A(transport=t3)
    d3._connected = True
    res3 = d3.read_burst(100, sample_interval_s=1e-4, dcv_range=0.1)
    budget = res3["summary"]["read_timeout_s"]
    rb = [a for n, a in t3.calls if n == "read_bytes"]
    check("burst timeout budget derived from n x interval",
          abs(budget - (10.0 + 3 * 100 * 1e-4)) < 1e-6 and rb and rb[0][1] == budget,
          f"budget={budget} read_bytes_arg={rb[:1]}")

    print("\nS17 read_series: one session, N points (offline, fake transport)", flush=True)
    t4 = FakeTransport(readings=["1.0", "2.0", "3.0"])
    d4 = DMM3458A(transport=t4)
    d4._connected = True
    out4 = d4.read_series(3, interval_s=None)
    check("read_series returns per-point values + stats + duration",
          out4["values"] == [1.0, 2.0, 3.0] and out4["summary"]["n"] == 3
          and out4["summary"]["mean"] == 2.0 and out4["summary"]["duration_s"] >= 0
          and len(out4["timestamps"]) == 3,
          f"values={out4['values']} n/mean/stddev="
          f"{out4['summary']['n']}/{out4['summary']['mean']}/{out4['summary']['stddev']}")
    check("read_series uses one TARM SGL,1 per point (no reconnect)",
          sum(1 for n, a in t4.calls if n == "query" and a == C.TARM_SGL_1) == 3,
          f"tarm_calls={sum(1 for n, a in t4.calls if n == 'query' and a == C.TARM_SGL_1)}")

    total = len(checks)
    passed = total - len(fails)
    print(f"\n== result: {passed}/{total} PASS"
          f"{' (all PASS)' if not fails else f' ({len(fails)} FAIL)'} ==", flush=True)
    for name in fails:
        print(f"  - FAIL: {name}")

    # 留痕（时间戳命名，防覆盖）
    try:
        out_dir = ROOT / "TEST_DATA" / "ks3458a"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"verify_3458a_offline_{stamp}.json"
        out_path.write_text(json.dumps({
            "when": datetime.now().isoformat(timespec="seconds"),
            "script": "TEST_SCRIPTS/ks3458a/verify_3458a_offline.py",
            "device_io": "none（全部走假传输/假 pyvisa）",
            "passed": passed, "total": total, "fails": fails, "checks": checks,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"evidence: {out_path}", flush=True)
    except Exception as exc:                          # noqa: BLE001 —— 留痕失败不影响结论
        print(f"evidence write failed (result unaffected): {type(exc).__name__}: {exc}", flush=True)

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
