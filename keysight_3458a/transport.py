"""3458A 的两条传输通路——同一接口，可互换。

    ① `PyVisaTransport` —— 任意 VISA 资源串：`GPIB0::9::INSTR`、本机 GPIB、
       `visa://<host>/GPIB0::9::INSTR`（远端 VISA server）。
    ② `SiclTransport`   —— 本机 Keysight SICL（`sicl:gpib0,9`），ctypes 直调 sicl32.dll。

**为什么需要两条**（EmoeCalibrator 现场实测）：本机用 Keysight VISA **打不开** 82357B
USB/GPIB 卡上的 `GPIB0::<addr>::INSTR`（报 `VI_ERROR_INTF_NUM_NCONFIG`，但 `GPIB0::INTFC`
能开、总线是通的）；SICL 是 Keysight 的第二套独立 API，走它能通。反过来，设备挂在
**远端 VISA server** 上时只有 VISA 通路可用。两条通路的能力差异见 `README.md`。

统一接口（`DMM3458A` 只依赖这套接口，离线测试用假传输实现同一套）::

    open() / close() / write(cmd) / read() / read_bytes(n) / query(cmd)
    clear() / drain() / set_timeout(s) / ifc()

两个实现细节是**实测教训**，不要"简化"：

    - 3458A **串尾必须是 LF**：CRLF 会让它不应答（[VISA] L529-531 实测超时）。
    - `drain()` **必须有上限**：被留在 free-run 的 3458A 会一直吐读数，无界 drain
      实测跑 80~91 s（[SICL] L223-230）。真正让序列停下的是 IFC/clear，drain 只扫尾。
"""
from __future__ import annotations

import ctypes
import os
import re
import time
from typing import Optional, Protocol

SETTLE_S = 0.05           # open 后 / clear 后的静默等待（原为 0.3s；2026-09-23 计时后收紧，
                          # open 的耗时其实来自 clear 本身，0.05s 足够吃下 Device Clear）
READ_MAX_ROUNDS = 64      # 文本行分片拼包上限
BLOCK_MAX_ROUNDS = 256    # 二进制块分片拼包上限
DRAIN_MAX_ROUNDS = 6      # drain 轮数上限（硬性：≤6）
DRAIN_TIMEOUT_MS = 250    # 每轮 drain 的超时（硬性：≤250ms）
# ⚠ 2026-09-23 实测：VISA 的 VI_ATTR_TMO_VALUE 有 ≈2s 最小粒度，250ms 设不下去 →
# 单轮 drain 实际耗时 ≈2s。因此 drain 是**慢路径**，只在 recover/收尾时用，轮数已压到 2。
DRAIN_ROUNDS_MIN = 2


class TransportError(RuntimeError):
    """传输层失败：打不开会话、读写失败、超时无数据、二进制块不足。"""


class Transport(Protocol):
    """`DMM3458A` 依赖的最小接口（假传输只要实现这些即可离线跑驱动）。"""

    resource: str

    def open(self) -> "Transport": ...
    def close(self) -> None: ...
    def write(self, cmd: str) -> None: ...
    def read(self, timeout_s: Optional[float] = None) -> str: ...
    def read_bytes(self, count: int, timeout_s: Optional[float] = None) -> bytes: ...
    def query(self, cmd: str, timeout_s: Optional[float] = None) -> str: ...
    def clear(self) -> None: ...
    def drain(self, max_rounds: int = DRAIN_MAX_ROUNDS,
              timeout_ms: int = DRAIN_TIMEOUT_MS) -> int: ...
    def set_timeout(self, seconds: float) -> None: ...
    def ifc(self) -> None: ...


# ---------------------------------------------------------------------------
# TMC（IEEE-488.2 二进制块）头处理
#
# pyvisa 的 read_bytes 会自动剥 TMC 头；SICL 的 iread 给的是**原始字节流**，
# 头要自己剥。下面的纯函数同时被两条通路与离线测试使用。
# ---------------------------------------------------------------------------

def tmc_split(raw: bytes) -> tuple[Optional[int], Optional[int]]:
    """拆 TMC 头，返回 `(数据体起始偏移, 整块总长)`；两者都可能为 None。

    - 不以 `#` 开头、或 `#` 后不是数字 → 无头：`(0, None)`
    - `#0` + 数据（长度未声明，靠 EOI 终止）→ `(2, None)`
    - `#<d><d 位长度数字>` + 数据 → `(2+d, 2+d+长度)`
    - 头部还没读全 → `(None, None)`（调用方继续读）
    """
    if not raw:
        return None, None
    if raw[0:1] != b"#":
        return 0, None
    if len(raw) < 2:
        return None, None
    digits = raw[1:2]
    if not digits.isdigit():
        return 0, None
    if digits == b"0":
        return 2, None
    ndigits = int(digits)
    if len(raw) < 2 + ndigits:
        return None, None
    return 2 + ndigits, 2 + ndigits + int(raw[2:2 + ndigits])


def tmc_body(raw: bytes) -> bytes:
    """取数据体（剥掉 TMC 头；头部不完整时按无头处理，由调用方判长度）。"""
    offset, total = tmc_split(raw)
    if offset is None:
        offset = 0
    body = raw[offset:]
    if total is not None:
        body = body[:max(0, total - offset)]
    return body


def _block_satisfied(raw: bytes, count: int) -> bool:
    """已收到的原始字节是否**足以**判定有 count 字节数据体。"""
    offset, total = tmc_split(raw)
    if offset is None:
        return False
    if total is not None:
        return len(raw) >= total
    return len(raw) - offset >= count


# ---------------------------------------------------------------------------
# ① pyvisa 通路
# ---------------------------------------------------------------------------

class PyVisaTransport:
    """pyvisa 通路：`GPIB0::9::INSTR` / `visa://<host>/GPIB0::9::INSTR` / USB / 串口。

    资源串**原样交给 pyvisa**，不在这里解析或拼接协议/端口（AGENTS.md：地址一律是
    完整 VISA 资源串，拼错一个字段就是对未知设备发命令）。

    GPIB 通路默认优先 **Keysight VISA**（`ktvisa\\ktbin\\visa32.dll`）并预加载套件的
    `ioGPIB.dll`/`ioGpibIntfc.dll`——2026-09-23 本机实测：这是唯一能让 82357B USB/GPIB
    在 **64 位** Python 里打开 `GPIB0::9::INSTR` 的组合；系统默认（NI-VISA/IVI 壳）
    会报 `VI_ERROR_LIBRARY_NFOUND`（NI 的 GPIB 护照需要 NI-488.2 或 32 位 Tulip 护照）。
    """

    def __init__(self, resource: str, timeout_s: float = 30.0,
                 open_timeout_ms: int = 3000, chunk_size: int = 1 << 16,
                 visalib: Optional[str] = None, prefer_keysight_visa: bool = True):
        self.resource = resource
        self.timeout_s = float(timeout_s)
        self.open_timeout_ms = int(open_timeout_ms)
        self.chunk_size = int(chunk_size)
        self.visalib = visalib
        self.prefer_keysight_visa = bool(prefer_keysight_visa)
        self._rm = None
        self._inst = None

    # -- 生命周期 ----------------------------------------------------------
    def open(self) -> "PyVisaTransport":
        if self._inst is not None:
            return self
        import pyvisa

        visalib = self.visalib
        local_gpib = (self.prefer_keysight_visa and os.name == "nt"
                      and self.resource.strip().upper().startswith("GPIB")
                      and "://" not in self.resource)
        if visalib is None and local_gpib:
            visalib = prepare_keysight_visa()
        self._rm = pyvisa.ResourceManager(visalib) if visalib else pyvisa.ResourceManager()
        try:
            self._inst = self._rm.open_resource(
                self.resource, open_timeout=self.open_timeout_ms)
            self._inst.timeout = int(self.timeout_s * 1000)
            # 3458A 用 LF 结尾；pyvisa 默认的 \r\n 会让它不应答（[VISA] L529-531 实测）
            self._inst.write_termination = "\n"
            self._inst.read_termination = "\n"
            # 二进制突发（2n+2 字节）走 read_bytes，块要够大
            self._inst.chunk_size = self.chunk_size
        except Exception:
            self.close()
            raise
        self.clear()
        time.sleep(SETTLE_S)
        return self

    def close(self) -> None:
        if self._inst is not None:
            try:
                self._inst.close()
            except Exception:
                pass
            self._inst = None
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception:
                pass
            self._rm = None

    @property
    def is_open(self) -> bool:
        return self._inst is not None

    def __enter__(self) -> "PyVisaTransport":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def _require(self):
        if self._inst is None:
            raise TransportError(f"3458A 会话未打开（{self.resource}）")
        return self._inst

    # -- 基本 I/O ----------------------------------------------------------
    def write(self, cmd: str) -> None:
        # write_termination='\n' 由 pyvisa 追加，这里不再自己拼（拼了会变成 LF LF）
        self._require().write(cmd)

    def read(self, timeout_s: Optional[float] = None) -> str:
        """读一行（终止符由 pyvisa 按 read_termination 剥离），返回去掉首尾空白的文本。"""
        inst = self._require()
        prev = None
        if timeout_s is not None:
            prev, inst.timeout = inst.timeout, int(float(timeout_s) * 1000)
        try:
            return inst.read().strip()
        finally:
            if prev is not None:
                inst.timeout = prev

    def read_bytes(self, count: int, timeout_s: Optional[float] = None) -> bytes:
        """读 count 字节**数据体**（TMC 头由 pyvisa 剥离）。

        字节数不足会明确报错——静默返回截断数据会让突发解析出错位的"合理值"。
        """
        inst = self._require()
        prev = None
        if timeout_s is not None:
            prev, inst.timeout = inst.timeout, int(float(timeout_s) * 1000)
        try:
            data = inst.read_bytes(int(count))
        except Exception as e:                      # noqa: BLE001
            raise TransportError(
                f"二进制回读失败（期望 {count} 字节）：{type(e).__name__}: {e}") from e
        finally:
            if prev is not None:
                inst.timeout = prev
        if len(data) < int(count):
            raise TransportError(
                f"二进制回读不足：期望 {count} 字节，实得 {len(data)} 字节")
        return data[:int(count)]

    def query(self, cmd: str, timeout_s: Optional[float] = None) -> str:
        self.write(cmd)
        return self.read(timeout_s)

    # -- 会话恢复用 --------------------------------------------------------
    def clear(self) -> None:
        """Device Clear（发给本设备）——中断它正在跑的测量序列。"""
        self._require().clear()

    def ifc(self) -> None:
        """VISA 侧**没有** IFC（接口清除）等价物 → 退化为 Device Clear。

        GPIB 上 IFC 是"接口清除"（整条总线所有设备一起中断），pyvisa 只暴露
        Selected Device Clear。3458A 处于 free-run 时 Device Clear 一般也能中止序列；
        若中止不掉（读数一直涌出、查询无响应），说明该走 SICL 通路（`SiclTransport.ifc`）
        或面板干预——见 README「free-run」一节。
        """
        self.clear()

    def drain(self, max_rounds: int = DRAIN_MAX_ROUNDS,
              timeout_ms: int = DRAIN_TIMEOUT_MS) -> int:
        """**有限**排空残留输出，返回丢弃的字节数。上限是硬性的（见模块 docstring）。"""
        inst = self._require()
        prev = inst.timeout
        inst.timeout = int(timeout_ms)
        total = 0
        try:
            for _ in range(max(0, int(max_rounds))):
                try:
                    chunk = inst.read_raw()
                except Exception:                   # noqa: BLE001 —— 超时即"没有残留"
                    break
                if not chunk:
                    break
                total += len(chunk)
        finally:
            inst.timeout = prev
        return total

    def set_timeout(self, seconds: float) -> None:
        self.timeout_s = float(seconds)
        if self._inst is not None:
            self._inst.timeout = int(self.timeout_s * 1000)


# ---------------------------------------------------------------------------
# ② SICL 通路（ctypes 直调 sicl32.dll）
#
# 原型逐字取自 Keysight IO Libraries 的 sicl.h（见 dmm_sicl.py 模块 docstring）：
#     int iwrite(INST id, char *buf, unsigned long datalen, int endi, unsigned long *actual);
#     int iread (INST id, char *buf, unsigned long bufsize, int *reason, unsigned long *actual);
# **传 4 参数形式会让进程崩溃——不要"简化"成 4 参数。**
# ---------------------------------------------------------------------------

_SICL_DIRS = (
    r"C:\Program Files\Keysight\IO Libraries Suite\bin",
    r"C:\Program Files\Keysight\IO Libraries Suite",
    r"C:\Program Files (x86)\Keysight\IO Libraries Suite\bin",
    r"C:\Windows\System32",
)
_SICL_PATHS = (
    r"C:\Windows\System32\sicl32.dll",
    r"C:\Windows\SysWOW64\sicl32.dll",
)

# sicl32.dll 需要同目录的兄弟 DLL（ioRM.dll / instr32.dll …）可解析
for _directory in _SICL_DIRS:
    if os.path.isdir(_directory):
        try:
            os.add_dll_directory(_directory)
        except (AttributeError, OSError):
            pass


# iread() 的终止原因（sicl.h）
REASON = {0: "NONE", 1: "CNTL", 2: "EOI", 3: "CHR", 4: "LEN", 5: "TERM"}

_SICL: dict = {"lib": None, "bound": None}
_IFC_SESSION: dict = {"inst": None}


def _load_sicl():
    """惰性加载 sicl32.dll 并绑定函数原型（失败抛 TransportError，不静默）。"""
    if _SICL["lib"] is not None:
        return _SICL["lib"]
    lib = None
    last = None
    for path in _SICL_PATHS:
        if not os.path.isfile(path):
            continue
        try:
            lib = ctypes.WinDLL(path)
            break
        except OSError as exc:                      # pragma: no cover - 环境相关
            last = exc
    if lib is None:
        raise TransportError(
            f"加载 sicl32.dll 失败（{last}）。本机需装 Keysight IO Libraries Suite；"
            f"找不到时改用 pyvisa 通路（如 GPIB0::9::INSTR）")

    def bind(name, restype, argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = argtypes
        return fn

    _SICL["lib"] = lib
    _SICL["bound"] = {
        "iopen": bind("iopen", ctypes.c_uint, [ctypes.c_char_p]),
        "iclose": bind("iclose", ctypes.c_int, [ctypes.c_uint]),
        "itimeout": bind("itimeout", ctypes.c_int, [ctypes.c_uint, ctypes.c_long]),
        "iclear": bind("iclear", ctypes.c_int, [ctypes.c_uint]),
        "iabort": bind("iabort", ctypes.c_int, [ctypes.c_uint]),
        "iwrite": bind("iwrite", ctypes.c_int,
                       [ctypes.c_uint, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_int,
                        ctypes.POINTER(ctypes.c_ulong)]),
        "iread": bind("iread", ctypes.c_int,
                      [ctypes.c_uint, ctypes.c_char_p, ctypes.c_ulong,
                       ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong)]),
        "ireadstb": bind("ireadstb", ctypes.c_int,
                         [ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte)]),
        "igeterrno": bind("igeterrno", ctypes.c_int, []),
        "igeterrstr": bind("igeterrstr", ctypes.c_char_p, [ctypes.c_int]),
        "igpibpulseifc": bind("igpibpulseifc", ctypes.c_int, [ctypes.c_uint]),
        "igpibrenctl": bind("igpibrenctl", ctypes.c_int, [ctypes.c_uint, ctypes.c_int]),
    }
    return lib


def _f(name: str):
    _load_sicl()
    return _SICL["bound"][name]


def _last_error() -> tuple[int, str]:
    errno = _f("igeterrno")()
    try:
        text = _f("igeterrstr")(errno).decode("ascii", "replace")
    except Exception:                               # noqa: BLE001
        text = "?"
    return errno, text


class SiclTransport:
    """SICL/GPIB 通路（本机 82357B 等 USB-GPIB 卡走这条）。

    与 dmm_sicl.py 的两处**必要差异**：

    1. 二进制安全 —— 参考实现把 iread 的字节 `decode('ascii','replace')` 再返回，
       SINT 读数里 >0x7F 的字节会被替换成 U+FFFD，**突发数组会全错**。本实现
       `read_raw` 返回 bytes，只有文本路径才 decode。
    2. TMC 头 —— iread 不做块分帧，`read_bytes` 自己剥 `#<n><len>` 头（`tmc_split`）。
    """

    def __init__(self, addr: int = 9, timeout_s: float = 30.0,
                 bufsize: int = 1 << 16, interface: str = "gpib0"):
        self.addr = int(addr)
        self.interface = interface
        self.timeout_s = float(timeout_s)
        self.bufsize = int(bufsize)
        self.resource = f"sicl:{interface},{self.addr}"
        self._inst = None
        self._buf = ctypes.create_string_buffer(self.bufsize)

    # -- 生命周期 ----------------------------------------------------------
    def open(self) -> "SiclTransport":
        if self._inst:
            return self
        inst = _f("iopen")(f"{self.interface},{self.addr}".encode())
        if not inst:
            errno, text = _last_error()
            raise TransportError(
                f"iopen({self.interface},{self.addr}) 失败：{errno} {text}"
                f"（SICL 是否已装？GPIB 地址是否正确？）")
        self._inst = inst
        _f("itimeout")(inst, int(self.timeout_s * 1000))
        self.clear()
        time.sleep(SETTLE_S)
        return self

    def close(self) -> None:
        if self._inst:
            try:
                _f("iclose")(self._inst)
            except Exception:                       # noqa: BLE001
                pass
            self._inst = None

    @property
    def is_open(self) -> bool:
        return bool(self._inst)

    def __enter__(self) -> "SiclTransport":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def _require(self):
        if not self._inst:
            raise TransportError(f"3458A 会话未打开（{self.resource}）")
        return self._inst

    # -- 基本 I/O ----------------------------------------------------------
    def write(self, cmd: str) -> int:
        inst = self._require()
        data = cmd.encode() if isinstance(cmd, str) else cmd
        if not data.endswith(b"\n"):
            data += b"\n"          # 3458A 只认 LF 结尾（CRLF 不应答）
        actual = ctypes.c_ulong(0)
        rc = _f("iwrite")(inst, data, len(data), 1, ctypes.byref(actual))
        if rc != 0:
            errno, text = _last_error()
            raise TransportError(f"iwrite({cmd!r}) 失败：{errno} {text}")
        return actual.value

    def read_raw(self, timeout_s: Optional[float] = None) -> tuple[int, bytes]:
        """一次 iread，返回 `(返回码, 原始字节)`（**不做 decode** —— 二进制读数必须保持字节）。"""
        inst = self._require()
        prev = None
        if timeout_s is not None:
            prev = self.timeout_s
            self.set_timeout(timeout_s)
        try:
            reason = ctypes.c_int(0)
            actual = ctypes.c_ulong(0)
            rc = _f("iread")(inst, self._buf, self.bufsize,
                             ctypes.byref(reason), ctypes.byref(actual))
            return rc, self._buf.raw[:actual.value]
        finally:
            if prev is not None:
                self.set_timeout(prev)

    def read(self, timeout_s: Optional[float] = None) -> str:
        """读一行：iread 可能分片返回，循环拼到 LF 结尾（最多 READ_MAX_ROUNDS 轮）。"""
        prev = None
        if timeout_s is not None:
            prev = self.timeout_s
            self.set_timeout(timeout_s)
        try:
            chunks: list[bytes] = []
            for _ in range(READ_MAX_ROUNDS):
                rc, data = self.read_raw()
                if data:
                    chunks.append(data)
                    if data.endswith(b"\n"):
                        break
                elif rc != 0:
                    break
            raw = b"".join(chunks)
            if not raw:
                errno, text = _last_error()
                raise TransportError(f"iread 无数据（errno {errno} {text}）")
            return raw.decode("ascii", "replace").strip()
        finally:
            if prev is not None:
                self.set_timeout(prev)

    def read_bytes(self, count: int, timeout_s: Optional[float] = None) -> bytes:
        """读 count 字节**数据体**（循环 iread 拼包，并剥掉 SICL 不会自动去掉的 TMC 头）。"""
        count = int(count)
        prev = None
        if timeout_s is not None:
            prev = self.timeout_s
            self.set_timeout(timeout_s)
        try:
            raw = b""
            for _ in range(BLOCK_MAX_ROUNDS):
                if _block_satisfied(raw, count):
                    break
                rc, data = self.read_raw()
                if data:
                    raw += data
                    continue
                if rc != 0:
                    break
            body = tmc_body(raw)
            if len(body) < count:
                raise TransportError(
                    f"二进制回读不足：期望 {count} 字节，实得 {len(body)} 字节"
                    f"（原始 {len(raw)} 字节；超时或设备未按 SINT 配方输出）")
            return body[:count]
        finally:
            if prev is not None:
                self.set_timeout(prev)

    def query(self, cmd: str, timeout_s: Optional[float] = None) -> str:
        self.write(cmd)
        return self.read(timeout_s)

    # -- 会话恢复用 --------------------------------------------------------
    def clear(self) -> None:
        """Device Clear（iclear，发给本设备）——中止正在跑的测量序列。"""
        inst = self._require()
        rc = _f("iclear")(inst)
        if rc != 0:
            errno, text = _last_error()
            raise TransportError(f"iclear 失败：{errno} {text}")

    def ifc(self) -> None:
        """GPIB 接口清除（igpibpulseifc）——**整条总线**上的设备都会被中断。

        为什么必须能发（[SICL] L273-276 实测）：上一次会话可能把 3458A 留在 free-run
        （持续吐读数、不理查询）；此时先 drain 只会一直读到数据（实测 91 s），
        必须先用 IFC 把序列打断。代价是同总线其它设备也受影响——本机 GPIB0 上只有
        这台 3458A（addr 9），可接受。
        """
        if _IFC_SESSION["inst"] is None:
            inst = _f("iopen")(self.interface.encode())
            if not inst:
                errno, text = _last_error()
                raise TransportError(f"iopen({self.interface}) 失败：{errno} {text}")
            _IFC_SESSION["inst"] = inst
        rc = _f("igpibpulseifc")(_IFC_SESSION["inst"])
        if rc != 0:
            errno, text = _last_error()
            raise TransportError(f"igpibpulseifc 失败：{errno} {text}")

    def drain(self, max_rounds: int = DRAIN_MAX_ROUNDS,
              timeout_ms: int = DRAIN_TIMEOUT_MS) -> int:
        """**有限**排空残留输出，返回丢弃的字节数。上限硬性（free-run 会读不完）。"""
        prev = self.timeout_s
        self.set_timeout(timeout_ms / 1000.0)
        total = 0
        try:
            for _ in range(max(0, int(max_rounds))):
                rc, data = self.read_raw()
                total += len(data)
                if not data and rc != 0:
                    break
        finally:
            self.set_timeout(prev)
        return total

    def set_timeout(self, seconds: float) -> None:
        self.timeout_s = float(seconds)
        if self._inst:
            _f("itimeout")(self._inst, int(self.timeout_s * 1000))


# ---------------------------------------------------------------------------
# 通路选择
# ---------------------------------------------------------------------------

# --- Keysight VISA 准备（GPIB 在 64 位 Python 下的唯一可行通路）-----------------
# 2026-09-23 本机实测结论：
#   * 系统默认 VISA（C:\Windows\System32\visa32.dll，IVI/NI 壳）打开 GPIB0::9::INSTR
#     报 VI_ERROR_LIBRARY_NFOUND —— 它的 GPIB 护照要 NI-488.2 或 32 位 Tulip 护照；
#   * Keysight VISA 核心是 ktvisa32.dll，且**必须先加载套件 bin 下的 GPIB 支持库**
#     ioGPIB.dll / ioGpibIntfc.dll，否则 ktvisa 的 viOpen 会抛 C++ 异常(0xE06D7363)
#     （SICL 的 iopen 同样症状）。Keysight 自带 test-idn.exe 正是导入 ktvisa32.dll 的。
_DLL_DIR_HANDLES: list = []   # add_dll_directory 返回的句柄必须持有，否则目录会被撤销
_PRELOADED_DLLS: list = []    # 预加载的 GPIB 支持库同样要保持引用
_KEYSIGHT_VISA: Optional[str] = None
_KEYSIGHT_VISA_CORE: Optional[str] = None
_KEYSIGHT_VISA_READY = False


def _visa_base_path() -> Optional[str]:
    """从注册表取 IVI VISA 根目录（Keysight 文档指定 VXIPNPPATH）。"""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\VXIPNP_Alliance\VXIPNP\CurrentVersion") as k:
            return winreg.QueryValueEx(k, "VXIPNPPATH")[0]
    except Exception:
        return None


def prepare_keysight_visa() -> Optional[str]:
    """按 Keysight 文档准备环境，返回 Keysight VISA DLL 路径（失败返回 None）。

    步骤：① VXIPNPPATH → `Win64\\bin`、`Win64\\ktvisa\\ktbin` 加入 DLL 搜索路径；
    ② 预加载套件 `bin\\ioGPIB.dll`、`bin\\ioGpibIntfc.dll`（**关键**，缺了 viOpen 会抛异常）；
    ③ 返回 `<base>\\Win64\\ktvisa\\ktbin\\visa32.dll` 供 pyvisa 指定 visalib。
    幂等：重复调用只做一次实际动作。
    """
    global _KEYSIGHT_VISA, _KEYSIGHT_VISA_CORE, _KEYSIGHT_VISA_READY
    if _KEYSIGHT_VISA_READY:
        return _KEYSIGHT_VISA
    _KEYSIGHT_VISA_READY = True

    if os.name != "nt":
        return None
    base = _visa_base_path()
    dirs = [d for d in (os.path.join(base, "Win64", "bin") if base else None,
                        os.path.join(base, "Win64", "ktvisa", "ktbin") if base else None,
                        r"C:\Program Files\Keysight\IO Libraries Suite\bin")
            if d and os.path.isdir(d)]
    for d in dirs:
        try:
            _DLL_DIR_HANDLES.append(os.add_dll_directory(d))
        except Exception:
            pass
    # 关键：套件 bin 里的 ioGPIB.dll 依赖按「当前目录/SetDllDirectory」解析——
    # 只 add_dll_directory 时 WinDLL(ioGPIB.dll) 会 FileNotFoundError，随后 ktvisa 的
    # viOpen 抛 C++ 异常 0xE06D7363。SetDllDirectoryW 是进程级等效且不改 CWD。
    suite_bin = r"C:\Program Files\Keysight\IO Libraries Suite\bin"
    if os.path.isdir(suite_bin):
        try:
            k32 = ctypes.windll.kernel32
            k32.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
            k32.SetDllDirectoryW.restype = ctypes.c_int
            k32.SetDllDirectoryW(suite_bin)
        except Exception:
            pass
    # 预加载 GPIB 支持库（必须在 ktvisa 之前）
    for name in ("ioGPIB.dll", "ioGpibIntfc.dll"):
        for d in dirs:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                try:
                    import ctypes

                    _PRELOADED_DLLS.append(ctypes.WinDLL(p))
                except Exception:
                    pass
                break
    cand = None
    if base:
        cand = os.path.join(base, "Win64", "ktvisa", "ktbin", "visa32.dll")
        core = os.path.join(base, "Win64", "ktvisa", "ktbin", "ktvisa32.dll")
        if os.path.isfile(core):
            _KEYSIGHT_VISA_CORE = core
    if cand and os.path.isfile(cand):
        _KEYSIGHT_VISA = cand
    else:
        for d in dirs:
            p = os.path.join(d, "visa32.dll")
            if os.path.isfile(p):
                _KEYSIGHT_VISA = p
                break
    if _KEYSIGHT_VISA_CORE is None:
        p = os.path.join(r"C:\Windows\System32", "ktvisa32.dll")
        if os.path.isfile(p):
            _KEYSIGHT_VISA_CORE = p
    return _KEYSIGHT_VISA


def keysight_visa_core() -> Optional[str]:
    """Keysight VISA 核心 DLL（`ktvisa32.dll`）路径；准备环境后返回，找不到返回 None。"""
    prepare_keysight_visa()
    global _KEYSIGHT_VISA_CORE
    return _KEYSIGHT_VISA_CORE


# --- ctypes 直连 Keysight VISA 核心（GPIB 在本机的唯一可行通路）----------------
_VI_ATTR_TMO_VALUE = 0x3FFF001A
_VI_ATTR_TERMCHAR = 0x3FFF0018
_VI_ATTR_TERMCHAR_EN = 0x3FFF0038
_VI_SUCCESS_TERM_CHAR = 0x3FFF0005
_VI_SUCCESS_MAX_CNT = 0x3FFF0006
_VI_ERROR_TMO = -1073807339


class KeysightVisaTransport:
    """ctypes 直连 `ktvisa32.dll`（Keysight VISA 核心）——本机 82357B/GPIB 实测可行。

    为什么不用 pyvisa：本机 Keysight VISA 是 *secondary*，`visa32.dll` 名字在
    `IVI\\Win64\\bin`（NI 护照所在）与 `ktvisa\\ktbin` 两处都有，pyvisa 会解析到
    NI 那套 → `VI_ERROR_LIBRARY_NFOUND`。直连 `ktvisa32.dll` 绕开歧义，并且能直接
    用 `viClear()` 做 free-run 恢复（SICL/pyvisa 都没这么直接）。
    """

    def __init__(self, resource: str, timeout_s: float = 30.0,
                 chunk_size: int = 1 << 16, core_dll: Optional[str] = None):
        self.resource = resource
        self.timeout_s = float(timeout_s)
        self.chunk_size = int(chunk_size)
        self.core_dll = core_dll
        self._lib = None
        self._rm = ctypes.c_uint(0)
        self._session = ctypes.c_uint(0)

    # -- 绑定 vi* 原型 -------------------------------------------------------
    def _bind(self):
        lib = self._lib

        def f(name, argtypes, restype=ctypes.c_long):
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = argtypes, restype
            return fn

        self._viOpenDefaultRM = f("viOpenDefaultRM", [ctypes.POINTER(ctypes.c_uint)])
        self._viOpen = f("viOpen", [ctypes.c_uint, ctypes.c_char_p, ctypes.c_ulong,
                                    ctypes.c_ulong, ctypes.POINTER(ctypes.c_uint)])
        self._viClose = f("viClose", [ctypes.c_uint])
        self._viWrite = f("viWrite", [ctypes.c_uint, ctypes.c_char_p, ctypes.c_ulong,
                                      ctypes.POINTER(ctypes.c_ulong)])
        self._viRead = f("viRead", [ctypes.c_uint, ctypes.c_char_p, ctypes.c_ulong,
                                    ctypes.POINTER(ctypes.c_ulong)])
        self._viClear = f("viClear", [ctypes.c_uint])
        self._viSetAttribute = f("viSetAttribute", [ctypes.c_uint, ctypes.c_ulong,
                                                    ctypes.c_ulong])
        self._viStatusDesc = f("viStatusDesc", [ctypes.c_uint, ctypes.c_long,
                                                ctypes.c_char_p])

    def _desc(self, status: int) -> str:
        try:
            buf = ctypes.create_string_buffer(256)
            self._viStatusDesc(self._rm, status, buf)
            return buf.value.decode("ascii", "replace")[:120]
        except Exception:
            return ""

    def _check(self, status: int, what: str):
        if status < 0:
            raise TransportError(f"{what} 失败: {status} {self._desc(status)}")

    # -- 生命周期 ------------------------------------------------------------
    def open(self) -> "KeysightVisaTransport":
        if self._session.value:
            return self
        dll = self.core_dll or keysight_visa_core()
        if not dll:
            raise TransportError("未找到 ktvisa32.dll（Keysight VISA 核心）")
        self._lib = ctypes.WinDLL(dll)
        self._bind()
        self._check(self._viOpenDefaultRM(ctypes.byref(self._rm)), "viOpenDefaultRM")
        ses = ctypes.c_uint(0)
        self._check(self._viOpen(self._rm, self.resource.encode("ascii"), 0, 0,
                                 ctypes.byref(ses)), f"viOpen({self.resource})")
        self._session = ses
        self.set_timeout(self.timeout_s)
        # 3458A 用 LF 结尾：让 viRead 以 '\n' 为终止符
        try:
            self._viSetAttribute(self._session, _VI_ATTR_TERMCHAR, 0x0A)
            self._viSetAttribute(self._session, _VI_ATTR_TERMCHAR_EN, 1)
        except Exception:
            pass
        self.clear()
        time.sleep(SETTLE_S)
        return self

    def close(self) -> None:
        if self._session.value:
            try:
                self._viClose(self._session)
            except Exception:
                pass
            self._session = ctypes.c_uint(0)
        if self._rm.value:
            try:
                self._viClose(self._rm)
            except Exception:
                pass
            self._rm = ctypes.c_uint(0)

    @property
    def is_open(self) -> bool:
        return bool(self._session.value)

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    def _require(self) -> ctypes.c_uint:
        if not self._session.value:
            raise TransportError("3458A 未连接")
        return self._session

    # -- I/O -----------------------------------------------------------------
    def set_timeout(self, seconds: float) -> None:
        self.timeout_s = float(seconds)
        if self._session.value:
            self._viSetAttribute(self._session, _VI_ATTR_TMO_VALUE,
                                 int(self.timeout_s * 1000))

    def write(self, cmd: str) -> int:
        s = self._require()
        data = cmd.encode("ascii") if isinstance(cmd, str) else bytes(cmd)
        if not data.endswith(b"\n"):
            data += b"\n"
        n = ctypes.c_ulong(0)
        self._check(self._viWrite(s, data, len(data), ctypes.byref(n)), f"viWrite({cmd!r})")
        return int(n.value)

    def read(self, timeout_s: Optional[float] = None) -> str:
        s = self._require()
        if timeout_s is not None:
            self.set_timeout(timeout_s)
        try:
            chunks: list[bytes] = []
            while True:
                buf = ctypes.create_string_buffer(self.chunk_size)
                n = ctypes.c_ulong(0)
                st = self._viRead(s, buf, self.chunk_size, ctypes.byref(n))
                if n.value:
                    chunks.append(buf.raw[:n.value])
                data = b"".join(chunks)
                if b"\n" in data:
                    return data.decode("ascii", "replace").strip()
                if st in (_VI_SUCCESS_TERM_CHAR, _VI_SUCCESS_MAX_CNT):
                    continue
                if st < 0:
                    self._check(st, "viRead")
                if not n.value:
                    raise TransportError("viRead 无数据且未超时（意外状态）")
        finally:
            if timeout_s is not None:
                self.set_timeout(self.timeout_s)

    def read_bytes(self, count: int, timeout_s: Optional[float] = None) -> bytes:
        s = self._require()
        if timeout_s is not None:
            self.set_timeout(timeout_s)
        try:
            out = bytearray()
            while len(out) < count:
                buf = ctypes.create_string_buffer(self.chunk_size)
                n = ctypes.c_ulong(0)
                st = self._viRead(s, buf, min(self.chunk_size, count - len(out)),
                                  ctypes.byref(n))
                if n.value:
                    out.extend(buf.raw[:n.value])
                if st < 0 and st != _VI_ERROR_TMO:
                    self._check(st, "viRead(bytes)")
                if st < 0 or (not n.value and st != _VI_SUCCESS_MAX_CNT):
                    break
            if len(out) < count:
                raise TransportError(
                    f"binary 数据不完整：期望 {count} 字节，实得 {len(out)} 字节")
            return bytes(out)
        finally:
            if timeout_s is not None:
                self.set_timeout(self.timeout_s)

    def query(self, cmd: str, timeout_s: Optional[float] = None) -> str:
        self.write(cmd)
        return self.read(timeout_s)

    def clear(self) -> None:
        if self._session.value:
            try:
                self._viClear(self._session)
            except Exception:
                pass

    def ifc(self) -> None:
        """VISA 侧无独立 IFC；用 Device Clear 等价（3458A 实测足够停 free-run）。"""
        self.clear()

    def drain(self, max_rounds: int = DRAIN_MAX_ROUNDS,
              timeout_ms: int = DRAIN_TIMEOUT_MS) -> int:
        """有界清空残留输出（硬上限：轮数与单轮超时）。"""
        s = self._require()
        total = 0
        old = self.timeout_s
        self.set_timeout(timeout_ms / 1000.0)
        try:
            for _ in range(max_rounds):
                buf = ctypes.create_string_buffer(self.chunk_size)
                n = ctypes.c_ulong(0)
                st = self._viRead(s, buf, self.chunk_size, ctypes.byref(n))
                total += int(n.value)
                if st < 0 or not n.value:
                    break
        finally:
            self.set_timeout(old)
        return total


def parse_sicl_addr(resource: str, default: int = 9) -> int:
    """`sicl:gpib0,9` / `gpib0,9` / `GPIB0::9::INSTR` → 9（取不到用 default）。"""
    text = str(resource or "")
    if text.lower().startswith("sicl:"):
        text = text.split(":", 1)[1]
    if "," in text:
        try:
            return int(text.rsplit(",", 1)[-1])
        except ValueError:
            return default
    match = re.search(r"::(\d+)::", text) or re.search(r"(\d+)\s*$", text)
    return int(match.group(1)) if match else default


def is_sicl_resource(resource: Optional[str]) -> bool:
    """`sicl:` 前缀或 `gpib0,9` 这类逗号短形式 → SICL 通路。"""
    text = str(resource or "").strip()
    if not text:
        return False
    if text.lower().startswith("sicl:"):
        return True
    return "," in text and "::" not in text


def make_transport(resource: str, timeout_s: float = 30.0,
                   visalib: Optional[str] = None,
                   prefer_keysight_visa: bool = True) -> Transport:
    """按资源串形态建通路。

    * SICL 短形式（`sicl:gpib0,9`）→ `SiclTransport`；
    * Windows 下的 GPIB 资源 → **`KeysightVisaTransport`**（ctypes 直连 ktvisa32.dll；
      2026-09-23 本机实测这是 64 位 Python 唯一可行通路），Keysight VISA 不可用时
      退回 `PyVisaTransport`；
    * 其余（`visa://…`、USB、串口）→ `PyVisaTransport`。
    """
    if is_sicl_resource(resource):
        return SiclTransport(addr=parse_sicl_addr(resource), timeout_s=timeout_s)
    # 只对**本地** GPIB 资源用 Keysight VISA 直连；`visa://<host>/…` 是远端 VISA server，
    # 必须走 pyvisa（把远端地址喂给本机 ktvisa 是错的）。
    local_gpib = (prefer_keysight_visa and os.name == "nt"
                  and resource.strip().upper().startswith("GPIB")
                  and "://" not in resource)
    if local_gpib and keysight_visa_core():
        return KeysightVisaTransport(resource, timeout_s=timeout_s)
    return PyVisaTransport(resource, timeout_s=timeout_s, visalib=visalib,
                           prefer_keysight_visa=prefer_keysight_visa)
