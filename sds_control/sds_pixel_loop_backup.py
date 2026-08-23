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
        self.write(f":MEASure:SIMPle:ITEM {item},ON")
        time.sleep(0.1)
        deadline = time.monotonic() + timeout_s
        last_raw = ""
        while time.monotonic() < deadline:
            time.sleep(0.5)
            last_raw = self.query(f":MEASure:SIMPle:VALue? {item}").strip()
            try:
                return float(_num(last_raw))
            except ValueError:
                continue  # 'The number of measurements is zero' 等待测量引擎就绪
        raise RuntimeError(
            f"{item}@{src} 在 {timeout_s}s 内无有效值（最后响应: {last_raw!r}）；"
            f"请检查信号接入/触发配置"
        )

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
        """截屏并统计通道轨迹在网格区内的像素 Y 分布（削顶/居中判断的物理依据）。

        只统计网格区内的轨迹像素（通道标签等 UI 元素在网格区外，天然排除）。
        返回 {visible, y_min, y_max, y_center, clipped, grid_top, grid_bottom,
        px_per_div, rows}。
        """
        data = self.screenshot()
        w = struct.unpack("<i", data[18:22])[0]
        h_raw = struct.unpack("<i", data[22:26])[0]
        top_down = h_raw < 0
        h = abs(h_raw)
        offset = struct.unpack("<I", data[10:14])[0]
        row_size = ((w * 4 + 3) // 4) * 4

        grid = self.SCREEN_GRID
        tr, tg, tb = self.CH_COLORS[ch]
        row_counts: dict[int, int] = {}
        for r in range(h):
            disp_r = r if top_down else h - 1 - r
            if not (grid["y0"] <= disp_r <= grid["y1"]):
                continue
            base = offset + r * row_size
            cnt = 0
            for c in range(grid["x0"], min(grid["x1"], w)):
                i = base + c * 4
                b, g, rr = data[i], data[i + 1], data[i + 2]
                if abs(rr - tr) < 70 and abs(g - tg) < 70 and abs(b - tb) < 70:
                    cnt += 1
            # 高密度行=网格边框/满宽线（非波形轨迹），排除防误判削顶
            if 0 < cnt < 300:
                row_counts[disp_r] = cnt
        ys = list(row_counts)
        out: dict = {
            "visible": bool(ys),
            "grid_top": grid["y0"],
            "grid_bottom": grid["y1"],
            "px_per_div": (grid["y1"] - grid["y0"]) / grid["divs_y"],
        }
        if ys:
            y_min, y_max = min(ys), max(ys)
            out.update({
                "y_min": y_min,
                "y_max": y_max,
                "y_center": (y_min + y_max) / 2,
                "rows": len(set(ys)),
                "clipped": y_min <= grid["y0"] + 3 or y_max >= grid["y1"] - 3,
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
        self.write("TRIG:EDGE:LEV 0V")
        actions.append("触发电平→0V")
        drain_errors(self)

        # 2. 打开通道
        if self.query(f"C{n}:TRA?").strip() != "ON":
            self.write(f"C{n}:TRA ON")
            actions.append(f"{src} 显示开启")

        # 3. 测量 Vpp/Freq —— TDIV 为上轮遗留时不适配会导致平线(****)，逐级重试
        vpp = freq = None
        for tdiv_try in (None, 1e-3, 1e-4, 1e-2, 1e-5):
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

        # 3b. 触发电平改设信号中点（MAX/MIN），提升非双极性/带偏置信号的触发稳定性
        if vpp and vpp > 1e-6:
            try:
                vmax = self.measure_simple("MAX", src)
                vmin = self.measure_simple("MIN", src)
                mid = (vmax + vmin) / 2
                self.write("TRIG:EDGE:LEV %gV" % mid)
                actions.append(f"触发电平→{mid:.3g}V(信号中点)")
            except RuntimeError:
                pass

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

        # 4. 垂直定标（像素闭环）：测量值超屏会被钳制不可信，
        #    削顶/居中判断一律以截屏轨迹像素为准。
        std_steps = [
            0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10,
        ]

        def px_adjust_vdiv(direction: int, cur: float) -> Optional[float]:
            """direction=+1 放大一档 / -1 缩小一档，返回新档位。"""
            if direction > 0:
                nxt = next((s for s in std_steps if s > cur * 1.2), None)
            else:
                nxt = next((s for s in reversed(std_steps) if s < cur * 0.8), None)
            if nxt:
                self.write(f"C{n}:VDIV {nxt}V")
                time.sleep(1.2)
            return nxt

        # 4a. 最大档起步（超屏读数钳制，初测值只当量级参考）
        try:
            self.write(f"C{n}:VDIV {std_steps[-1]}V")
            actions.append(f"VDIV→{std_steps[-1]}V(最大档起步)")
            time.sleep(1.2)
            vpp = self.measure_simple("PKPK", src)
            freq = self.measure_simple("FREQ", src) or freq
            result["vpp"] = vpp
            if vpp:
                start = min((s for s in std_steps if s >= vpp / 6.0), default=10.0)
                self.write(f"C{n}:VDIV {start}V")
                result["adjusted"]["vdiv"] = start
                actions.append(f"按 Vpp≈{vpp:.3g} 跳档 → {start}V/div")
                time.sleep(1.2)

            # 4b. 像素闭环：削顶→放大；偏离中线→调 OFST。最多 5 轮
            for _ in range(5):
                scr = self.analyze_screen(n)
                if not scr.get("visible"):
                    actions.append("像素分析: 轨迹不可见，停止垂直定标")
                    break
                px_div = scr["px_per_div"]
                mid_px = (scr["grid_top"] + scr["grid_bottom"]) / 2
                if scr.get("clipped"):
                    cur = _num(self.query(f"C{n}:VDIV?"))
                    nxt = px_adjust_vdiv(+1, cur)
                    if not nxt:
                        actions.append("已最大档仍削顶")
                        break
                    result["adjusted"]["vdiv"] = nxt
                    actions.append(f"像素检出削顶 → VDIV {cur}→{nxt}")
                    continue
                delta_px = scr["y_center"] - mid_px
                if abs(delta_px) > px_div * 0.4:
                    cur_vdiv = _num(self.query(f"C{n}:VDIV?"))
                    cur_ofst = _num(self.query(f"C{n}:OFST?"))
                    # 波形偏高(y_center 小) → OFST 增大把它拉下；方向一次探测
                    trial = cur_ofst + delta_px / px_div * cur_vdiv
                    self.write(f"C{n}:OFST {trial}V")
                    time.sleep(1.2)
                    scr2 = self.analyze_screen(n)
                    if scr2.get("visible") and abs(
                        (scr2.get("y_center", mid_px)) - mid_px
                    ) > abs(delta_px):
                        trial = cur_ofst - delta_px / px_div * cur_vdiv
                        self.write(f"C{n}:OFST {trial}V")
                        time.sleep(1.2)
                    result["adjusted"]["ofst"] = trial
                    actions.append(f"偏置居中: OFST→{trial:g}V")
                    continue
                break

            # 4c. 水平定标：按 FREQ 调 TDIV 使全屏含 target_cycles 个周期
            if freq:
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
                    actions.append(f"TDIV {cur_t}→{best_t}({freq:.3g}Hz×{target_cycles}周期)")
                    time.sleep(1.2)

            # 4d. 终测
            vpp = self.measure_simple("PKPK", src)
            freq = self.measure_simple("FREQ", src) or freq
            result["vpp"] = vpp
        except RuntimeError as e:
            actions.append(f"垂直定标失败: {e}")

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
