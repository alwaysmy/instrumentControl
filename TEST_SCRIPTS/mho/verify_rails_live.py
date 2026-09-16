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
from rigol_scope import snap_1_2_5, snap_up  # noqa: E402

AP = argparse.ArgumentParser()
AP.add_argument("--ch", type=int, default=None, help="目标通道 1-4（默认自动挑有信号的）")
AP.add_argument("--dry-run", action="store_true", help="只打印计划，不写设备")
AP.add_argument("--resource", default=None)
ARGS = AP.parse_args()

fails: list[str] = []
records: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ARGS.dry_run:      # 没真写设备，贴边类断言无意义 → 标 SKIP
        print(f"  [SKIP] {name:56s} (dry-run 不写设备) {str(detail)[:70]}", flush=True)
        return
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:56s} {str(detail)[:110]}", flush=True)
    if not ok:
        fails.append(name)


def retry(fn, times: int = 3, delay: float = 0.25):
    """测量偶发无有效值（现场实测：面板有值但 SCPI 回 9.9E37，重读即正常）→ 重试。"""
    last: Exception | None = None
    for _ in range(times):
        try:
            return fn()
        except ValueError as e:
            last = e
            time.sleep(delay)
    raise last  # type: ignore[misc]


def main() -> int:
    res = ARGS.resource or resolve("mho")
    print(f"资源: {res}")
    try:
        # 注意：`connect()` 的返回值是**资源串**（库里如此设计），实例要用 `with` 拿
        s = MHO(res)
        s.connect()
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
            try:                      # 偶发无有效值很常见 → 用重试版
                cand.append((ch, abs(s.measure_retry("VPP", ch, tries=5))))
            except ValueError:
                cand.append((ch, 0.0))   # 读不到也保留候选（有 --ch 时仍可指定它）
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
        try:  # noqa: SIM105  下面的步骤整体兜异常：出错记 FAIL，finally 仍会恢复原设定
            # 2) 先确保可测且不贴边（fit_channel 会自动放大到可测）
            #    ⚠ dry-run 时**不能调它**——fit_channel 会真的写档位/偏置（踩过：
            #    一次 dry-run 把 CH2 留在 0.05 V/div 且因恢复被 dry-run 跳过而没还回去）
            if ARGS.dry_run:
                print("  [SKIP] fit_channel（dry-run 不写设备）")
            else:
                fit0 = s.fit_channel(ch)
                print(f"  fit_channel → ok={fit0['ok']} scale={fit0['after']['scale_v_div']:g} "
                      f"occupancy={fit0.get('occupancy')}")
                records.append({"step": "fit_initial", "result": fit0})

            # 3) **瞄准顶轨**：把窗口上沿对准 VMAX（拿实测值反算 scale/offset）
            #    为什么不是"一路缩小 scale"：那只会先撞**底**轨（取决于信号在窗内的位置）。
            #    窗口 = [中心−4·scale, 中心+4·scale]，中心 = −offset
            #    → 要让顶轨贴住上沿：中心 = VMAX − 4·scale，即 offset = 4·scale − VMAX
            vmax = retry(lambda: s.measure_item("VMAX", ch))
            vmin = retry(lambda: s.measure_item("VMIN", ch))
            print(f"  实测轨: VMAX={vmax:.6g} VMIN={vmin:.6g}（VPP={vmax - vmin:.6g}）")

            def aim(top_v: float, scale_v: float) -> dict:
                """把窗口上沿对准 top_v（先 scale 后 offset，并回读）。

                ⚠ **必须按偏置量程抬档**：偏置上限随档位变（实测 0.05 V/div 只允许 ±1 V），
                小档位下目标偏置会被静默钳制 → 窗口跑到别处（实机踩过）。
                这里闭环：写 → 回读，被钳就把档位抬一档再来，直到放得下。
                """
                sc = scale_v
                res: dict = {}
                for _ in range(8):
                    off = 4.0 * sc - top_v
                    res = s.configure_channel(ch, scale=sc, offset=off)
                    if not (res.get("adjusted") or {}).get("offset"):
                        print(f"  [写] CH{ch} scale={sc:g} V/div, offset={off:.6g} V "
                              f"（窗口上沿目标 {top_v:.6g} V）")
                        return res
                    print(f"  [抬档] {sc:g} V/div 放不下偏置 {off:.6g} V → 换大档重试")
                    nxt = snap_up(sc, 10.0)
                    if nxt is None:
                        return res
                    sc = nxt
                return res

            # 3a) 上沿 = VMAX（贴住不削）→ 期望 top_touching=True、bottom=False
            span = vmax - vmin
            scale_aim = snap_1_2_5(max(span / 2.0, 0.02))     # 够窄才有意义
            if not ARGS.dry_run:
                applied = aim(vmax, scale_aim)
                time.sleep(0.2)
            plan.append({"step": "aim_top", "scale": scale_aim, "top": vmax})
            r = s.rails(ch)
            records.append({"step": "aim_top", "rails": r})
            print(f"       rails: vtop={r['vtop']} vbase={r['vbase']} "
                  f"edges={r['edges_touching']}")
            check("① 顶轨贴住上沿：edges_touching 含 'top' 且不含 'bottom'",
                  r["edges_touching"] == ["top"],
                  f"edges={r['edges_touching']} window={r['window']}")

            # 3b) 越过一点：上沿压到 VMIN+20%·span 处 → 顶端被切（可能给"看着合理的假值"）
            if not ARGS.dry_run:
                aim(vmin + 0.2 * span, scale_aim)
                time.sleep(0.2)
            r2 = s.rails(ch)
            records.append({"step": "clip_top", "rails": r2})
            print(f"       rails: vtop={r2['vtop']} vmax={r2['vmax']} edges={r2['edges_touching']}")
            # 实机行为（2026-09-16 实测两种表现都可能）：
            #   a) 顶端极值失效/贴边 → edges 含 top（"顶端已在窗外"）
            #   b) 极值与轨值**全**不可测 → unreadable=True（连 VMIN 也回 9.9E37）
            # 两种都必须**明确报出来**，不能给空的 edges 让人以为没问题。
            warned = bool(r2.get("unreadable")) or "top" in (r2["edges_touching"] or [])
            check("② 顶端被切：明确报出'出窗/不可测'（不静默）", warned,
                  f"edges={r2['edges_touching']} unreadable={r2.get('unreadable')} "
                  f"vmax={r2['vmax']} vmin={r2['vmin']} window_top={r2['window']['top_v']:.6g}")
            if warned and r2.get("hints"):
                print(f"      提示: {r2['hints'][0][:110]}")

            # 4) 读数的两种命运：有效但贴边（不可信）或无效 → 诊断分类
            try:
                vavg = s.measure_item("VAVG", ch)
                print(f"      VAVG 仍有值 = {vavg:.6g} V（**贴边/削顶时不可信**）")
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
                # 判据用"读数有效 + 不贴边"：占屏率可能被**偏置量程**限制
                # （实测 0.05 V/div 只允许 ±1 V 偏置，直流信号因此做不到 0.4 占屏率）
                check("fit_channel 救回：读数有效且不贴边（margin_ok）",
                      bool(fit1.get("margin_ok")) and fit1.get("measured") is not None,
                      f"ok={fit1['ok']} scale={fit1['after']['scale_v_div']:g} "
                      f"occupancy={fit1.get('occupancy')} reasons={fit1.get('reasons')}")
        except Exception as e:                      # 任何设备/协议异常都不该让脚本崩
            print(f"  [FAIL] 复现流程异常：{type(e).__name__}: {str(e)[:140]}")
            fails.append(f"复现流程异常: {type(e).__name__}")
        finally:
            # 6) 恢复原始设定（哪怕上面抛了）；dry-run 没写过设备就不用恢复
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
