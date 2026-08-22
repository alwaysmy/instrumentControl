"""Siglent SDS 系列（SDS800X HD 基准）示波器控制库。

实测基准：SDS824X HD（VXI-11 inst0）。命令来源见 commands.py 头部。
"""
from __future__ import annotations

import re
import struct
import sys
import time
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.discovery import find_device, identify, list_resources, scan  # noqa: F401
from common.visa_client import VisaClient

from . import commands as C


def _num(text: str) -> float:
    """从带单位后缀的响应中提取数值（如 '2.00E-03S' → 2e-3；'C1:ATTN 10' 由调用方先剥离）。"""
    m = re.search(r"[-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?", text)
    if m is None:
        raise ValueError(f"无数字可解析: {text!r}")
    return float(m.group().replace("D", "E").replace("d", "e"))


class SDS:
    """Siglent SDS 系列示波器控制封装。"""

    def __init__(
        self,
        resource: Optional[str] = None,
        model: str = "SDS",
        timeout_ms: int = 10000,
        hosts: Optional[list[str]] = None,
        cidr: Optional[str] = None,
        allow_scan: bool = False,
    ):
        self.model = model
        self.resource = resource
        self.timeout_ms = timeout_ms
        self.hosts = list(hosts) if hosts else []
        self.cidr = cidr
        self.allow_scan = allow_scan
        self.client: Optional[VisaClient] = None

    def connect(self, resource: Optional[str] = None) -> str:
        if resource:
            self.resource = resource
        if not self.resource:
            hit = find_device(
                self.model,
                hosts=self.hosts or None,
                allow_scan=self.allow_scan,
                cidr=self.cidr,
                timeout_ms=min(self.timeout_ms, 5000),
            )
            self.resource = hit.resource
        assert self.resource is not None
        self.client = VisaClient(self.resource, timeout_ms=self.timeout_ms)
        return self.resource

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def __enter__(self) -> "SDS":
        if self.client is None:
            self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _c(self) -> VisaClient:
        if self.client is None:
            raise RuntimeError("未连接设备，请先 connect()")
        return self.client

    def query(self, cmd: str) -> str:
        resp = self._c().query(cmd).strip()
        # SDS 多数查询响应带回显头（如发 "C1:VDIV?" 收 "C1:VDIV 5.00E+00V"）；
        # 仅当响应以命令头部开头时才剥离，避免误伤 *IDN? 等无回显响应。
        cmd_head = cmd.lstrip(":").split(" ")[0].split("?")[0]
        if " " in resp and resp.upper().startswith(cmd_head.upper()):
            return resp.split(" ", 1)[1].strip()
        return resp

    def write(self, cmd: str) -> None:
        self._c().write(cmd)

    def query_raw(self, cmd: str) -> bytes:
        return self._c().query_raw(cmd)

    # ---------- 信息 ----------
    def idn(self) -> str:
        return self.query("*IDN?")

    def system_error(self) -> Optional[str]:
        resp = self.query(C.SYST_ERR)
        return resp or None

    def run(self) -> None:
        self.write(C.RUN)

    def stop(self) -> None:
        self.write(C.STOP)

    def autoset(self) -> None:
        self.write(C.AUTOSET)

    # ---------- 通道 ----------
    def _ch(self, ch: int) -> int:
        n = int(ch)
        if n not in (1, 2, 3, 4):
            raise ValueError(f"invalid channel: {ch!r}")
        return n

    def channel_scale(self, ch: int, scale_v: Optional[float] = None) -> Optional[float]:
        n = self._ch(ch)
        if scale_v is None:
            return _num(self.query(f"C{n}:VDIV?"))
        self.write(f"C{n}:VDIV {scale_v}V")
        return None

    def channel_offset(self, ch: int, offset_v: Optional[float] = None) -> Optional[float]:
        n = self._ch(ch)
        if offset_v is None:
            return _num(self.query(f"C{n}:OFST?"))
        self.write(f"C{n}:OFST {offset_v}V")
        return None

    def channel_attenuation(self, ch: int) -> float:
        """探头衰减比（响应如 'C1:ATTN 10' → 10.0；D1M 表示 1M:1 数字探针）。"""
        raw = self.query(f"C{self._ch(ch)}:ATTN?")
        try:
            return float(raw)
        except ValueError:
            return float(raw.replace("D", "E")) if "D" in raw else float(raw.rstrip("M") or 0)

    def channel_coupling(self, ch: int, coupling: Optional[str] = None) -> Optional[str]:
        n = self._ch(ch)
        if coupling is None:
            raw = self.query(f"C{n}:COUPLING?").strip()
            # 响应头为缩写形式（发 COUPLING? 收 "C1:CPL D1M"），手动剥离
            if raw.upper().startswith("C") and " " in raw[:10]:
                return raw.split(" ", 1)[1].strip()
            return raw
        self.write(f"C{n}:COUPLING {coupling.upper()}")
        return None

    # ---------- 时基/触发 ----------
    def timebase_scale(self) -> float:
        return _num(self.query(C.TB_SCALE))

    def trigger_delay(self) -> float:
        return _num(self.query(C.TRIG_DELAY))

    def trigger_mode(self) -> str:
        return self.query(C.TRIG_MODE).strip()

    def trigger_status(self) -> str:
        return self.query(C.TRIG_STATUS).strip()

    def edge_source(self, source: Optional[str] = None) -> Optional[str]:
        if source is None:
            return self.query(C.TRIG_EDGE_SOUR).strip()
        self.write(C.TRIG_EDGE_SOUR_W.format(src=source.upper()))
        return None

    def edge_level(self, level: Optional[float] = None) -> Optional[float]:
        if level is None:
            return _num(self.query(C.TRIG_EDGE_LEV))
        self.write(C.TRIG_EDGE_LEV_W.format(val=level))
        return None

    def edge_slope(self, slope: Optional[str] = None) -> Optional[str]:
        if slope is None:
            return self.query(C.TRIG_EDGE_SLOP).strip()
        self.write(f"TRIG:EDGE:SLOP {slope}")
        return None

    # ---------- 采集 ----------
    def acquire_depth(self, value: Optional[str] = None) -> Optional[str]:
        if value is None:
            return self.query(C.ACQ_MDEP).strip()
        self.write(f"{C.ACQ_MDEP} {value}")
        return None

    def sample_rate(self) -> float:
        return _num(self.query(C.ACQ_SRAT))

    # ---------- 测量 ----------
    def measure_summary(self) -> dict:
        """:MEAS? 返回当前已打开测量项的统计值串，原样解析为键值对。"""
        raw = self.query(C.MEAS_ALL)
        out: dict = {}
        for token in raw.split(","):
            k, _, v = token.partition(":")
            k = k.strip()
            if k:
                out[k] = v.strip()
        return out

    MEAS_TYPES = (
        "PKPK", "MAX", "MIN", "AMPL", "TOP", "BASE", "CMEAN", "MEAN",
        "STDEV", "VSTD", "RMS", "CRMS", "MEDIAN", "OVSP", "OVSN",
        "PER", "FREQ", "TMAX", "TMIN", "PWID", "NWID", "DUTY", "NDUTY",
        "RISE", "FALL", "EDGES", "PPULSES", "NPULSES", "PSLOPE", "NSLOPE",
    )

    def adv_measure_setup(self, slot: int, mtype: str, src: str = "C1") -> None:
        """配置高级测量槽 P<n>（TYPE + 信源）。slot 1~8，mtype 见 MEAS_TYPES。"""
        if not (1 <= int(slot) <= 8):
            raise ValueError(f"invalid slot: {slot}")
        if mtype not in self.MEAS_TYPES:
            raise ValueError(f"未知测量类型 {mtype!r}，可用: {', '.join(self.MEAS_TYPES)}")
        self.write(f":MEASure:ADVanced:P{int(slot)}:SOURce1 {src.upper()}")
        self.write(f":MEASure:ADVanced:P{int(slot)}:TYPE {mtype}")

    def adv_measure_value(self, slot: int) -> Optional[float]:
        """读取高级测量槽 P<n> 当前值；'****'(无有效读数) 返回 None，
        9.9E37(超界) 原样返回由调用方判断。"""
        raw = self.query(C.MEAS_ADV_VAL.format(n=int(slot))).strip()
        try:
            return _num(raw)
        except ValueError:
            return None

    def clear_adv_measurements(self) -> None:
        self.write(C.MEAS_ADV_CLEAR)

    # ---------- 自动定标与诊断 ----------
    # Siglent SDS800X HD 默认通道色（RGB，容差量化匹配）
    CH_COLORS = {
        1: (240, 240, 0),    # 黄
        2: (0, 240, 240),    # 青
        3: (240, 80, 240),   # 紫/粉
        4: (32, 240, 32),    # 绿
    }
    # 屏幕网格区近似标定（1024x600 截图，可按机型微调）
    SCREEN_GRID = {"x0": 20, "x1": 935, "y0": 48, "y1": 552, "divs_y": 10}

    def screenshot(self, save_dir: Optional[Path] = None) -> bytes:
        """:PRIN? BMP 截屏原始字节（含 TMC 头则剥离）。"""
        data = self.query_raw(C.SCREEN_BMP)
        return self._strip_tmc(data) if data.find(b"#") == 0 else data

    def screenshot_png(self, save_path: Path) -> Path:
        """截屏并存为 PNG（供人工/AI 查看）。"""
        import struct

        from PIL import Image

        data = self.screenshot()
        w = struct.unpack("<i", data[18:22])[0]
        h_raw = struct.unpack("<i", data[22:26])[0]
        offset = struct.unpack("<I", data[10:14])[0]
        row_size = ((w * 4 + 3) // 4) * 4
        img = Image.frombytes(
            "RGBA",
            (w, abs(h_raw)),
            bytes(data[offset : offset + row_size * abs(h_raw)]),
            "raw",
            "BGRA",
        )
        if h_raw > 0:
            img = img.transpose(0)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(save_path)
        return save_path

    def analyze_screen(self, ch: int) -> dict:
        """截屏并统计通道轨迹的像素 Y 分布（视觉反馈核心）。

        返回 {visible, y_min, y_max, y_center, grid_top, grid_bottom,
              px_per_div, rows}，坐标为截图像素系（自上而下）。
        """
        data = self.screenshot()
        w = struct.unpack("<i", data[18:22])[0]
        h_raw = struct.unpack("<i", data[22:26])[0]
        top_down = h_raw < 0
        h = abs(h_raw)
        offset = struct.unpack("<I", data[10:14])[0]
        row_size = ((w * 4 + 3) // 4) * 4

        tr, tg, tb = self.CH_COLORS[ch]
        ys: list[int] = []
        for r in range(h):
            base = offset + r * row_size
            for c in range(w):
                i = base + c * 4
                b, g, rr = data[i], data[i + 1], data[i + 2]
                if (
                    abs(rr - tr) < 64 and abs(gg := g - tg) < 64 and abs(b - tb) < 64
                    or (tr > 200 and rr > 200 and tg > 150 and b < 100)
                ):
                    disp_r = r if top_down else h - 1 - r
                    ys.append(disp_r)
                    _ = gg
        grid = self.SCREEN_GRID
        out: dict = {
            "visible": bool(ys),
            "grid_top": grid["y0"],
            "grid_bottom": grid["y1"],
            "px_per_div": (grid["y1"] - grid["y0"]) / grid["divs_y"],
        }
        if ys:
            out.update({
                "y_min": min(ys),
                "y_max": max(ys),
                "y_center": (min(ys) + max(ys)) / 2,
                "rows": len(set(ys)),
            })
        return out

    def diagnose_trigger(self) -> dict:
        """读取触发链路状态（定位'屏幕无波形'的第一嫌疑）。"""
        return {
            "mode": self.trigger_mode(),
            "status": self.trigger_status(),
            "edge_source": self.edge_source(),
            "edge_level_v": self.edge_level(),
            "timebase_s_div": self.timebase_scale(),
        }

    def auto_scale(
        self,
        ch: int,
        target_cycles: float = 5.0,
        target_divs: tuple[float, float] = (2.5, 6.0),
        verbose: bool = False,
    ) -> dict:
        """让通道 ch 正确显示波形：修触发 → 测 Vpp/Freq → 调垂直/水平。

        适用场景：屏幕无波形或显示不佳。步骤：
        1. 触发源切到本通道、电平回 0V、扫频方式 AUTO（无触发也刷新）；
        2. 打开通道显示；
        3. 用高级测量读 Vpp 与频率；
        4. VDIV 调到使波形占 target_divs 格；TDIV 调到约 target_cycles 个周期。
        """
        n = self._ch(ch)
        src = f"C{n}"
        actions: list[str] = []

        # 1. 触发链路修复（'屏幕无波形'的头号根因：触发源挂空/电平过高）
        trig = self.diagnose_trigger()
        if f"C{n}" != str(trig.get("edge_source", "")):
            self.write(f"TRIG:EDGE:SOUR {src}")
            actions.append(f"触发源 {trig['edge_source']}→{src}")
        if trig["mode"] and "NORM" in str(trig["mode"]).upper():
            self.write(":TRIGger:SWEep AUTO")
            actions.append("扫描方式→AUTO(免触发刷新)")
        self.write(f"TRIG:EDGE:LEV 0V")
        actions.append("触发电平→0V")

        # 2. 打开通道
        if self.query(f"C{n}:TRA?").strip() != "ON":
            self.write(f"C{n}:TRA ON")
            actions.append(f"{src} 显示开启")

        # 3. 测量 Vpp/Freq
        self.adv_measure_setup(1, "VPP", src)
        self.adv_measure_setup(2, "FREQuency", src)
        vpp = freq = None
        for _ in range(6):
            time.sleep(0.8)
            vpp = self.adv_measure_value(1)
            freq = self.adv_measure_value(2)
            if vpp is not None and freq is not None:
                break
        if verbose:
            print(f"[auto_scale] {src}: Vpp={vpp} Freq={freq} 动作={actions}")

        result = {
            "channel": src,
            "actions": actions,
            "vpp": vpp,
            "freq": freq,
            "adjusted": {},
        }
        if vpp is None or freq is None:
            result["error"] = "无法测得 Vpp/频率：请检查信号接入与探头"
            return result

        # 4a. 垂直档位：VDIV ∈ 1-2-5 序列，使 Vpp 占 2.5~6 格
        std_steps = [
            0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.05 * 2, 0.05 * 5,
            0.1, 0.2, 0.5, 1, 2, 5, 10,
        ]
        ideal = vpp / sum(target_divs) * 2  # 目标格数中点
        best = min(std_steps, key=lambda s: abs(s - ideal))
        cur = _num(self.query(f"C{n}:VDIV?"))
        if abs(best - cur) / cur > 0.2:
            self.write(f"C{n}:VDIV {best}V")
            result["adjusted"]["vdiv"] = best
            actions.append(f"VDIV {cur}→{best}")

        # 4b. 垂直偏置：把信号中心拉回屏幕中线（简化：偏置=0 起步）
        # 4c. 水平：TDIV 使屏幕(10格)含 target_cycles 个周期
        ideal_tdiv = (freq and (target_cycles / freq)) or None
        if ideal_tdiv:
            tdiv_std = [
                x * m
                for x in (1e-9, 1e-6, 1e-3, 1)
                for m in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
                if 1e-9 <= x * m <= 1000
            ]
            best_t = min(tdiv_std, key=lambda s: abs(s - ideal_tdiv))
            cur_t = self.timebase_scale()
            if abs(best_t - cur_t) / max(cur_t, 1e-12) > 0.3:
                self.write(f"TDIV {best_t}")
                result["adjusted"]["tdiv"] = best_t
                actions.append(f"TDIV {cur_t}→{best_t}")
        result["actions"] = actions
        if verbose:
            print(f"[auto_scale] 最终动作: {actions}")
        return result

    # ---------- 波形读取 ----------
    @staticmethod
    def _strip_tmc(data: bytes) -> bytes:
        idx = data.find(b"#")
        ndigits = int(data[idx + 1 : idx + 2])
        length = int(data[idx + 2 : idx + 2 + ndigits])
        body = data[idx + 2 + ndigits :]
        if len(body) < length:
            raise ValueError(f"TMC 数据不完整: 期望 {length}，实得 {len(body)}")
        return body[:length]

    def _preamble(self, src: str) -> dict:
        raw = self._strip_tmc(self.query_raw(C.WAV_PREAMBLE))
        out: dict = {}
        for key, (off, fmt) in C.PREAMBLE_OFFSETS.items():
            size = {"h": 2, "i": 4, "f": 4, "d": 8}[fmt]
            chunk = raw[off : off + size]
            out[key] = struct.unpack("<" + fmt, chunk)[0]
        out["tdiv"] = C.TDIV_ENUM[out["tdiv"]]
        out["vdiv"] *= out["probe"]
        out["offset"] *= out["probe"]
        return out

    def get_waveform(self, src: Union[int, str] = 1, points: Optional[int] = None) -> dict:
        """读取模拟通道波形并换算物理量（分片读取，官方协议）。

        电压 = raw/code*vdiv - offset；时间 = -(tdiv*10/2) + i*interval + delay。
        """
        source = f"C{int(src)}" if isinstance(src, int) else str(src).upper()
        self.write(f"{C.WAV_SOUR} {source}")
        pre = self._preamble(source)
        total = pre["point_num"]
        max_pts = int(float(self.query(C.WAV_MAXPOINT)))
        width = "WORD" if pre["adc_bit"] > 8 else "BYTE"
        self.write(f"{C.WAV_WIDTH} {width}")
        if points is not None:
            total = min(points, total)
            self.write(f"{C.WAV_POINTS} {total}")

        chunks: list[bytes] = []
        start = 0
        while start < total:
            n = min(max_pts, total - start)
            self.write(f"{C.WAV_START} {start}")
            chunks.append(self._strip_tmc(self.query_raw(C.WAV_DATA)))
            start += n
        blob = b"".join(chunks)[:total * (2 if width == "WORD" else 1)]

        if width == "WORD":
            codes = struct.unpack(f"<{len(blob)//2}h", blob)
        else:
            codes = struct.unpack(f"<{len(blob)}b", blob)
        volts = [c / pre["code"] * pre["vdiv"] - pre["offset"] for c in codes]
        times = [
            -(pre["tdiv"] * 10 / 2) + i * pre["interval"] + pre["delay"]
            for i in range(len(codes))
        ]
        return {
            "t": times,
            "v": volts,
            "source": source,
            "points": len(volts),
            "interval_s": pre["interval"],
            "vdiv_v": pre["vdiv"],
            "adc_bit": pre["adc_bit"],
        }

    def screenshot_bmp(self) -> bytes:
        """:PRIN? BMP 截屏原始字节（含 TMC 头则剥离）。"""
        data = self.query_raw(C.SCREEN_BMP)
        return self._strip_tmc(data) if data.find(b"#") == 0 else data

    # ---------- 快照 ----------
    def snapshot(self) -> dict:
        chans = {}
        for ch in (1, 2, 3, 4):
            try:
                chans[f"ch{ch}"] = {
                    "coupling": self.channel_coupling(ch),
                    "attenuation_x": self.channel_attenuation(ch),
                    "scale_v_div": self.channel_scale(ch),
                    "offset_v": self.channel_offset(ch),
                }
            except Exception as e:
                chans[f"ch{ch}"] = {"error": str(e)}
        return {
            "idn": self.idn(),
            "acquire_depth": self.acquire_depth(),
            "sample_rate_hz": self.sample_rate(),
            "timebase_scale_s_div": self.timebase_scale(),
            "trigger_delay_s": self.trigger_delay(),
            "trigger_mode": self.trigger_mode(),
            "channels": chans,
        }


def find_sds(
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    cidr: Optional[str] = None,
    allow_scan: bool = False,
    timeout_ms: int = 3000,
) -> str:
    """发现 *IDN? 含 'SDS' 的 Siglent 示波器，返回资源地址。"""
    hit = find_device(
        "SDS",
        resource=resource,
        hosts=hosts,
        allow_scan=allow_scan,
        cidr=cidr,
        timeout_ms=timeout_ms,
    )
    return hit.resource
