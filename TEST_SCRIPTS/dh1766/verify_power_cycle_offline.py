# -*- coding: utf-8 -*-
"""DH1766 `power_cycle` 返回体离线验证（FakeClient，不碰真实 VISA/仪器）。

背景（2026-10-29）：原实现每轮只在**开启并延迟后**测一次电压，关断阶段既不测电压
也不测电流；返回体里 `records[].voltage_v` 是三路电压的 list、`after` 是 dict，
且文档里写死了"电容残留需 >=6s"（误导：放电时间取决于负载与电容，没有通用值）。

本次改动：每轮在 off / on 两个时刻各取一个快照（三路 `output_on` + `voltage_v` +
`current_a`），并在循环前后加 `before` / `after` 快照；放电时间改为按 off 快照电压
实测判断，不再写死数字。

本脚本用最小 SCPI 仿真证明：
  1) 关断后**确实**做了电压/电流测量（测量出现在 OUTP OFF 与下一个 OUTP ON 之间）；
  2) 每轮 off/on 快照与 before/after 结构完整、数值随开关状态变化；
  3) channel/output_mode/cycles 回填正确；cycles<1 抛 ValueError。

不覆盖：真实设备时序/测量精度（需真机跑真上下电；电源在使用中时不跑）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

import dh1766_control.dh1766 as dhmod          # noqa: E402
from dh1766_control import DH1766              # noqa: E402

# 测试里把驱动延时置 0（模块级常量，仅本进程生效，生产行为不变）
dhmod.CMD_DELAY_S = 0.0
dhmod.CHANNEL_SWITCH_DELAY_S = 0.0

VOLTS = [12.0, 5.0, 3.3]
CURRENTS = [0.1000, 0.2000, 0.0500]


class FakeClient:
    """最小 DH1766 SCPI 仿真：实现 power_cycle 用到的读写命令，并记录事件顺序。"""

    def __init__(self, outputs: list[bool] | None = None):
        self.events: list[tuple[str, str]] = []
        self.ch = 1
        self.outputs = list(outputs or [False, False, False])

    def write(self, cmd: str) -> None:
        self.events.append(("write", cmd))
        parts = cmd.split()
        if parts[0] == "INST:NSEL":
            self.ch = int(parts[1])
        elif parts[0] == "OUTP":
            self.outputs[self.ch - 1] = parts[1] == "ON"
        else:  # pragma: no cover - 不应出现
            raise AssertionError(f"unexpected write: {cmd}")

    def query(self, cmd: str) -> str:
        self.events.append(("query", cmd))
        if cmd in ("OUTP:TRAC?", "OUTP:SERI?", "OUTP:PARA?"):
            return "0"
        if cmd == "APPL:OUTP?":
            return ",".join("1" if s else "0" for s in self.outputs)
        if cmd == "MEAS:VOLT:ALL?":
            return ",".join(f"{v:.4f}" if s else "0.0000"
                            for v, s in zip(VOLTS, self.outputs))
        if cmd == "MEAS:CURR:ALL?":
            return ",".join(f"{c:.4f}" if s else "0.0000"
                            for c, s in zip(CURRENTS, self.outputs))
        raise AssertionError(f"unexpected query: {cmd}")   # pragma: no cover

    def close(self) -> None:
        pass


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def check(fails: list[str], name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name:56s} {detail}", flush=True)
    if not cond:
        fails.append(name)


def main() -> int:
    fails: list[str] = []

    print("S1 结构/字段（cycles=2，初始全关）", flush=True)
    fake = FakeClient()
    res = DH1766(fake).power_cycle("CH1", "NORM", off_delay_s=0,
                                   on_delay_s=0, cycles=2)
    check(fails, "top-level keys", set(res) >= {
        "cycles", "channel", "output_mode", "off_delay_s", "on_delay_s",
        "before", "records", "after"}, str(sorted(res)))
    check(fails, "cycles/channel/output_mode",
          res.get("cycles") == 2 and res.get("channel") == "CH1"
          and res.get("output_mode") == "NORM",
          f"{res.get('cycles')}/{res.get('channel')}/{res.get('output_mode')}")
    check(fails, "records length = cycles", len(res.get("records", [])) == 2)
    snap_keys = {"output_on", "voltage_v", "current_a"}
    check(fails, "before snapshot keys", set(res["before"]) == snap_keys)
    check(fails, "each record has cycle/off_delay_s/on_delay_s/off/on",
          all({"cycle", "off_delay_s", "on_delay_s", "off", "on"} <= set(r)
              for r in res["records"]))
    check(fails, "off/on snapshot keys",
          all(set(r["off"]) == snap_keys and set(r["on"]) == snap_keys
              for r in res["records"]))

    print("S2 数值随开关状态变化（关断=0，开启=设定值）", flush=True)
    b = res["before"]
    check(fails, "before: all outputs off",
          b["output_on"] == [False, False, False]
          and all(approx(v, 0.0) for v in b["voltage_v"].values()))
    for i, r in enumerate(res["records"], 1):
        off, on = r["off"], r["on"]
        check(fails, f"cycle {i} off: CH1 output_on=False, V=0, I=0",
              off["output_on"][0] is False
              and approx(off["voltage_v"]["CH1"], 0.0)
              and approx(off["current_a"]["CH1"], 0.0),
              f"V={off['voltage_v']['CH1']} I={off['current_a']['CH1']}")
        check(fails, f"cycle {i} on: CH1 output_on=True, V=12, I=0.1",
              on["output_on"][0] is True
              and approx(on["voltage_v"]["CH1"], VOLTS[0])
              and approx(on["current_a"]["CH1"], CURRENTS[0]),
              f"V={on['voltage_v']['CH1']} I={on['current_a']['CH1']}")
        check(fails, f"cycle {i} on: 其余两路仍关",
              on["output_on"][1:] == [False, False]
              and approx(on["voltage_v"]["CH2"], 0.0))
    check(fails, "after 与最后一轮 on 一致",
          res["after"]["output_on"] == [True, False, False]
          and approx(res["after"]["voltage_v"]["CH1"], VOLTS[0]))

    print("S3 关断阶段确实测量（测量夹在 OUTP OFF 与下一个 OUTP ON 之间）", flush=True)
    off_idx = [i for i, (k, c) in enumerate(fake.events)
               if k == "write" and c == "OUTP OFF"]
    on_idx = [i for i, (k, c) in enumerate(fake.events)
              if k == "write" and c == "OUTP ON"]
    check(fails, "2 cycles => 2xOFF / 2xON",
          len(off_idx) == 2 and len(on_idx) == 2,
          f"off={off_idx} on={on_idx}")
    mid_queries = [
        [c for k, c in fake.events[o + 1:on_idx[j]] if k == "query"]
        for j, o in enumerate(off_idx)
    ]
    ok_mid = all("MEAS:VOLT:ALL?" in q and "MEAS:CURR:ALL?" in q
                 for q in mid_queries)
    check(fails, "OFF 后、ON 前都有电压+电流测量", ok_mid, str(mid_queries))
    v_total = sum(1 for k, c in fake.events
                  if k == "query" and c == "MEAS:VOLT:ALL?")
    expected = 1 + 2 * 2 + 1     # before + cycles*2(off/on) + after
    check(fails, f"电压测量次数 = {expected}（before/off/on/after）",
          v_total == expected, f"got {v_total}")

    print("S4 初始已带电时的 before 快照 + 非法 cycles", flush=True)
    fake2 = FakeClient(outputs=[True, False, False])
    res2 = DH1766(fake2).power_cycle(1, "NORM", off_delay_s=0,
                                     on_delay_s=0, cycles=1)
    check(fails, "初始带电：before 读到 CH1 ON/12V",
          res2["before"]["output_on"][0] is True
          and approx(res2["before"]["voltage_v"]["CH1"], VOLTS[0]))
    check(fails, "初始带电：第一轮 off 后读到 0",
          res2["records"][0]["off"]["output_on"][0] is False
          and approx(res2["records"][0]["off"]["voltage_v"]["CH1"], 0.0))
    raised = False
    try:
        DH1766(FakeClient()).power_cycle(1, "NORM", cycles=0)
    except ValueError:
        raised = True
    check(fails, "cycles=0 抛 ValueError", raised)

    print(f"\n== result: {'all PASS' if not fails else 'FAIL: ' + ', '.join(fails)} ==",
          flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
