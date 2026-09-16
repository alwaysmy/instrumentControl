"""MHO **实机**复现"顶轨贴边/削顶"并验证 `rails()` / `diagnose` / `fit_channel`。

背景：现场文档（E_distance《示波器使用要点（MHO984D）》§1.5/§2.7）记录的坑——
把档位/偏置调到让信号**顶端贴出窗口**时，测量会给"看着合理的假值"或有值但不可信；
工具侧新增的 `rails()` 要能**分顶/底**报出来，`fit_channel()` 要能自动救回。

本脚本安全设计（共享实验台）：
- **不改触发配置**；默认挑"显示开着且幅度最大"的通道，可用 `--ch` 指定；
- 每一步写入前后都打印，并记录 before 快照；
- `finally` 里**恢复原始 scale/offset/display**（先 fit 救回再恢复，两条路都试）；
- 结束后清测量项。

跑法：
    python TEST_SCRIPTS/mho/verify_rails_live.py            # 自动挑通道
    python TEST_SCRIPTS/mho/verify_rails_live.py --ch 3     # 指定通道
    python TEST_SCRIPTS/mho/verify_rails_live.py --dry-run  # 只打印计划不写入
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402
from mho_control import MHO  # noqa: E402
from rigol_scope import snap_down  # noqa: E402

AP = argparse.ArgumentParser()
AP.add_argument("--ch", type=int, default=None, help="目标通道 1-4（默认自动挑有信号的）")
AP.add_argument("--dry-run", action="store_true", help="只打印计划，不写设备")
AP.add_argument("--resource", default=None)
ARGS = AP.parse_args()

fails: list[str] = []
records: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:56s} {str(detail)[:110]}", flush=True)
    if not ok:
        fails.append(name)


def main() -> int:
    res = ARGS.resource or resolve("mho")
    print(f"资源: {res}")
    try:
        s = MHO(res).connect()
    except Exception as e:
        print(f"  [SKIP] 设备不可达：{type(e).__name__}: {str(e)[:160]}")
        print("  → 检查示波器面板 Utility→I/O→LAN 的当前 IP 与网线，或改用 USB。")
        return 2

    with s:
        print(f"idn: {s.idn()}")
        snap = s.snapshot()
        trig_src = snap.get("edge_source")
        print(f"触发源: {trig_src}（**本脚本不改触发**）")

        # 1) 挑通道：显示开着 + VPP 最大；避免选中的是触发源（除非它才有信号）
        cand: list[tuple[int, float]] = []
        for ch in range(1, 5):
            info = snap["channels"].get(f"ch{ch}", {})
            if not info.get("display"):
                continue
            try:
                cand.append((ch, abs(s.measure_item("VPP", ch))))
            except ValueError:
                continue
        if not cand:
            print("  [SKIP] 所有开启通道都测不到 VPP——没有可用信号，无法复现顶轨。")
            s.measure_clear()
            return 2
        cand.sort(key=lambda x: -x[1])                 # 幅度大的优先
        trig_ch = next((c for c, _ in cand if str(trig_src).endswith(str(c))), None)
        if ARGS.ch:
            ch = ARGS.ch
        else:
            # 优先选**非触发源**通道（动它不影响触发观察）；只有触发源那路有信号时才用它
            ch = next((c for c, _ in cand if c != trig_ch), cand[0][0])
        vpp0 = dict(cand).get(ch, 0.0)
        print(f"目标通道: CH{ch}（VPP≈{vpp0:.4g} V）"
              f"{'  ⚠ 与触发源同通道' if str(trig_src).endswith(str(ch)) else ''}")

        before = s.configure_channel(ch)          # 纯回读
        print(f"  原始设定: {json.dumps(before['actual'], ensure_ascii=False)}")

        plan: list[dict] = []
        ok_repro = False
        try:
            # 2) 先确保可测且不贴边（fit_channel 会自动放大到可测）
            fit0 = s.fit_channel(ch)
            print(f"  fit_channel → ok={fit0['ok']} scale={fit0['after']['scale_v_div']:g} "
                  f"occupancy={fit0.get('occupancy')}")
            records.append({"step": "fit_initial", "result": fit0})

            # 3) 复现顶轨：沿 1-2-5 **逐档缩小 scale**（窗口变窄），直到 rails 报贴顶
            scale_now = s.channel_scale(ch)
            for i in range(8):
                nxt = snap_down(scale_now, min_scale=200e-6) or (scale_now / 2)
                plan.append({"iter": i + 1, "scale_from": scale_now, "scale_to": nxt})
                print(f"  [写] CH{ch} scale {scale_now:g} → {nxt:g} V/div（窗口变窄，逼出顶轨）")
                if not ARGS.dry_run:
                    s.configure_channel(ch, scale=nxt)
                    time.sleep(0.2)
                scale_now = nxt
                r = s.rails(ch)
                print(f"       rails: vtop={r['vtop']} vbase={r['vbase']} "
                      f"edges={r['edges_touching']} hints={r['hints'][:1]}")
                records.append({"step": "shrink", "iter": i + 1, "rails": r})
                if "top" in (r["edges_touching"] or []):
                    ok_repro = True
                    break
            check("复现顶轨：rails 报出 edges_touching 含 'top'", ok_repro,
                  f"共 {len(plan)} 档；hints={records[-1].get('rails', {}).get('hints', [])[:1]}")

            # 4) 顶轨贴边时，测量值与诊断（可能给"看着合理的假值"或有值但贴边）
            if not ARGS.dry_run:
                try:
                    vavg = s.measure_item("VAVG", ch)
                    print(f"      VAVG 仍有值 = {vavg:.6g} V（**贴边时不可信**）")
                except ValueError as e:
                    diag = s.diagnose_no_reading("VAVG", ch)
                    print(f"      VAVG 无有效值 → suspicious={diag['suspicious']} "
                          f"edges={diag.get('edges_touching')}")
                    check("无有效值时诊断分顶/底", diag.get("edges_touching") is not None
                          or diag["suspicious"] in ("off_screen", "near_edge"),
                          f"{diag['suspicious']} {diag.get('edges_touching')}")

            # 5) fit_channel 救回（验证 ok + 不贴边）
            if not ARGS.dry_run:
                fit1 = s.fit_channel(ch)
                records.append({"step": "fit_recover", "result": fit1})
                check("fit_channel 能救回（ok=True 且 margin_ok）",
                      bool(fit1["ok"]) and bool(fit1.get("margin_ok")),
                      f"scale={fit1['after']['scale_v_div']:g} occupancy={fit1.get('occupancy')}")
        finally:
            # 6) 恢复原始设定（哪怕上面抛了）
            if not ARGS.dry_run:
                try:
                    r = s.configure_channel(
                        ch, scale=before["actual"]["scale_v_div"],
                        offset=before["actual"]["offset_v"],
                        display=before["actual"]["display"])
                    print(f"  [恢复] CH{ch} → {json.dumps(r['actual'], ensure_ascii=False)}"
                          f"{' (adjusted: %s)' % r['adjusted'] if r['adjusted'] else ''}")
                    check("原设定已恢复（scale/offset/display 与 before 一致）",
                          abs((r['actual']['scale_v_div'] or 0) - (before['actual']['scale_v_div'] or 0)) < 1e-9
                          and abs((r['actual']['offset_v'] or 0) - (before['actual']['offset_v'] or 0)) < 0.02,
                          json.dumps(r['actual'], ensure_ascii=False))
                except Exception as e:
                    print(f"  [恢复失败] {type(e).__name__}: {e}")
                    fails.append("恢复原始设定")
            s.measure_clear()

    out = ROOT / "TEST_DATA" / "mho" / f"rails_live_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"resource": res, "ch": ch, "before": before,
                               "plan": plan, "records": records, "fails": fails},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n留痕: {out}")
    print(f"== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL'} ==")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
