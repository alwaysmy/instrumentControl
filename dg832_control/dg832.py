# -*- coding: utf-8 -*-
"""
DG832 控制库 — RIGOL DG800 系列函数/任意波形发生器（基于 VISA/SCPI，默认型号 DG832，多型号预留）

多型号预留：所有入口接受 model 参数（默认 DG832）。当前支持 DG800 全系列
（DG832 基准实测；DG831/DG822/DG821/DG812/DG811 命令集相同）。新增型号时
在 MODEL_REGISTRY 登记即可扩展。

用法：
    作为库:  from dg832 import DG832
             gen = DG832(model="DG832"); gen.connect(); gen.idn()
    命令行:  python dg832.py idn
             python dg832.py status
             python dg832.py sine 1000 2.5 0 90 --ch 1 --out on
             python dg832.py freq 1000 --ch 1
             python dg832.py out on --ch 1
             python dg832.py counter
依赖: pyvisa（需完整版 NI-VISA ≥ 24.x，不要用 Ultra Sigma 自带的旧版 IVI visa 3.2）
"""
import sys
import argparse

import pyvisa


# ============ 错误类型（供 MCP/调用方分类处理） ============
class DgError(Exception):
    """DG 控制库错误基类"""


class ProtectRequiredError(ValueError, DgError):
    """强制流程错误：未开启有效电压保护就设置幅度/偏移/输出"""


class ProtectRangeError(ValueError, DgError):
    """超出电压保护范围"""


class ParamValidationError(ValueError, DgError):
    """基本参数校验失败（数值不合法）"""


class ModelUnsupportedError(ValueError, DgError):
    """型号未在 MODEL_REGISTRY 登记"""


class ConnectionError_(RuntimeError, DgError):
    """连接失败（未找到设备/无法打开资源）"""

VENDOR_ID_RIGOL = "0x1AB1"   # RIGOL USB VID
# DG832 实际 USB PID 为 0x0643（手册示例为 0x0642，以实测为准）

# ============ 型号注册表（多型号预留扩展点） ============
# 新增型号时：在此添加条目，并按需细化连接参数（pid）或命令集适配。
# pid=None 表示不按 PID 过滤，连接时自动发现 RIGOL 设备。
# 本套 SCPI 路径以 DG832 为基准验证；DG800 系列其余型号命令集相同，已列入支持。
MODEL_REGISTRY = {
    "DG832": {"vid": "0x1AB1", "pid": "0x0643", "channels": 2, "max_freq_mhz": 35, "note": "基准型号，实测"},
    "DG831": {"vid": "0x1AB1", "pid": None, "channels": 1, "max_freq_mhz": 35, "note": "同命令集，未实测"},
    "DG822": {"vid": "0x1AB1", "pid": None, "channels": 2, "max_freq_mhz": 25, "note": "同命令集，未实测"},
    "DG821": {"vid": "0x1AB1", "pid": None, "channels": 1, "max_freq_mhz": 25, "note": "同命令集，未实测"},
    "DG812": {"vid": "0x1AB1", "pid": None, "channels": 2, "max_freq_mhz": 10, "note": "同命令集，未实测"},
    "DG811": {"vid": "0x1AB1", "pid": None, "channels": 1, "max_freq_mhz": 10, "note": "同命令集，未实测"},
}
DEFAULT_MODEL = "DG832"


def resolve_model(model):
    """型号规范化与校验：返回标准化型号名；未知型号抛 ModelUnsupportedError（多型号预留入口）"""
    m = (model or DEFAULT_MODEL).strip().upper()
    if m not in MODEL_REGISTRY:
        raise ModelUnsupportedError(
            f"型号 {model} 尚未适配；当前支持: {', '.join(sorted(MODEL_REGISTRY))}"
            "（可在 MODEL_REGISTRY 中登记后扩展）"
        )
    return m


def discover(timeout_ms=1200, check_idn=True):
    """发现本机所有 VISA 仪器资源（兼容 USB / 以太网 / 串口 / GPIB，pyvisa 已封装）。

    返回 [{resource, kind, online, idn, error}, ...]：
      kind: usb | ethernet | serial | gpib | other
      online: 对 INSTR 类资源尝试 *IDN? 判定（串口默认不自动测，online=None）
    用于确认仪器是否在线、当前有哪些设备。
    """
    rm = pyvisa.ResourceManager()
    results = []
    try:
        try:
            resources = rm.list_resources()
        except Exception as e:
            return [{"resource": None, "kind": None, "online": None, "idn": None,
                     "error": f"列出 VISA 资源失败（确认已安装完整版 NI-VISA）: {e}"}]
        for r in resources:
            up = r.upper()
            if up.startswith("USB"):
                kind = "usb"
            elif up.startswith("TCPIP"):
                kind = "ethernet"
            elif up.startswith("ASRL"):
                kind = "serial"
            elif up.startswith("GPIB"):
                kind = "gpib"
            else:
                kind = "other"
            entry = {"resource": r, "kind": kind, "online": None, "idn": None, "error": None}
            if check_idn and kind in ("usb", "ethernet", "gpib") and "INSTR" in up:
                instr = None
                try:
                    instr = rm.open_resource(r)
                    instr.timeout = timeout_ms
                    idn = instr.query("*IDN?").strip()
                    entry["online"] = bool(idn)
                    entry["idn"] = idn
                except Exception as e:
                    entry["error"] = type(e).__name__
                finally:
                    if instr is not None:
                        try:
                            instr.close()
                        except Exception:
                            pass
            results.append(entry)
    finally:
        try:
            rm.close()
        except Exception:
            pass
    return results


# 波形类型 -> SCPI 缩写（:SOUR{n}:FUNC[:SHAPe] 取值）
SHAPE_SCPI = {
    "sine": "SIN", "sin": "SIN", "sinusoid": "SIN",
    "square": "SQU", "sqr": "SQU",
    "ramp": "RAMP",
    "pulse": "PULS", "pul": "PULS",
    "dc": "DC",
    "noise": "NOIS", "nois": "NOIS",
    "prbs": "PRBS",
    "arb": "USER", "user": "USER", "arbitrary": "USER",
    "harmonic": "HARM", "harm": "HARM",
    "dualtone": "DUAL", "dual": "DUAL",
    "rs232": "RS232",
    "sequence": "SEQ", "seq": "SEQ",
}
SHAPE_APPL = {  # :SOUR{n}:APPL:<XXX> 快速设置后缀
    "sine": "SIN", "sin": "SIN", "sinusoid": "SIN",
    "square": "SQU", "sqr": "SQU",
    "ramp": "RAMP",
    "pulse": "PULS", "pul": "PULS",
    "dc": "DC",
    "noise": "NOIS", "nois": "NOIS",
    "prbs": "PRBS",
    "user": "USER", "arb": "USER", "arbitrary": "USER",
    "harmonic": "HARM", "harm": "HARM",
    "dualtone": "DUAL", "dual": "DUAL",
    "rs232": "RS232",
    "sequence": "SEQ", "seq": "SEQ",
}
# 各波形 APPL 命令的参数顺序模板（编程手册核对）：
#   f=频率/占位, a=幅度, o=偏移, p=相位, s=采样率
#   正弦/方波/锯齿/脉冲/谐波/任意波: freq,amp,offset,phase
#   序列: sample_rate,amp,offset,phase；DC/双音/PRBS: freq,amp,offset（无相位）
#   噪声/RS232: amp,offset（无频率）
APPL_PARAMS = {
    "sine": "faop", "sin": "faop", "sinusoid": "faop",
    "square": "faop", "sqr": "faop",
    "ramp": "faop",
    "pulse": "faop", "pul": "faop",
    "harmonic": "faop", "harm": "faop",
    "user": "faop", "arb": "faop", "arbitrary": "faop",
    "sequence": "saop", "seq": "saop",
    "dc": "fao",
    "dualtone": "fao", "dual": "fao",
    "prbs": "fao",
    "noise": "ao", "nois": "ao",
    "rs232": "ao",
}

# 各波形频率上限（Hz）——编程手册表 2-1（按型号分组）。
# 注意：只有正弦的上限 = 型号上限；方波/锯齿/脉冲等上限更低（DG832 实测：
# square 35MHz 会被设备静默钳制为 10MHz，曾踩坑）。key 用 SHAPE_APPL 的规范名。
WAVEFORM_FREQ_LIMITS = {
    # DG832/DG831（型号上限 35MHz）
    35: {"sine": 35e6, "square": 10e6, "ramp": 1e6, "pulse": 10e6, "harmonic": 15e6,
         "dualtone": 20e6, "user": 10e6, "prbs": 30e6},
    # DG822/DG821（型号上限 25MHz）
    25: {"sine": 25e6, "square": 10e6, "ramp": 500e3, "pulse": 10e6, "harmonic": 10e6,
         "dualtone": 20e6, "user": 10e6, "prbs": 20e6},
    # DG812/DG811（型号上限 10MHz）
    10: {"sine": 10e6, "square": 5e6, "ramp": 200e3, "pulse": 5e6, "harmonic": 5e6,
         "dualtone": 10e6, "user": 5e6, "prbs": 10e6},
}
# FUNC? 返回 -> 规范波形名（用于 set_freq 按当前波形校验）
_FUNC_TO_SHAPE = {"SIN": "sine", "SQU": "square", "RAMP": "ramp", "PULS": "pulse",
                  "DC": "dc", "NOIS": "noise", "USER": "user", "HARM": "harmonic",
                  "DUAL": "dualtone", "RS232": "rs232", "PRBS": "prbs", "SEQ": "sequence"}

# 扫频支持的波形（编程手册 2-126：正弦/方波/锯齿/任意波；脉冲、噪声不允许）
SWEEP_SHAPES = ("sine", "square", "ramp", "user")
# 扫频间隔/触发源取值 -> SCPI 缩写
SWEEP_SPACING = {"lin": "LIN", "linear": "LIN", "log": "LOG", "logarithmic": "LOG",
                 "step": "STEP", "stepped": "STEP"}
SWEEP_TRIG = {"int": "INT", "internal": "INT", "ext": "EXT", "external": "EXT",
              "man": "MAN", "manual": "MAN"}
SWEEP_TRIG_SLOPE = {"pos": "POS", "positive": "POS", "neg": "NEG", "negative": "NEG"}


def _wave_freq_limit(model, shape):
    """按型号+波形返回频率上限（Hz）；无频率参数/未知则返回 None"""
    spec = MODEL_REGISTRY.get(model, {})
    table = WAVEFORM_FREQ_LIMITS.get(spec.get("max_freq_mhz"))
    if not table:
        return None
    return table.get(shape)


class DG832:
    """RIGOL DG800 系列信号源控制封装（SCPI over VISA，默认 DG832，多型号见 MODEL_REGISTRY）"""

    def __init__(self, resource=None, timeout_ms=3000, model=DEFAULT_MODEL):
        self.model = resolve_model(model)
        self.rm = pyvisa.ResourceManager()
        self.resource = resource
        self.instr = None
        self.timeout_ms = timeout_ms

    # ---------- 连接管理 ----------
    def find_resource(self):
        """按型号查找 VISA 资源（vid/pid 来自 MODEL_REGISTRY），返回资源名或 None"""
        spec = MODEL_REGISTRY.get(self.model, {})
        vid = spec.get("vid")
        pid = spec.get("pid")
        try:
            resources = self.rm.list_resources()
        except Exception as e:
            raise ConnectionError_(f"列出 VISA 资源失败（确认已安装完整版 NI-VISA）: {e}")
        for r in resources:
            r_up = r.upper()
            if "INSTR" in r_up and vid.upper() in r_up and (not pid or pid.upper() in r_up):
                return r
        # 兜底：任意 RIGOL VID 的 INSTR 资源
        for r in resources:
            r_up = r.upper()
            if vid.upper() in r_up and "INSTR" in r_up:
                return r
        for r in resources:
            if "INSTR" in r.upper():
                return r
        return None

    def connect(self, resource=None):
        """连接设备；resource 为空时按型号自动查找 RIGOL 设备"""
        if resource:
            self.resource = resource
        if not self.resource:
            self.resource = self.find_resource()
        if not self.resource:
            raise ConnectionError_(f"未找到 {self.model} 设备资源，请检查 USB 连接与驱动")
        try:
            self.instr = self.rm.open_resource(self.resource)
            self.instr.timeout = self.timeout_ms
            self.instr.clear()
        except Exception as e:
            raise ConnectionError_(f"打开 {self.model} 设备失败: {e}（检查 USB 连接与驱动）")
        return self.resource

    def close(self):
        if self.instr is not None:
            try:
                self.instr.close()
            finally:
                self.instr = None
        try:
            self.rm.close()
        except Exception:
            pass

    def __enter__(self):
        if self.instr is None:
            self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------- 底层 ----------
    def write(self, cmd: str):
        self.instr.write(cmd)

    def query(self, cmd: str, strip=True) -> str:
        raw = self.instr.query(cmd)
        return raw.strip() if strip else raw

    def check_error(self, clear=True) -> list:
        """读取并清空错误队列，返回 [(编号, 内容), ...]"""
        errors = []
        for _ in range(10):
            resp = self.query(":SYST:ERR?")
            if resp.startswith("0"):
                break
            errors.append(resp)
        return errors

    # ---------- 信息 ----------
    def idn(self) -> str:
        return self.query("*IDN?")

    # ---------- 参数校验（防误操作 / 防超压） ----------
    def _protect_active(self, ch) -> tuple:
        """强制保护检查：返回 (是否有效开启, 原因/提示)。
        强制流程要求：设置幅度/偏移或打开输出前，电压保护必须已开启且范围有效（high > low）。
        读取失败抛 ConnectionError_（通信问题走重试，而非伪装成"未开保护"）。"""
        try:
            st = self.query(f":OUTP{ch}:VOLL:STAT?").strip()
            high = float(self.query(f":OUTP{ch}:VOLL:HIGH?"))
            low = float(self.query(f":OUTP{ch}:VOLL:LOW?"))
        except Exception as e:
            raise ConnectionError_(f"读取电压保护状态失败: {e}")
        if st not in ("ON", "1"):
            return False, (f"强制保护未开启：设置幅度/偏移或打开输出前，必须先执行 "
                           f"instrument_protect(ch={ch}, state=True) 开启电压保护（可同时设 high/low）")
        if high <= low:
            return False, (f"电压保护范围无效（high={high} <= low={low}）：请先执行 "
                           f"instrument_protect(ch={ch}, high=…, low=…) 设置 high > low")
        return True, ""

    def _require_protect(self, ch):
        """强制保护检查，不通过抛 ProtectRequiredError"""
        ok, reason = self._protect_active(ch)
        if not ok:
            raise ProtectRequiredError(reason)
        return True

    def _validate_params(self, freq=None, amp=None, offset=None, phase=None, sample_rate=None, shape=None):
        """基本数值校验；越界抛 ParamValidationError（不合法值一律拒绝，不做静默裁剪）。
        shape 已知时（set_wave/set_freq）按波形频率上限校验（方波/锯齿等上限低于型号上限）。"""
        spec = MODEL_REGISTRY.get(self.model, {})
        if sample_rate is not None:
            if not (2e3 <= sample_rate <= 125e6):
                raise ParamValidationError(f"序列采样率必须在 2kSa/s~125MSa/s，收到 {sample_rate}")
        if freq is not None:
            if freq <= 0:
                raise ParamValidationError(f"频率必须 > 0，收到 {freq}")
            max_hz = spec.get("max_freq_mhz")
            if max_hz and freq > max_hz * 1e6:
                raise ParamValidationError(f"频率 {freq}Hz 超出 {self.model} 上限 {max_hz} MHz")
            if shape is not None:
                lim = _wave_freq_limit(self.model, shape)
                if lim and freq > lim:
                    raise ParamValidationError(
                        f"频率 {freq:g}Hz 超出 {shape} 波形上限 {lim/1e6:g}MHz"
                        f"（型号 {self.model} 上限 {max_hz}MHz 仅正弦适用；"
                        f"超限会被设备静默钳制，曾踩坑 square 35MHz→10MHz）")
        if amp is not None and amp < 0:
            raise ParamValidationError(f"幅度必须 ≥ 0 Vpp，收到 {amp}")
        if offset is not None and abs(offset) > 10:
            raise ParamValidationError(f"偏移超出 ±10V（高阻下的典型上限，受负载/幅度限制，以设备实际为准）: {offset}")
        if phase is not None and not (0 <= phase <= 360):
            raise ParamValidationError(f"相位必须在 0~360°，收到 {phase}")

    def check_amp_limit(self, ch, amp=None, offset=None):
        """电压保护校验：若保护开启且范围有效，检查 (amp Vpp, offset Vdc) 是否越界。
        返回 (ok, message)；越界时 ok=False，message 直接给出越界计算与可选调整方案。"""
        try:
            st = self.query(f":OUTP{ch}:VOLL:STAT?").strip()
            high = float(self.query(f":OUTP{ch}:VOLL:HIGH?"))
            low = float(self.query(f":OUTP{ch}:VOLL:LOW?"))
        except Exception as e:
            raise ConnectionError_(f"读取电压保护状态失败: {e}")
        if st not in ("ON", "1") or high <= low:
            return True, None  # 保护未开启或范围无效，不约束
        if amp is not None and amp > high - low + 1e-9:
            return False, (f"幅度 {amp:.3f}Vpp 超出保护范围可用幅度（上限-下限 = {high - low:.3f}V，"
                           f"保护内允许的最大幅度）；请调低幅度至 ≤ {high - low:.3f}Vpp")
        if amp is not None and offset is not None and amp > 1e-9:
            v_hi = offset + amp / 2
            v_lo = offset - amp / 2
            if v_hi > high + 1e-9 or v_lo < low - 1e-9:
                # 直接算出越界原因（包络 = offset ± amp/2），只给不破坏保护的调整方案
                why = []
                if v_lo < low - 1e-9:
                    why.append(f"包络下限 {v_lo:.3f}V < 保护下限 {low:.3f}V（超 {low - v_lo:.3f}V）")
                if v_hi > high + 1e-9:
                    why.append(f"包络上限 {v_hi:.3f}V > 保护上限 {high:.3f}V（超 {v_hi - high:.3f}V）")
                amp_max = max(0.0, 2 * min(offset - low, high - offset))
                off_min = low + amp / 2
                off_max = high - amp / 2
                if amp_max > 1e-9:
                    opt_amp = f"请调低幅度至 ≤ {amp_max:.3f}Vpp"
                else:
                    opt_amp = "保持此偏移时任何幅度都越界（需先调偏移）"
                return False, (
                    f"幅度/偏移使瞬时电平 {v_lo:.3f}~{v_hi:.3f}V 超出保护范围 [{low:.3f}V, {high:.3f}V]"
                    f"（{'；'.join(why)}）。{opt_amp}，或将偏移调至 [{off_min:.3f}, {off_max:.3f}]V 内"
                )
        elif offset is not None and not (low - 1e-9 <= offset <= high + 1e-9):
            if offset < low:
                side = f"低于保护下限 {low:.3f}V（差 {low - offset:.3f}V）"
            else:
                side = f"高于保护上限 {high:.3f}V（差 {offset - high:.3f}V）"
            return False, (f"偏移 {offset:.3f}V 超出保护范围 [{low:.3f}V, {high:.3f}V]（{side}）；"
                           f"请将偏移调至 [{low:.3f}, {high:.3f}]V 内")
        return True, None

    # ---------- 波形与参数 ----------
    def _config_snapshot(self, ch) -> dict:
        """读取通道当前波形配置快照（set_dc_only 返回给调用方，切回时显式传参用）"""
        parts = []
        try:
            parts = self.query(f":SOUR{ch}:APPL?").strip().strip('"').split(",")
        except Exception:
            pass

        def _num(i):
            if i < len(parts) and parts[i] not in ("DEF", ""):
                try:
                    return float(parts[i])
                except ValueError:
                    pass
            return None

        return {
            "shape": _FUNC_TO_SHAPE.get(parts[0].strip().upper()) if parts else None,
            "freq": _num(1), "amp": _num(2), "offset": _num(3), "phase": _num(4),
        }

    def set_wave(self, ch, shape, freq=None, amp=None, offset=None, phase=None, sample_rate=None):
        """快速设置波形。shape: sine/square/ramp/pulse/dc/noise/prbs/user/harmonic/dualtone/rs232/sequence。
        按各波形的 APPL 参数模板生成命令；省略的参数保持当前值（读取当前配置填充，而非重置为默认）。
        注意：从 DC 切回非 DC 时，DC 下 APPL? 的 freq/amp 是 DEF 占位，省略参数无法保持原值——
        如需保留切换前的参数，请用 set_dc_only 返回的 restore 值显式传参（不隐式恢复）。"""
        key = shape.lower()
        if key not in SHAPE_APPL:
            raise ParamValidationError(f"不支持的波形: {shape}（可用: {sorted(set(SHAPE_APPL))}）")
        template = APPL_PARAMS[key]
        # sequence 的首参数是采样率：sample_rate 优先，未给时用 freq 位置值
        sr = sample_rate if sample_rate is not None else (freq if "s" in template else None)
        self._validate_params(freq=(None if "s" in template else freq), amp=amp,
                              offset=offset, phase=phase, sample_rate=sr, shape=key)
        explicit_voltage = amp is not None or offset is not None
        values = {"f": freq, "a": amp, "o": offset, "p": phase, "s": sr}
        self._fill_keep(ch, template, values)
        if explicit_voltage:
            self._require_protect(ch)
            # DC 波形的 freq/amp 仅占位符（手册 4071 行），瞬时电平 = offset，按 amp=0 参与保护校验
            check_amp = 0.0 if key == "dc" else values["a"]
            ok2, msg = self.check_amp_limit(ch, amp=check_amp, offset=values["o"])
            if not ok2:
                raise ProtectRangeError(msg)
        args = []
        for code in template:
            v = values[code]
            args.append(str(v) if v is not None else "DEF")
        cmd = f":SOUR{ch}:APPL:{SHAPE_APPL[key]} {','.join(args)}"
        if key == "dc":
            # DC 波形的幅度是占位符（设备端会忽略 APPL:DC 的 amp 参数，保留残留幅度）。
            # 残留幅度会使设备按 offset±amp/2 钳制 OFFS 写入窗口（曾误判为"固件锁定 OFFS"）。
            # 必须先清掉幅度占位符再写 APPL:DC，否则 offset 会被钳制到窗口边界（如 0.5 被钳成 1.0）。
            self.write(f":SOUR{ch}:VOLT 0")
        self.write(cmd)
        return self.query(f":SOUR{ch}:APPL?")

    # APPL? 返回字段在逗号分隔布局中的位置（freq/amp/offset/phase；DC 为 4 段无 phase；NOISE 为 5 段）
    # s=sequence 采样率，对应返回首段（索引 1）
    _APPL_QIDX = {"f": 1, "a": 2, "o": 3, "p": 4, "s": 1}

    def _fill_keep(self, ch, template, values):
        """省略参数保持当前值：读取当前 APPL?，用当前值填充 None 项；当前为 DEF/占位则保持 DEF"""
        try:
            parts = self.query(f":SOUR{ch}:APPL?").strip().strip('"').split(",")
        except Exception:
            return
        for code in template:
            if values[code] is None:
                i = self._APPL_QIDX[code]
                if i < len(parts) and parts[i] not in ("DEF", ""):
                    try:
                        values[code] = float(parts[i])
                    except ValueError:
                        pass

    def set_dc_only(self, ch, level):
        """DC 专用切换入口：设置直流电平（V），返回切换前波形配置快照（restore），
        切回非 DC 时请用 restore 值**显式**传参（不隐式恢复，避免非预期的写入；
        已在 DC 时仅修改电平，restore 为 None）。
        返回 {"value": <设备实际电平>, "restore": <切换前配置快照|None>, "appl": <APPL?>, "note": <提示|None>}"""
        snapshot = self._config_snapshot(ch) if not self._is_dc(ch) else None
        appl = self.set_wave(ch, "dc", offset=level)
        actual = self.query(f":SOUR{ch}:VOLT:OFFS?")
        note = None
        try:
            if abs(float(actual) - level) > 1e-6:
                note = f"电平 {level:g}V 被设备钳制为 {float(actual):g}V"
        except (TypeError, ValueError):
            pass
        return {"value": actual, "restore": snapshot, "appl": appl, "note": note}

    def set_shape(self, ch, shape):
        """仅切换波形类型（保留其他参数）"""
        key = shape.lower()
        if key not in SHAPE_SCPI:
            raise ParamValidationError(f"不支持的波形: {shape}")
        self.write(f":SOUR{ch}:FUNC {SHAPE_SCPI[key]}")
        return self.query(f":SOUR{ch}:FUNC?")

    def _current_shape(self, ch) -> str | None:
        """查询当前波形（规范名，如 sine/square/dc）；查询失败返回 None"""
        try:
            return _FUNC_TO_SHAPE.get(self.query(f":SOUR{ch}:FUNC?").strip().upper())
        except Exception:
            return None

    def set_freq(self, ch, freq):
        """设置频率。按当前波形校验频率上限（方波/锯齿等上限低于型号上限，超限会被设备
        静默钳制）；写后回读检测设备端钳制（频率被钳/幅度被自动调整）并返回 note 提示。
        返回 {"value": <设备实际频率>, "note": <提示|None>}"""
        shape = self._current_shape(ch)
        self._validate_params(freq=freq, shape=shape)
        try:
            amp_before = float(self.query(f":SOUR{ch}:VOLT?"))
        except Exception:
            amp_before = None
        self.write(f":SOUR{ch}:FREQ {freq}")
        actual = self.query(f":SOUR{ch}:FREQ?")
        note = None
        try:
            notes = []
            if abs(float(actual) - freq) > 1e-6:
                notes.append(f"频率 {freq:g}Hz 被设备钳制为 {float(actual):g}Hz"
                             f"（{shape or '当前'}波形频率上限）")
            if amp_before is not None:
                amp_after = float(self.query(f":SOUR{ch}:VOLT?"))
                if abs(amp_after - amp_before) > 1e-6:
                    notes.append(f"频率改变后幅度被设备自动调整: {amp_before:g}Vpp -> {amp_after:g}Vpp")
            if notes:
                note = "；".join(notes)
        except (TypeError, ValueError):
            pass
        return {"value": actual, "note": note}

    def _is_dc(self, ch) -> bool:
        """当前通道波形是否为 DC（DC 下幅度是占位符，瞬时电平 = 偏移）"""
        try:
            return self.query(f":SOUR{ch}:FUNC?").strip().upper() == "DC"
        except Exception:
            return False

    def set_amp(self, ch, amp):
        """设置幅度。前校验（保护范围）+ 写后回读检测设备端钳制（频率/负载相关上限）。
        返回 {"value": <设备实际幅度>, "note": <提示|None>}"""
        self._validate_params(amp=amp)
        if self._is_dc(ch):
            raise ParamValidationError(
                f"CH{ch} 当前为 DC 波形：幅度是占位符（无意义），直流电平请用 "
                f"set_offset / instrument_set_param(ch, 'offset', …) 设置"
            )
        self._require_protect(ch)
        try:
            cur_offset = float(self.query(f":SOUR{ch}:VOLT:OFFS?"))
        except Exception:
            cur_offset = None
        ok2, msg = self.check_amp_limit(ch, amp=amp, offset=cur_offset)
        if not ok2:
            raise ProtectRangeError(msg)
        self.write(f":SOUR{ch}:VOLT {amp}")
        actual = self.query(f":SOUR{ch}:VOLT?")
        note = None
        try:
            if abs(float(actual) - amp) > 1e-6:
                note = (f"幅度 {amp:g}Vpp 被设备钳制为 {float(actual):g}Vpp"
                        f"（频率/负载相关幅度上限）")
        except (TypeError, ValueError):
            pass
        return {"value": actual, "note": note}

    def set_offset(self, ch, offset):
        """设置偏移电压。DC 模式走 VOLT 0 + APPL:DC 规范路径（直接 VOLT:OFFS 存在设备端
        "寄存器更新但输出不刷新"的可疑行为，APPL:DC 是手册规范路径，双保险）；
        非 DC 模式按保护语义校验瞬时包络 offset±amp/2 必须在保护范围内。
        返回 {"value": <设备实际偏移>, "note": <提示|None>}"""
        self._validate_params(offset=offset)
        self._require_protect(ch)
        if self._is_dc(ch):
            # DC：瞬时电平 = 偏移（按 amp=0 校验）；先 VOLT 0 清残留幅度占位符
            # （解除设备端 offset±amp/2 钳制窗口），再 APPL:DC 写电平
            ok2, msg = self.check_amp_limit(ch, amp=0.0, offset=offset)
            if not ok2:
                raise ProtectRangeError(msg)
            self.write(f":SOUR{ch}:VOLT 0")
            self.write(f":SOUR{ch}:APPL:DC DEF,DEF,{offset}")
            actual = self.query(f":SOUR{ch}:VOLT:OFFS?")
        else:
            # 非 DC：保护语义要求瞬时包络 offset±amp/2 在 [low, high] 内。
            # （另一会话曾疑为"误判"，实测为正确行为：SIN 0.5Vpp + 保护 [0,2.5] 时
            #  offset 0 的包络 -0.25V 越界被拒；需要负电平请调整保护范围而非绕过校验）
            try:
                cur_amp = float(self.query(f":SOUR{ch}:VOLT?"))
            except Exception:
                cur_amp = None
            ok2, msg = self.check_amp_limit(ch, amp=cur_amp, offset=offset)
            if not ok2:
                raise ProtectRangeError(msg)
            self.write(f":SOUR{ch}:VOLT:OFFS {offset}")
            actual = self.query(f":SOUR{ch}:VOLT:OFFS?")
        note = None
        try:
            if abs(float(actual) - offset) > 1e-6:
                note = (f"偏移 {offset:g}V 被设备钳制为 {float(actual):g}V"
                        f"（频率/负载相关偏移上限）")
        except (TypeError, ValueError):
            pass
        return {"value": actual, "note": note}

    def set_phase(self, ch, phase):
        self._validate_params(phase=phase)
        self.write(f":SOUR{ch}:PHAS {phase}")
        return self.query(f":SOUR{ch}:PHAS?")

    def get_wave_config(self, ch) -> dict:
        """读取通道当前波形配置（APPL? 返回 波形,频率,幅度,偏移,相位）"""
        resp = self.query(f":SOUR{ch}:APPL?").strip().strip('"')
        parts = resp.split(",")
        return {
            "ch": ch,
            "shape": parts[0],
            "freq": parts[1] if len(parts) > 1 else None,
            "amp": parts[2] if len(parts) > 2 else None,
            "offset": parts[3] if len(parts) > 3 else None,
            "phase": parts[4] if len(parts) > 4 else None,
            "output": self.query(f":OUTP{ch}?"),
            "load": self.query(f":OUTP{ch}:LOAD?"),
        }

    # ---------- 输出 ----------
    def get_voltage_limit(self, ch) -> dict:
        """查询电压保护配置：{state, high, low}（V）"""
        return {
            "state": self.query(f":OUTP{ch}:VOLL:STAT?"),
            "high": self.query(f":OUTP{ch}:VOLL:HIGH?"),
            "low": self.query(f":OUTP{ch}:VOLL:LOW?"),
        }

    def set_voltage_limit(self, ch, high=None, low=None, state=None) -> dict:
        """设置输出电压保护（防超压）：high/low 为输出电平上限/下限（V），state 为开关。
        省略的参数保持当前值；全部省略 = 仅查询。设置后 set_wave/set_amp/set_offset 会受约束。"""
        if high is not None or low is not None:
            try:
                cur_high = float(self.query(f":OUTP{ch}:VOLL:HIGH?")) if high is None else high
                cur_low = float(self.query(f":OUTP{ch}:VOLL:LOW?")) if low is None else low
            except Exception:
                cur_high, cur_low = high, low
            if cur_high is not None and cur_low is not None and cur_high <= cur_low:
                raise ParamValidationError(f"上限 HIGH 必须 > 下限 LOW（{cur_high} <= {cur_low}）")
        if high is not None:
            self.write(f":OUTP{ch}:VOLL:HIGH {high}")
        if low is not None:
            self.write(f":OUTP{ch}:VOLL:LOW {low}")
        if state is not None:
            self.write(f":OUTP{ch}:VOLL:STAT {'ON' if state else 'OFF'}")
        result = self.get_voltage_limit(ch)
        # 固件钳制检测：请求值与实际不符时提示（当前输出电平过高会钳制保护范围）
        note = None
        try:
            if high is not None and abs(float(result["high"]) - high) > 1e-6:
                note = (f"high 请求 {high}V 被设备钳制为 {float(result['high']):g}V"
                        f"（当前输出电平过高）；请先调低幅度/偏移再设保护")
            elif low is not None and abs(float(result["low"]) - low) > 1e-6:
                note = (f"low 请求 {low}V 被设备钳制为 {float(result['low']):g}V"
                        f"（当前输出电平过高）；请先调低幅度/偏移再设保护")
        except (TypeError, ValueError):
            pass
        if note:
            result["note"] = note
        return result

    def output(self, ch, on: bool) -> str:
        """开关输出。打开输出前强制要求电压保护已开启（防止未设保护就输出）。"""
        if on:
            self._require_protect(ch)
        state = "ON" if on else "OFF"
        self.write(f":OUTP{ch} {state}")
        return self.query(f":OUTP{ch}?")

    def set_load(self, ch, ohms):
        """设置负载阻抗（Ω）；ohms=None/'inf'/'high' 表示高阻。
        写后检测设备端因阻抗改变对幅度/偏移的自动调整（手册：无效参数自动设为新上限）。
        返回 {"value": <设备实际负载>, "note": <提示|None>}"""
        val = "INF" if ohms in (None, "inf", "INF", "high") else str(ohms)
        try:
            amp_before = float(self.query(f":SOUR{ch}:VOLT?"))
            off_before = float(self.query(f":SOUR{ch}:VOLT:OFFS?"))
        except Exception:
            amp_before = off_before = None
        self.write(f":OUTP{ch}:LOAD {val}")
        actual = self.query(f":OUTP{ch}:LOAD?")
        note = None
        try:
            if amp_before is not None and off_before is not None:
                amp_after = float(self.query(f":SOUR{ch}:VOLT?"))
                off_after = float(self.query(f":SOUR{ch}:VOLT:OFFS?"))
                if abs(amp_after - amp_before) > 1e-6 or abs(off_after - off_before) > 1e-6:
                    note = (f"负载切换后幅度/偏移被设备自动调整: "
                            f"{amp_before:g}Vpp/{off_before:g}V -> {amp_after:g}Vpp/{off_after:g}V")
        except (TypeError, ValueError):
            pass
        return {"value": actual, "note": note}

    def channel_copy(self, src=1, dst=2):
        self.write(f":SYST:CSC CH{src},CH{dst}")

    # ---------- 扫频 ----------
    def get_sweep_config(self, ch) -> dict:
        """查询指定通道扫频配置（频率扫频）：state/start/stop/time/spacing/step/
        htime_start/htime_stop/rtime/trig_source/trig_slope"""
        return {
            "state": self.query(f":SOUR{ch}:SWE:STAT?"),
            "start": self.query(f":SOUR{ch}:FREQ:STAR?"),
            "stop": self.query(f":SOUR{ch}:FREQ:STOP?"),
            "time": self.query(f":SOUR{ch}:SWE:TIME?"),
            "spacing": self.query(f":SOUR{ch}:SWE:SPAC?"),
            "step": self.query(f":SOUR{ch}:SWE:STEP?"),
            "htime_start": self.query(f":SOUR{ch}:SWE:HTIM:STAR?"),
            "htime_stop": self.query(f":SOUR{ch}:SWE:HTIM:STOP?"),
            "rtime": self.query(f":SOUR{ch}:SWE:RTIM?"),
            "trig_source": self.query(f":SOUR{ch}:SWE:TRIG:SOUR?"),
            "trig_slope": self.query(f":SOUR{ch}:SWE:TRIG:SLOP?"),
        }

    def set_sweep(self, ch, start=None, stop=None, time=None, spacing=None, step=None,
                  htime_start=None, htime_stop=None, rtime=None, trig_source=None,
                  trig_slope=None, center=None, span=None, state=None):
        """配置/开启/查询扫频（频率扫频；仅 sine/square/ramp/user 支持；开启时设备会自动
        关闭调制/脉冲串，谐波打开时无法开启）。全部参数省略且 state=None = 仅查询。
        可设置参数（编程手册 :SOURce:SWEep 命令组）：
          start/stop: 起始/终止频率 Hz（双向扫频均可，须在当前波形频率上限内）
          center/span: 中心频率/频率跨度 Hz（与 start/stop 二选一，设备自动换算）
          time: 扫频时间 s（1ms~500s）；spacing: lin/log/step；step: 步进数 2~1024（仅 step 间隔）
          htime_start/htime_stop/rtime: 起始保持/终止保持/返回时间 s
          trig_source: int/ext/man 触发源；trig_slope: pos/neg 外部触发边沿
          state: True 开启 / False 关闭 / None 不改变
        **注意（实测）**：FREQ:STAR/STOP 边界频率在扫频关闭时写入会被设备拒绝（-220），
        库会自动"先开扫频→写参数→按需恢复原开关状态"。
        返回当前扫频配置（见 get_sweep_config）"""
        if center is not None and (start is not None or stop is not None):
            raise ParamValidationError("start/stop 与 center/span 只能选一组设置")
        if span is not None and (start is not None or stop is not None):
            raise ParamValidationError("start/stop 与 center/span 只能选一组设置")
        write_params = any(v is not None for v in (start, stop, time, spacing, step,
                                                   htime_start, htime_stop, rtime,
                                                   trig_source, trig_slope, center, span))
        if not write_params and state is None:
            return self.get_sweep_config(ch)
        shape = self._current_shape(ch)
        if shape not in SWEEP_SHAPES:
            raise ParamValidationError(
                f"当前波形 {shape or '未知'} 不支持扫频（仅 {', '.join(SWEEP_SHAPES)} 支持）")
        limit = _wave_freq_limit(self.model, shape)
        for name, v in (("扫频起始频率", start), ("扫频终止频率", stop),
                        ("扫频中心频率", center), ("扫频频率跨度", span)):
            if v is not None:
                if v <= 0 or (limit and v > limit):
                    raise ParamValidationError(
                        f"{name} {v:g}Hz 超出 {shape} 波形频率范围"
                        f"（0~{limit/1e6:g}MHz）")
        if time is not None and not (1e-3 <= time <= 500):
            raise ParamValidationError(f"扫频时间必须在 1ms~500s，收到 {time}")
        if spacing is not None and spacing.lower() not in SWEEP_SPACING:
            raise ParamValidationError(f"spacing 必须是 lin/log/step，收到 {spacing}")
        if step is not None and not (2 <= step <= 1024):
            raise ParamValidationError(f"步进数必须在 2~1024，收到 {step}")
        if trig_source is not None and trig_source.lower() not in SWEEP_TRIG:
            raise ParamValidationError(f"trig_source 必须是 int/ext/man，收到 {trig_source}")
        if trig_slope is not None and trig_slope.lower() not in SWEEP_TRIG_SLOPE:
            raise ParamValidationError(f"trig_slope 必须是 pos/neg，收到 {trig_slope}")
        # 边界频率仅在扫频开启时可写（实测：关闭时 FREQ:STAR/STOP 报 -220）：
        # 写参数前若扫频关闭则先开启，写完按 state 恢复
        was_on = None
        if write_params:
            was_on = self.query(f":SOUR{ch}:SWE:STAT?").strip() in ("ON", "1")
            if not was_on:
                self.write(f":SOUR{ch}:SWE:STAT ON")
            if start is not None:
                self.write(f":SOUR{ch}:FREQ:STAR {start}")
            if stop is not None:
                self.write(f":SOUR{ch}:FREQ:STOP {stop}")
            if center is not None:
                self.write(f":SOUR{ch}:FREQ:CENT {center}")
            if span is not None:
                self.write(f":SOUR{ch}:FREQ:SPAN {span}")
            if time is not None:
                self.write(f":SOUR{ch}:SWE:TIME {time}")
            if spacing is not None:
                self.write(f":SOUR{ch}:SWE:SPAC {SWEEP_SPACING[spacing.lower()]}")
            if step is not None:
                self.write(f":SOUR{ch}:SWE:STEP {step}")
            if htime_start is not None:
                self.write(f":SOUR{ch}:SWE:HTIM:STAR {htime_start}")
            if htime_stop is not None:
                self.write(f":SOUR{ch}:SWE:HTIM:STOP {htime_stop}")
            if rtime is not None:
                self.write(f":SOUR{ch}:SWE:RTIM {rtime}")
            if trig_source is not None:
                self.write(f":SOUR{ch}:SWE:TRIG:SOUR {SWEEP_TRIG[trig_source.lower()]}")
            if trig_slope is not None:
                self.write(f":SOUR{ch}:SWE:TRIG:SLOP {SWEEP_TRIG_SLOPE[trig_slope.lower()]}")
        if state is not None:
            self.write(f":SOUR{ch}:SWE:STAT {'ON' if state else 'OFF'}")
        elif was_on is False:
            # 未指定开关且原为关闭：参数写完后恢复关闭
            self.write(f":SOUR{ch}:SWE:STAT OFF")
        return self.get_sweep_config(ch)

    def sweep_trigger(self, ch):
        """手动触发一次扫频。前置：触发源必须为 manual（TRIG:SOUR MAN）且该通道输出已打开；
        否则设备回 -220（手册：SWE:TRIG:IMM 仅适用于手动触发）。非 MAN 时这里给出明确提示。"""
        try:
            src = self.query(f":SOUR{ch}:SWE:TRIG:SOUR?").strip().upper()
        except Exception:
            src = None
        if src not in ("MAN", "MANUAL"):
            raise ParamValidationError(
                f"手动触发扫频要求触发源为 manual（当前 {src}）：请先设置 "
                f"set_sweep(ch, trig_source='man') 再调用（设备在非 MAN 下发 "
                f"SWE:TRIG:IMM 会回 -220）"
            )
        self.write(f":SOUR{ch}:SWE:TRIG:IMM")

    # ---------- 频率计 ----------
    def counter_on(self, run=True):
        self.write(f":COUN {'RUN' if run else 'OFF'}")

    def counter_measure(self, timeout=2.0) -> str:
        """打开频率计并读一次测量结果（频率,周期,占空比? 视返回而定）"""
        self.write(":COUN RUN")
        old = self.instr.timeout
        try:
            self.instr.timeout = max(500, int(timeout * 1000))
            return self.query(":COUN:MEAS?", strip=True)
        except pyvisa.VisaIOError:
            return "测量超时（请确认 [Counter] 输入口有信号）"
        finally:
            self.instr.timeout = old

    # ---------- 系统 ----------
    def reset(self):
        """*RST 复位。⚠️ 复位后恢复出厂默认：SIN 1kHz / 5Vpp / 0 偏移 / 输出 OFF /
        电压保护关闭（±5V）——**必须先重新设置电压保护并配置好参数，才能打开输出**；
        未开保护时 output on / amp / offset 会被库拒绝（protect_required）。"""
        self.write("*RST")

    def status(self) -> dict:
        spec = MODEL_REGISTRY.get(self.model, {})
        n = int(spec.get("channels", 2))
        out = {"model": self.model, "idn": self.idn()}
        for i in range(1, n + 1):
            out[f"ch{i}"] = self.get_wave_config(i)
        return out


# ================= CLI =================

def main(argv=None):
    p = argparse.ArgumentParser(prog="dg832", description="RIGOL DG800 系列信号源控制（默认 DG832，支持 DG800 全系）")
    p.add_argument("--res", default=None, help="VISA 资源名（默认按型号自动查找）")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"仪器型号（当前支持 {', '.join(sorted(MODEL_REGISTRY))}），默认 {DEFAULT_MODEL}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("idn", help="查询设备信息")
    sub.add_parser("status", help="读取两通道配置与状态")
    sub.add_parser("counter", help="频率计测一次")
    sub.add_parser("reset", help="*RST 复位设备")

    def add_ch(parser):
        parser.add_argument("--ch", type=int, default=1, choices=[1, 2])

    dc_p = sub.add_parser("dc", help="DC 专用切换（设电平，返回切换前配置快照供显式恢复）")
    dc_p.add_argument("level", type=float, help="直流电平 V")
    add_ch(dc_p)

    swp = sub.add_parser("sweep", help="配置/开启/查询扫频（无参数=仅查询；仅 sine/square/ramp/user 支持）")
    swp.add_argument("--start", type=float, default=None, help="起始频率 Hz")
    swp.add_argument("--stop", type=float, default=None, help="终止频率 Hz")
    swp.add_argument("--center", type=float, default=None, help="中心频率 Hz（与 start/stop 二选一）")
    swp.add_argument("--span", type=float, default=None, help="频率跨度 Hz（与 start/stop 二选一）")
    swp.add_argument("--time", type=float, default=None, help="扫频时间 s (1ms~500s)")
    swp.add_argument("--spacing", choices=["lin", "log", "step"], default=None, help="扫频间隔")
    swp.add_argument("--step", type=int, default=None, help="步进数 2~1024（仅 step 间隔）")
    swp.add_argument("--trig-source", choices=["int", "ext", "man"], default=None, help="触发源")
    swp.add_argument("--trig-slope", choices=["pos", "neg"], default=None, help="外部触发边沿")
    swp.add_argument("--on", dest="sweep_on", action="store_true", help="开启扫频")
    swp.add_argument("--off", dest="sweep_off", action="store_true", help="关闭扫频")
    add_ch(swp)

    sw = sub.add_parser("sine", help="设置正弦波")
    sw.add_argument("freq", type=float)
    sw.add_argument("amp", type=float)
    sw.add_argument("offset", nargs="?", type=float, default=None)
    sw.add_argument("phase", nargs="?", type=float, default=None)
    add_ch(sw)
    sw.add_argument("--out", choices=["on", "off"], default=None, help="同时切换输出")

    sq = sub.add_parser("square", help="设置方波")
    sq.add_argument("freq", type=float)
    sq.add_argument("amp", type=float)
    add_ch(sq)
    sq.add_argument("--out", choices=["on", "off"], default=None)

    for name in ("freq", "amp", "offset", "phase"):
        sp = sub.add_parser(name, help=f"设置{name}")
        sp.add_argument("value", type=float)
        add_ch(sp)

    outp = sub.add_parser("out", help="开关输出 on/off")
    outp.add_argument("state", choices=["on", "off"])
    add_ch(outp)
    sub.add_parser("off", help="关闭全部输出")

    prot = sub.add_parser("protect", help="设置/查询电压保护（强制流程：设置幅度/输出前必须先开保护）")
    prot.add_argument("--high", type=float, default=None, help="电压上限 V")
    prot.add_argument("--low", type=float, default=None, help="电压下限 V")
    prot.add_argument("--on", dest="on", action="store_true", help="开启保护")
    prot.add_argument("--off", dest="off", action="store_true", help="关闭保护")
    add_ch(prot)

    args = p.parse_args(argv)

    try:
        gen = DG832(resource=args.res, model=args.model)
        gen.connect()
    except RuntimeError as e:
        print(f"连接失败: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"型号错误: {e}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "idn":
            print(gen.idn())
        elif args.cmd == "status":
            st = gen.status()
            print(f"设备({st['model']}): {st['idn']}")
            for k in ("ch1", "ch2"):
                c = st[k]
                print(f"{k}: 波形={c['shape']} 频率={c['freq']}Hz 幅度={c['amp']}Vpp "
                      f"偏移={c['offset']}V 相位={c['phase']}° 输出={c['output']} 负载={c['load']}")
        elif args.cmd == "counter":
            print("频率计:", gen.counter_measure())
        elif args.cmd == "reset":
            gen.reset()
            print("已复位（默认 SIN 1kHz/5Vpp/0V，输出 OFF，保护已关闭）")
            print("⚠️ 请先 instrument_protect 设置保护并配置参数，再打开输出", file=sys.stderr)
        elif args.cmd == "dc":
            r = gen.set_dc_only(args.ch, args.level)
            print(f"CH{args.ch} DC 电平: {r['value']}")
            if r["restore"]:
                b = r["restore"]
                print(f"切换前配置(restore): {b.get('shape')} freq={b.get('freq')} amp={b.get('amp')} "
                      f"offset={b.get('offset')} phase={b.get('phase')}（切回时请显式传参）")
            if r["note"]:
                print(f"提示: {r['note']}", file=sys.stderr)
        elif args.cmd == "sweep":
            if args.sweep_on and args.sweep_off:
                print("错误[validation]: --on 与 --off 不能同时指定", file=sys.stderr)
                return 3
            state = True if args.sweep_on else (False if args.sweep_off else None)
            print(gen.set_sweep(args.ch, start=args.start, stop=args.stop, time=args.time,
                                spacing=args.spacing, step=args.step,
                                trig_source=args.trig_source, trig_slope=args.trig_slope,
                                center=args.center, span=args.span, state=state))
        elif args.cmd == "sine":
            r = gen.set_wave(args.ch, "sine", args.freq, args.amp, args.offset, args.phase)
            print(f"CH{args.ch} -> {r}")
            if args.out:
                print(f"输出: {gen.output(args.ch, args.out == 'on')}")
        elif args.cmd == "square":
            r = gen.set_wave(args.ch, "square", args.freq, args.amp)
            print(f"CH{args.ch} -> {r}")
            if args.out:
                print(f"输出: {gen.output(args.ch, args.out == 'on')}")
        elif args.cmd == "freq":
            r = gen.set_freq(args.ch, args.value)
            print(r["value"])
            if r["note"]:
                print(f"提示: {r['note']}", file=sys.stderr)
        elif args.cmd == "amp":
            r = gen.set_amp(args.ch, args.value)
            print(r["value"])
            if r["note"]:
                print(f"提示: {r['note']}", file=sys.stderr)
        elif args.cmd == "offset":
            r = gen.set_offset(args.ch, args.value)
            print(r["value"])
            if r["note"]:
                print(f"提示: {r['note']}", file=sys.stderr)
        elif args.cmd == "phase":
            print(gen.set_phase(args.ch, args.value))
        elif args.cmd == "out":
            print(gen.output(args.ch, args.state == "on"))
        elif args.cmd == "protect":
            if args.on and args.off:
                print("错误[validation]: --on 与 --off 不能同时指定", file=sys.stderr)
                return 3
            state = True if args.on else (False if args.off else None)
            print(gen.set_voltage_limit(args.ch, high=args.high, low=args.low, state=state))
        elif args.cmd == "off":
            gen.output(1, False)
            gen.output(2, False)
            print("CH1/CH2 输出已关闭")

        # 只读命令（idn/status/counter）不查错误队列，避免历史遗留错误误报
        if args.cmd in ("sine", "square", "dc", "sweep", "freq", "amp", "offset", "phase", "out", "off", "protect", "reset"):
            errs = gen.check_error()
            if errs:
                print("设备错误队列:", errs, file=sys.stderr)
                return 2
        return 0
    except ProtectRequiredError as e:
        print(f"错误[protect_required]: {e}", file=sys.stderr)
        return 3
    except ProtectRangeError as e:
        print(f"错误[protect_range]: {e}", file=sys.stderr)
        return 3
    except ParamValidationError as e:
        print(f"错误[param_validation]: {e}", file=sys.stderr)
        return 3
    except ConnectionError_ as e:
        print(f"错误[connection]: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"错误[validation]: {e}", file=sys.stderr)
        return 3
    finally:
        gen.close()


if __name__ == "__main__":
    sys.exit(main())
