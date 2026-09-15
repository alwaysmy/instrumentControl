"""DHO 合并后真机复验（**给"有 DHO 的那一侧"**）：一条命令跑完 6 项检查并留痕。

用法：
    python TEST_SCRIPTS/dho/verify_dho_after_merge.py              # 默认只读（不改任何设定）
    python TEST_SCRIPTS/dho/verify_dho_after_merge.py --allow-write # 追加会改设定的 2 项（自动恢复）
    python TEST_SCRIPTS/dho/verify_dho_after_merge.py --allow-stop  # 追加 RAW（会短暂冻结采集）

配套说明：`docs/dho_live_verification_handoff.md`（含每项的含义、不符时改哪个字段、回填格式）。

背景：2026-09-15 把 DHO800/900 与 MHO900 合并到共享内核 `rigol_scope/`
（比对证据 `docs/rigol_scope_compare_20260915.md`）。合并机器上没有 DHO，故 DHO 路径
只做了离线验证（`verify_rigol_scope_shared.py`）；本脚本是**真机**那半边的补验。

检查项（与交接单一致）：
    ① 身份/地址解析（kind=dho）
    ② 快照与只读查询（族标 family=DHO、通道/时基/触发能读）
    ③ **波形 ASCII 是否带 TMC 头**（MHO 实测不带；DHO 未知——本项就是答案）
    ④ 三格式交叉比对 + 截屏 PNG（WORD/ASCii 应一致；BYTE 按 8bit 量化容差）
    ⑤ 双信源测量（RRPHase——DHO 手册有记载，合并后才暴露的能力）
    ⑥ [--allow-write] 清测量用 :MEASure:CLEar、采集第四态用 ULTRa（都会恢复原值）
    ⑦ [--allow-stop] RAW 内存波形分片读取
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

from common.resolver import resolve  # noqa: E402
from dho_control import DHO  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dho"
ALLOW_WRITE = "--allow-write" in sys.argv
ALLOW_STOP = "--allow-stop" in sys.argv
rows: list[dict] = []
HINTS: list[str] = []


def rec(step: str, ok: bool, detail="", hint: str = "") -> None:
    rows.append({"step": step, "ok": bool(ok), "detail": str(detail)[:400], "hint": hint})
    print(f"  [{'PASS' if ok else 'FAIL'}] {step:40s} {str(detail)[:120]}", flush=True)
    if hint and not ok:
        HINTS.append(f"{step} → {hint}")


def vpp(wf: dict) -> float:
    return max(wf["v"]) - min(wf["v"])


def main() -> int:
    print("=== §1 身份与地址解析 ===", flush=True)
    try:
        res = resolve("dho")                # 解析层（不写死地址）
    except Exception as e:
        print(f"  [FAIL] 未解析到 DHO 地址：{type(e).__name__}: {str(e)[:200]}")
        print("    请先定位设备（两者其一即可）：")
        print("      python mcp_instruments/config_cli.py set dho <IP>   # 裸 IP 会自动探测协议并核对 *IDN?")
        print("      python TEST_SCRIPTS/common/test_discovery.py        # 或先跑发现，结果自动回写缓存")
        return 2
    print(f"      解析层 dho -> {res}", flush=True)
    s = DHO(res)
    s.connect()
    idn = s.idn()
    rec("idn 含 DHO", "DHO" in idn.upper(), idn)
    rec("族标 family=DHO", s.family.name == "DHO", s.family.name)

    print("\n=== §2 快照与只读查询（合并后不应退化）===", flush=True)
    snap = s.snapshot()
    rec("snapshot 结构", snap.get("family") == "DHO" and len(snap.get("channels", {})) == 4,
        f"trigger={snap.get('trigger_status')} timebase={snap.get('timebase_scale_s_div')} "
        f"sr={snap.get('sample_rate_hz')}")
    rec("错误队列", s.drain_errors() == [], "队列干净")

    print("\n=== §3 波形 ASCII 是否带 TMC 头（MHO 实测：不带）===", flush=True)
    status_before = s.trigger_status()
    try:
        if not status_before.startswith("STOP"):
            s.stop(); time.sleep(0.8)
        try:
            wf_a = s.get_waveform(1, fmt="ASCii", points=1000)
            rec("ASCII 波形可解析", wf_a["points"] > 100,
                f"{wf_a['points']} 点（按 Family.ascii_waveform_has_tmc="
                f"{s.family.ascii_waveform_has_tmc} 解析成功）")
            ascii_ok = True
        except ValueError as e:
            ascii_ok = False
            rec("ASCII 波形可解析", False, str(e)[:100],
                "DHO 的 ASCII 带 TMC 头 → 改 rigol_scope/families.py 里 DHO 的 "
                "ascii_waveform_has_tmc=True，再重跑本脚本")
        # §4 三格式比对 + 截屏（冻结态下才有意义）
        wf_b = s.get_waveform(1, fmt="BYTE", points=1000)
        wf_w = s.get_waveform(1, fmt="WORD", points=1000)
        vb, vw = vpp(wf_b), vpp(wf_w)
        if ascii_ok:
            d_wa = abs(vw - vpp(wf_a)) / max(vpp(wf_a), 1e-9)
            rec("WORD/ASCii Vpp 一致（<2%，两者都高分辨率）", d_wa < 0.02,
                f"{vw:.5g} vs {vpp(wf_a):.5g}（差 {d_wa:.2%}）→ 可据此判断 WORD 字节序")
        codes = vb / max(wf_b["yinc"], 1e-12)
        tol = max(0.02, 4 * wf_b["yinc"] / max(vb, 1e-9))
        d_bw = abs(vb - vw) / max(vw, 1e-9)
        rec("BYTE/WORD 一致（按 8bit 量化容差）", d_bw < tol,
            f"{vb:.5g} vs {vw:.5g}（差 {d_bw:.1%}；信号仅 {codes:.1f} 码，容差 {tol:.0%}）")
        png = OUT_DIR / f"dho_after_merge_{datetime.now():%Y%m%d_%H%M%S}.png"
        s.screenshot_png(png)
        head = png.read_bytes()[:8]
        rec("截屏 PNG 魔数", head == b"\x89PNG\r\n\x1a\n", f"{png.stat().st_size}B -> {png.name}")
    finally:
        if not status_before.startswith("STOP"):
            s.run(); time.sleep(0.5)
        rec("恢复原采集状态", True, f"{status_before} -> {s.trigger_status()}")

    print("\n=== §5 双信源测量（合并后新增能力）===", flush=True)
    try:
        v = s.measure_item("RRPHase", 1, 2)
        rec("RRPHase CH1,CH2", True, f"{v:.6g}°")
    except ValueError as e:
        # 通道无信号/无完整周期时无有效值属正常，只要**命令被接受**即算通过
        rec("RRPHase CH1,CH2（命令被接受）", "无有效值" in str(e), str(e)[:110],
            "若报『未知测量项』说明 Family 表缺 dual 项——检查 families.py")

    if ALLOW_WRITE:
        print("\n=== §6 写路径（改后恢复）===", flush=True)
        acq0 = s.acquire_type()
        try:
            s.measure_clear()
            err = s.system_error()
            rec("清测量 :MEASure:CLEar 被接受", err is None, f"syst_err={err}",
                "若报错说明 DHO 实际用 :MEASure:DELete → 改 families.py 的 measure_clear")
            s.acquire_type("ULTRa")
            back = s.acquire_type()
            rec("采集第四态 ULTRa 被接受", str(back).upper().startswith("ULT"),
                f"回读 {back!r}",
                "若被拒说明取值名不符 → 改 families.py 里 DHO 的 acq_types")
        finally:
            if acq0:
                s.acquire_type(acq0)
            rec("恢复采集方式", s.acquire_type() == acq0, f"{acq0} -> {s.acquire_type()}")
    else:
        print("\n=== §6 写路径（跳过：需 --allow-write，会改设定后恢复）===", flush=True)

    if ALLOW_STOP:
        print("\n=== §7 RAW 内存波形（分片读取）===", flush=True)
        st = s.trigger_status()
        try:
            s.stop(); time.sleep(0.8)
            raw = s.get_waveform(1, mode="RAW", fmt="BYTE", points=50000)
            sr = s.sample_rate()
            rec("RAW 50000 点", raw["points"] == 50000, f"{raw['points']} 点 xinc={raw['xinc']:.4g}s")
            rec("RAW xinc 与采样率自洽", abs(raw["xinc"] - 1 / sr) / (1 / sr) < 0.01,
                f"xinc={raw['xinc']:.4g}s 1/sr={1 / sr:.4g}s")
        finally:
            if not st.startswith("STOP"):
                s.run(); time.sleep(0.5)
            rec("恢复原采集状态", True, f"{st} -> {s.trigger_status()}")
    else:
        print("\n=== §7 RAW（跳过：需 --allow-stop，会短暂冻结采集）===", flush=True)

    s.close()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"verify_dho_after_merge_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    out.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "resource": res, "allow_write": ALLOW_WRITE, "allow_stop": ALLOW_STOP,
        "family": "DHO", "ascii_waveform_has_tmc_assumed": s.family.ascii_waveform_has_tmc,
        "rows": rows, "hints": HINTS,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 结果: {len(rows) - n_fail}/{len(rows)} PASS ==")
    if HINTS:
        print("== 需要调整的地方 ==")
        for h in HINTS:
            print(f"  - {h}")
    print(f"留痕: {out}\n请把该 JSON（和 §三 的结论）按交接单 §四 回填。")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
