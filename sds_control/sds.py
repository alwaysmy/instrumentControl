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


def drain_errors(scope: "SDS") -> int:
    """清空设备错误队列（滞后报错会污染逐命令查错，写序列前必须先清）。"""
    n = 0
    while n < 30:
        e = scope.query(C.SYST_ERR).strip()
        if e.startswith("+0") or "No error" in e:
            break
        n += 1
    return n


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
        """探头衰减比（响应如 'C1:ATTN 10' → 10.0；'D1M' 为 1M:1 数字探针 → 1e6）。"""
        raw = self.query(f"C{self._ch(ch)}:ATTN?")
        try:
            return float(raw)
        except ValueError:
            pass
        m = re.match(r"^D(\d+)M$", raw.strip())
        if m:
            return float(m.group(1)) * 1e6
        raise ValueError(f"无法解析衰减比: {raw!r}")

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
        """:MEAS? 返回测量显示开关状态（非统计值，实测确认）。"""
        raw = self.query(C.MEAS_ALL)
        out: dict = {}
        for token in raw.split(","):
            k, _, v = token.partition(":")
            k = k.strip()
            if k:
                out[k] = v.strip()
        return out

    def measure_simple(self, item: str, src: str = "C4", timeout_s: float = 6.0) -> float:
        """SIMPLE 模式单次测量：自动切模式→设信源→开测量项→读值。

        实测要点（SDS800X HD）：
        - 必须先 :MEASure:MODE SIMPle（默认 ADVANCED 下 SIMPle 组整体失效，
          VALue? 返回 'The number of measurements is zero'）；
        - SOURce 与 ITEM 是两条命令，ITEM 必须带 ,ON 状态参数；
        - item 用 SDS 缩写枚举（PKPK/FREQ/PER/MAX/RMS...，与 ADVanced 同表）；
        - 每步后查 SYST:ERR? 确认。
        """
        if item not in self.MEAS_TYPES:
            raise ValueError(f"未知测量项 {item!r}，可用: {', '.join(self.MEAS_TYPES)}")
        drain_errors(self)
        self.write(":MEASure:MODE SIMPle")
        time.sleep(0.2)
        err = self.query(C.SYST_ERR).strip()
        if not err.startswith("+0") and "No error" not in err:
            raise RuntimeError(f":MEASure:MODE SIMPle 被拒: {err}")
        self.write(f":MEASure:SIMPle:SOURce {src.upper()}")
        time.sleep(0.1)
        err = self.query(C.SYST_ERR).strip()
        if not err.startswith("+0") and "No error" not in err:
            raise RuntimeError(f":MEASure:SIMPle:SOURce 被拒: {err}")
        self.write(f":MEASure:SIMPle:ITEM {item},ON")
        err = self.query(C.SYST_ERR).strip()
        if not err.startswith("+0") and "No error" not in err:
            raise RuntimeError(f":MEASure:SIMPle:ITEM 被拒: {err}")
        # 测量项切换后引擎需要重建（实测：连续切换时读到过渡期旧值，
        # 如 MAX 读出上一项的残值导致 auto_scale 连环误判）
        time.sleep(0.8)
        deadline = time.monotonic() + timeout_s
        last_raw = ""
        poll_start = time.monotonic()
        while time.monotonic() < deadline:
            last_raw = self.query(f":MEASure:SIMPle:VALue? {item}").strip()
            try:
                return float(_num(last_raw))
            except ValueError:
                time.sleep(0.5)
            if time.monotonic() - poll_start > 3.0:
                # 长时间无有效值时重发 ITEM 刷新测量引擎
                self.write(f":MEASure:SIMPle:ITEM {item},ON")
                time.sleep(0.5)
                poll_start = time.monotonic()
        raise RuntimeError(
            f"{item}@{src} 在 {timeout_s}s 内无有效值（最后响应: {last_raw!r}）；"
            f"请检查信号接入/触发配置"
        )

    # SIMPLE 模式允许表 = 手册 §p.181 SIMPle:ITEM 参数表逐字（2026-09-09 核对）。
    # 注意：PSLOPE/NSLOPE 不在 SIMPLE 表内（实测 SIMPle:ITEM PSLOPE,ON 不报错
    # 但 VALue? 恒 'The number of measurements is zero'，属 ADV 专用）。
    MEAS_TYPES = (
        "PKPK", "MAX", "MIN", "AMPL", "TOP", "BASE", "LEVELX", "CMEAN",
        "MEAN", "STDEV", "VSTD", "RMS", "CRMS", "MEDIAN", "CMEDIAN",
        "OVSN", "FPRE", "OVSP", "RPRE", "ULOWer", "PER", "FREQ",
        "TMAX", "TMIN", "PWID", "NWID", "DUTY", "NDUTY", "WID", "NBWID",
        "DELAY", "TIMEL", "RISE", "FALL", "RISE20T90", "FALL80T20",
        "CCJ", "PAREA", "NAREA", "AREA", "ABSAREA", "CYCLES",
        "REDGES", "FEDGES", "EDGES", "PPULSES", "NPULSES",
        "PACArea", "NACArea", "ACArea", "ABSACArea",
    )

    def meas_mode(self, mode: Optional[str] = None) -> Optional[str]:
        """:MEASure:MODE 测量模式 SIMPle/ADVanced（回读短格式 SIMP/ADV）。

        ADVanced 槽位制测量要求 MODE=ADVanced；SIMPLE 组在 ADVANCED 下整体失效。
        """
        if mode is None:
            return self.query(C.MEAS_MODE + "?").strip() or None
        self.write(f"{C.MEAS_MODE} {mode}")
        return None

    def adv_slot(self, slot: int, on: Optional[bool] = None) -> Optional[bool]:
        """:MEASure:ADVanced:P<n> 槽位独立开关（n∈[1,12]）。VALue? 出值的前提是槽已开。"""
        n = int(slot)
        if not 1 <= n <= 12:
            raise ValueError(f"invalid slot: {slot!r}（P 槽范围 1~12）")
        if on is None:
            return self.query(f"{C.MEAS_ADV_SLOT.format(n=n)}?").strip() in ("1", "ON")
        self.write(f"{C.MEAS_ADV_SLOT.format(n=n)} {'ON' if on else 'OFF'}")
        return None

    def adv_measure_setup(
        self,
        slot: int,
        mtype: str,
        src: str = "C1",
        src2: Optional[str] = None,
        enable: bool = True,
    ) -> None:
        """配置高级测量槽 P<n>（TYPE + 信源A/信源B + 开槽），逐条查错。

        双通道测量（PHA/SKEW/FRR…）必须同时给 src（=A）与 src2（=B）；
        槽开关默认打开（此前缺这步是 VALue? 恒 '****' 的根因之一）。
        """
        n = int(slot)
        if not 1 <= n <= 12:
            raise ValueError(f"invalid slot: {slot!r}（P 槽范围 1~12）")
        allowed = self.MEAS_TYPES + C.MEAS_ADV_SINGLES + C.MEAS_DUAL_TYPES
        if mtype not in allowed:
            raise ValueError(
                f"未知测量类型 {mtype!r}。单通道: {', '.join(self.MEAS_TYPES)}；"
                f"ADV 专用: {', '.join(C.MEAS_ADV_SINGLES)}；"
                f"双通道: {', '.join(C.MEAS_DUAL_TYPES)}"
            )
        drain_errors(self)
        self.write(f"{C.MEAS_ADV_SOUR1.format(n=n)} {src.upper()}")
        err = self.query(C.SYST_ERR).strip()
        if not err.startswith("+0") and "No error" not in err:
            raise RuntimeError(f"P{n} SOURce1 被拒: {err}")
        if src2 is not None:
            self.write(f"{C.MEAS_ADV_SOUR2.format(n=n)} {src2.upper()}")
            err = self.query(C.SYST_ERR).strip()
            if not err.startswith("+0") and "No error" not in err:
                raise RuntimeError(f"P{n} SOURce2 被拒: {err}")
        self.write(C.MEAS_ADV_TYPE_W.format(n=n, t=mtype))
        err = self.query(C.SYST_ERR).strip()
        if not err.startswith("+0") and "No error" not in err:
            raise RuntimeError(f"P{n} TYPE 被拒: {err}")
        if enable:
            self.write(f"{C.MEAS_ADV_SLOT.format(n=n)} ON")
            err = self.query(C.SYST_ERR).strip()
            if not err.startswith("+0") and "No error" not in err:
                raise RuntimeError(f"P{n} 开槽被拒: {err}")

    def measure_phase(
        self, src_a: str = "C2", src_b: str = "C1",
        slot: Optional[int] = None, timeout_s: float = 12.0,
    ) -> dict:
        """双通道相位差（度）：A/B 第一个上升沿中值点间相位 = B 相对 A 的相位。

        完整序列（手册 CN11G §3.17/表 5-1，2026-09-08 实测）：
        MODE ADVanced → Pn SOURce1=A → Pn SOURce2=B → Pn TYPE PHA →
        Pn ON → Pn VALue?。要求两通道完整周期在屏内。
        slot=None 时自动选用首个 OFF 空槽；返回 {"degrees","slot","raw"}。
        用后请 adv_slot(slot, False) 关闭并恢复 MODE（调用方负责恢复）。
        """
        if slot is None:
            slot = next(
                (i for i in range(1, 13) if not self.adv_slot(i)),
                None,
            )
            if slot is None:
                raise RuntimeError("P1..P12 全开，无空闲槽（拒绝覆盖已有配置）")
        n = int(slot)
        self.write(f"{C.MEAS_MODE} ADVanced")
        time.sleep(0.2)
        self.adv_measure_setup(n, "PHA", src_a, src2=src_b, enable=True)
        last_raw = ""
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout_s:
            time.sleep(1.0)
            last_raw = self.query(C.MEAS_ADV_VAL.format(n=n)).strip()
            try:
                v = float(last_raw)
                if abs(v) < 9.0e36:
                    return {"degrees": v, "slot": n, "raw": last_raw}
            except ValueError:
                pass
        raise RuntimeError(
            f"PHA@{src_a}/{src_b}(P{n}) 在 {timeout_s}s 内无有效值"
            f"（最后响应: {last_raw!r}）；请确认两通道完整周期在屏内且已触发"
        )

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
        """截屏并存为 PNG（供人工/AI 查看）。

        注意：SDS 的 BMP alpha 字节恒为 0，若直接存 RGBA 会得到全透明图
        （查看器/模型渲染为纯白）——必须转 RGB 丢弃 alpha（2026-09-09 实测）。
        """
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
        img = img.convert("RGB")  # 丢弃全 0 的 alpha，否则 PNG 全透明
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
        use_autoset: bool = False,
    ) -> dict:
        """让通道 ch 正确显示波形。

        默认（use_autoset=False）走 SCPI 闭环，只动目标通道——多信号场景下
        其他已调好的通道不受影响。

        use_autoset=True 仅在满足以下全部条件时显式启用：
            - 信号类型简单且周期性（正弦/方波等，NOISE/复杂调制不适用）；
            - 没有其他已调好的通道（:AUToset 是全局破坏性命令，会重置
              所有通道档位/时基/触发配置）。
        AUToset 路径：一步定标 → SCPI 读 PKPK/FREQ 验证 → 微调，零截图。
        SCPI 闭环路径：触发修复 → TDIV 重试 → 垂直定标（削顶回退/偏置居中）。
        两者失败均可再用截图像素诊断兜底。
        """
        n = self._ch(ch)
        src = f"C{n}"
        actions: list[str] = []

        # 1. 触发链路修复（'屏幕无波形'的头号根因：触发源挂空/电平过高）
        trig = self.diagnose_trigger()
        if f"C{n}" != str(trig.get("edge_source", "")):
            self.write(f"TRIG:EDGE:SOUR {src}")
            actions.append(f"触发源 {trig['edge_source']}→{src}")
        # AUTO 模式（手册 3.27.1）：超时未触发也强制采集，测量引擎不会冻结
        # （NOISE 等无规则波形在 NORMal 下永不触发，会污染后续所有测量）
        if str(trig.get("mode", "")).upper() != "AUTO":
            self.write(":TRIGger:MODE AUTO")
            actions.append("触发模式→AUTO(免触发冻结)")
        drain_errors(self)

        # 2. 打开通道
        if self.query(f"C{n}:TRA?").strip() != "ON":
            self.write(f"C{n}:TRA ON")
            actions.append(f"{src} 显示开启")

        std_steps = [
            0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10,
        ]
        result = {
            "channel": src,
            "actions": actions,
            "vpp": None,
            "freq": None,
            "adjusted": {},
        }

        # 2.5 AUToset 快速路径（简单规则信号一步定标，零截图；失败落入 SCPI 闭环）
        if use_autoset:
            try:
                self.write(C.AUTOSET)
                time.sleep(2.5)
                drain_errors(self)
                vpp = self.measure_simple("PKPK", src)
                freq = self.measure_simple("FREQ", src)
                result["vpp"], result["freq"] = vpp, freq
                if vpp and freq and vpp > 1e-6:
                    # AUToset 已保证入屏，读数可信——微调到目标格数/周期数
                    ideal = vpp / sum(target_divs) * 2
                    best = min(std_steps, key=lambda s: abs(s - ideal))
                    cur = _num(self.query(f"C{n}:VDIV?"))
                    if abs(best - cur) / cur > 0.2:
                        self.write(f"C{n}:VDIV {best}V")
                        time.sleep(1.2)
                        vmax = self.measure_simple("MAX", src)
                        vmin = self.measure_simple("MIN", src)
                        lim = 4.5 * best
                        if vmax > lim or vmin < -lim or vmax - vmin < 1e-3:
                            self.write(f"C{n}:VDIV {cur}V")
                            actions.append(f"细调 {best} 异常，回退 {cur}")
                        else:
                            result["adjusted"]["vdiv"] = best
                            actions.append(f"细调: VDIV {cur}→{best}")
                    ideal_tdiv = (target_cycles / freq) / 10
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
                    time.sleep(0.8)
                    result["vpp"] = self.measure_simple("PKPK", src)
                    result["freq"] = self.measure_simple("FREQ", src)
                    if verbose:
                        print(f"[auto_scale:AUToset] {result}")
                return result
            except RuntimeError as e:
                actions.append(f"AUToset 路径失败({e})，回退 SCPI 闭环")

        # 3. 测量 Vpp/Freq —— TDIV 为上轮遗留时不适配会导致平线(****)，逐级重试
        # 列表覆盖低频（10Hz 需 ≥20ms/div）到高频
        vpp = freq = None
        for tdiv_try in (None, 1e-3, 1e-2, 1e-4, 1e-1, 1.0, 1e-5):
            if tdiv_try is not None:
                self.write("TDIV %g" % tdiv_try)
                time.sleep(0.8)
            try:
                vpp = self.measure_simple("PKPK", src)
                freq = self.measure_simple("FREQ", src)
                if vpp and freq and vpp > 1e-6:
                    break
                actions.append(f"TDIV={tdiv_try or '保持'} 无有效波形(PKPK={vpp})，换档重试")
            except RuntimeError as e:
                actions.append(f"TDIV={tdiv_try or '保持'} 重试失败")

        # 3b. 垂直定标（先缩放入屏，再中点电平/偏置——超屏时 MAX/MIN 被钳制不可信）
        std_steps = [
            0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10,
        ]
        if vpp and freq:
            # 3b-1【缩放入屏】：只放大不缩小（宁大勿小）——最大档起步会在 Roll 模式
            # 与低分辨率读数下引入新问题，改为：钳制初测偏小时 start 偏小，
            # 削顶由 3b-3 验证回退兜底；信号丢失(出屏)由 MAX-MIN≈0 检测
            try:
                ideal_in = max(vpp / 6.0, 0.05)  # 下限 50mV：钳制初测防极小档化
                start = min((s for s in std_steps if s >= ideal_in), default=10.0)
                start = max(start, 0.05)
                cur = _num(self.query(f"C{n}:VDIV?"))
                if start > cur:
                    self.write(f"C{n}:VDIV {start}V")
                    result["adjusted"]["vdiv"] = start
                    actions.append(f"缩放入屏: VDIV {cur}→{start}")
                    time.sleep(1.2)
                    vpp = self.measure_simple("PKPK", src)
                    result["vpp"] = vpp
            except RuntimeError as e:
                actions.append(f"缩放入屏失败: {e}")

            # 3b-2【信号中点触发电平】：入屏后 MAX/MIN 可信
            try:
                vmax = self.measure_simple("MAX", src)
                vmin = self.measure_simple("MIN", src)
                mid = (vmax + vmin) / 2
                self.write("TRIG:EDGE:LEV %gV" % mid)
                actions.append(f"触发电平→{mid:.3g}V(信号中点)")
            except RuntimeError:
                pass

            # 3b-3【细调档位】：往目标格数调，调后验证 MAX/MIN 仍在屏内否则回退
            try:
                ideal = vpp / sum(target_divs) * 2
                best = min(std_steps, key=lambda s: abs(s - ideal))
                cur = _num(self.query(f"C{n}:VDIV?"))
                if best < cur and abs(best - cur) / cur > 0.2:
                    self.write(f"C{n}:VDIV {best}V")
                    time.sleep(1.2)
                    vmax = self.measure_simple("MAX", src)
                    vmin = self.measure_simple("MIN", src)
                    lim = 4.5 * best
                    if vmax > lim or vmin < -lim:
                        self.write(f"C{n}:VDIV {cur}V")
                        actions.append(f"细调 {best} 引发削顶，回退 {cur}")
                    elif vmax - vmin < 1e-3:
                        # 信号完全出屏时 MAX/MIN 读数趋 0（非屏界钳制），削顶验证失效
                        self.write(f"C{n}:VDIV {cur}V")
                        actions.append(
                            f"细调 {best} 后信号丢失(MAX-MIN={vmax - vmin:.3g})，回退 {cur}"
                        )
                        vpp = self.measure_simple("PKPK", src)
                        result["vpp"] = vpp
                    else:
                        result["adjusted"]["vdiv"] = best
                        actions.append(f"细调: VDIV {cur}→{best}")
                        vpp = self.measure_simple("PKPK", src)
                        result["vpp"] = vpp
            except RuntimeError as e:
                actions.append(f"细调失败: {e}")

            # 3b-4【偏置居中】：中点偏离 0 时用 OFST 拉回（方向探测一次）
            try:
                vmax = self.measure_simple("MAX", src)
                vmin = self.measure_simple("MIN", src)
                mid = (vmax + vmin) / 2
                cur_vdiv = _num(self.query(f"C{n}:VDIV?"))
                if abs(mid) > 0.1 * cur_vdiv:
                    cur_ofst = _num(self.query(f"C{n}:OFST?"))
                    trial = cur_ofst - mid
                    self.write(f"C{n}:OFST {trial}V")
                    time.sleep(1.2)
                    mid2 = (self.measure_simple("MAX", src) + self.measure_simple("MIN", src)) / 2
                    if abs(mid2) > abs(mid):
                        trial = cur_ofst + mid
                        self.write(f"C{n}:OFST {trial}V")
                        time.sleep(1.2)
                    result["adjusted"]["ofst"] = trial
                    actions.append(f"偏置居中: OFST→{trial:g}V")
            except RuntimeError:
                pass

        if verbose:
            print(f"[auto_scale] {src}: Vpp={vpp} Freq={freq} 动作={actions}")

        if vpp is None or freq is None:
            result["error"] = "无法测得 Vpp/频率：请检查信号接入与探头"
            return result

        # 4a. 垂直档位：VDIV ∈ 1-2-5 序列，使 Vpp 占 2.5~6 格；调后复测确认收敛
        std_steps = [
            0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10,
        ]
        ideal = vpp / sum(target_divs) * 2  # 目标格数中点
        best = min(std_steps, key=lambda s: abs(s - ideal))
        cur = _num(self.query(f"C{n}:VDIV?"))
        if abs(best - cur) / cur > 0.2:
            self.write(f"C{n}:VDIV {best}V")
            result["adjusted"]["vdiv"] = best
            actions.append(f"VDIV {cur}→{best}")
            time.sleep(1.2)
            try:
                vpp2 = self.measure_simple("PKPK", src)
                if vpp2 and vpp and abs(vpp2 - vpp) / max(vpp, 1e-9) > 0.3:
                    actions.append(f"复测 Vpp 漂移 {vpp:.3g}→{vpp2:.3g}，按新值二次定标")
                    ideal = vpp2 / sum(target_divs) * 2
                    best2 = min(std_steps, key=lambda s: abs(s - ideal))
                    cur2 = _num(self.query(f"C{n}:VDIV?"))
                    if abs(best2 - cur2) / cur2 > 0.2:
                        self.write(f"C{n}:VDIV {best2}V")
                        result["adjusted"]["vdiv"] = best2
                        actions.append(f"VDIV {cur2}→{best2}")
                    result["vpp"] = vpp2
            except RuntimeError as e:
                actions.append(f"复测失败: {e}")

        # 4b. 垂直偏置：把信号中心拉回屏幕中线（简化：偏置=0 起步）
        # 4c. 水平：TDIV 使全屏(10格)含 target_cycles 个周期
        ideal_tdiv = (freq and (target_cycles / freq) / 10) or None
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

    def shutdown(self, confirm: bool = False) -> None:
        """:SYSTem:SHUTdown 远程关机（手册 237 页；实测 ~6s 离线）。

        ⚠ 破坏性：设备将关机离线，需面板手动开机（无网络唤醒）。
        必须显式 confirm=True 才执行。
        """
        if not confirm:
            raise RuntimeError("shutdown 需要 confirm=True（设备将关机离线，需手动开机）")
        self.write(":SYSTem:SHUTdown")

    def reboot(self, confirm: bool = False) -> None:
        """:SYSTem:REBoot 远程重启（手册同节）。⚠ 破坏性，需显式 confirm=True。"""
        if not confirm:
            raise RuntimeError("reboot 需要 confirm=True（设备将重启离线）")
        self.write(":SYSTem:REBoot")

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
