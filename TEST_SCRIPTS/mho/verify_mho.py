"""MHO900（MHO984D）真机验收：库 + MCP 工具全链路，默认**只读**，留痕到 TEST_DATA/mho/。

用法：
    python TEST_SCRIPTS/mho/verify_mho.py                # 只读（不改任何设定）
    python TEST_SCRIPTS/mho/verify_mho.py --allow-stop   # 追加 RAW 内存波形（需 STOP，会短暂冻结采集）

覆盖：
    §1 身份与快照（IDN/版本/触发/采集/时基/四通道档位）
    §2 测量：单信源 + 双信源（延迟/相位）
    §3 波形：NORMal 模式 BYTE / WORD / ASCii 同一窗口交叉比对（WORD 字节序的实机证据）
    §4 波形读取参数写入 → SYST:ERR? → 回读比对 → 恢复（写操作三步铁律）
    §5 截屏 PNG（校验 PNG 魔数与尺寸）
    §6 RAW 内存波形：--allow-stop 时 STOP→读→恢复 RUN；否则验证"非 STOP 拒绝读"护栏
    §7 MCP 工具层（server.mho_*）全链路

安全：脚本不开关输出、不改通道档位/时基/触发、不 autoset、不复位；§4/§6 改动均
try/finally 恢复（§6 恢复原采集状态）。RAW 读取期间的 STOP 会短暂冻结采集——
共享实验台上先用 §1 的快照确认没有他人在跑长采集，或用 --allow-stop 显式授权。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

from common.resolver import resolve  # noqa: E402
from mho_control import MHO  # noqa: E402

# server 必须在**任何设备调用之前**导入：模块导入会启动 `_prewarm_visa_rm` 后台线程
# 预建/关闭一个 ResourceManager，与"同时进行的首次 open_resource"竞争时 VISA 会抛
# VI_ERROR_INV_OBJECT（-1073807346，"session or object reference is invalid"）。
# 实测：脚本里把 import server 放到 §7 才做，第一次 mho_status 就撞上；提到顶部即消除。
# （verify_all_devices.py 也是顶部导入，故从未暴露。）
import server  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "mho"
ALLOW_STOP = "--allow-stop" in sys.argv
rows: list[dict] = []


def rec(step: str, ok: bool, detail="") -> None:
    rows.append({"step": step, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {step:34s} {str(detail)[:120]}", flush=True)


def main() -> int:
    res = resolve("mho")           # 地址走解析层（不写死 IP）
    print(f"=== MHO 验收：resource={res}（解析层 mho）===\n", flush=True)
    s = MHO(res)
    s.connect()

    # ---------- §1 身份与快照 ----------
    print("§1 身份与快照", flush=True)
    idn = s.idn()
    rec("idn", "MHO" in idn.upper(), idn)
    snap = s.snapshot()
    rec("snapshot", bool(snap.get("timebase_scale_s_div")),
        f"status={snap['trigger_status']} sweep={snap['trigger_sweep']} "
        f"sr={snap['sample_rate_hz']:.3g}Sa/s depth={snap['acquire_depth']}")
    rec("drain_errors", True, s.drain_errors() or "队列干净")

    # ---------- §2 测量 ----------
    print("\n§2 测量（单/双信源）", flush=True)
    got: dict[str, float] = {}
    for item in ("VPP", "VMAX", "VMIN", "VAVG", "VRMS", "VAMP", "PERiod", "FREQuency"):
        try:
            v = s.measure_item(item, 1)
            got[item] = v
            rec(f"measure {item} CH1", True, f"{v:.6g}")
        except ValueError as e:
            # 无有效读数是**信号条件**问题（如噪声无周期），不是 API 故障
            rec(f"measure {item} CH1", "无有效值" in str(e), f"invalid/na: {str(e)[:80]}")
    # 双信源：相位/延迟需要两路都有完整周期，无值属预期
    for item in ("RRPHase", "RRDelay"):
        try:
            v = s.measure_item(item, 1, 2)
            rec(f"measure {item} CH1,CH2", True, f"{v:.6g}")
        except ValueError as e:
            rec(f"measure {item} CH1,CH2", "无有效值" in str(e), f"invalid/na: {str(e)[:80]}")
    rec("measure 未知项被拒", _expect_raises(lambda: s.measure_item("NOPE", 1)))
    rec("measure 双信源缺 src2 被拒", _expect_raises(lambda: s.measure_item("RRPHase", 1)))
    s.drain_errors()

    # ---------- §3 波形结构（只读；RUN 态下逐次采集不同，故只做结构断言）----------
    print("\n§3 波形 NORMal 结构断言（RUN 态：每次读的是新采集，不做跨格式严格比对）", flush=True)
    wf_b = s.get_waveform(1, points=1000, fmt="BYTE")
    wf_w = s.get_waveform(1, points=1000, fmt="WORD")
    wf_a = s.get_waveform(1, points=1000, fmt="ASCii")
    for nm, wf in (("BYTE", wf_b), ("WORD", wf_w), ("ASCii", wf_a)):
        rec(f"{nm} 长度/解析", wf["points"] == 1000 and len(wf["t"]) == 1000, f"{wf['points']} 点")
    rec("时间轴单调递增", all(b > a for a, b in zip(wf_b["t"], wf_b["t"][1:])),
        f"xinc={wf_b['xinc']:.4g}s t=[{wf_b['t'][0]:.4g},{wf_b['t'][-1]:.4g}]s")
    # RUN + AUTO 下被测信号逐次变化（本机为噪声样信号，Vpp 在 0.2~0.35V 间跳），
    # 三格式读数因此**不应**要求一致——严格交叉比对放 §6 冻结态做（字节序实证在那里）。
    vpp_b, vpp_w, vpp_a = (_vpp(wf) for wf in (wf_b, wf_w, wf_a))
    spread = max(vpp_b, vpp_w, vpp_a) / max(min(vpp_b, vpp_w, vpp_a), 1e-12)
    rec("三格式量级一致（宽松 <3×，RUN 态）", spread < 3.0,
        f"BYTE={vpp_b:.4g} WORD={vpp_w:.4g} ASCii={vpp_a:.4g} 最大/最小={spread:.2f}")
    try:
        m_vpp = s.measure_item("VPP", 1)
        d_m = abs(vpp_b - m_vpp) / max(m_vpp, 1e-9)
        rec("波形 Vpp 与设备测量同量级", d_m < 0.6, f"wf={vpp_b:.4g} meas={m_vpp:.4g}（差 {d_m:.1%}）")
    except ValueError as e:
        rec("波形 Vpp 与设备测量同量级", False, str(e)[:80])
    rec("NORMal 超 1000 点被拒", _expect_raises(lambda: s.get_waveform(1, points=5000)))
    rec("非法模式被拒", _expect_raises(lambda: s.get_waveform(1, mode="BOGUS")))
    # CSV 落盘（与 MCP 工具同格式）
    csv_p = OUT_DIR / f"mho_wave_ch1_{datetime.now():%Y%m%d_%H%M%S}.csv"
    csv_p.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_p, "w", newline="", encoding="utf-8") as f:
        f.write("time_s,voltage_v\n")
        f.writelines(f"{t:.9g},{v:.9g}\n" for t, v in zip(wf_b["t"], wf_b["v"]))
    rec("波形 CSV 落盘", csv_p.exists() and csv_p.stat().st_size > 1000,
        f"{csv_p.name} {csv_p.stat().st_size}B")

    # ---------- §4 写操作三步铁律（备份→改→查错→回读→恢复）----------
    print("\n§4 波形读取参数写入（备份→改→回读→恢复）", flush=True)
    bak = (s.query(":WAVeform:SOURce?").strip(), s.query(":WAVeform:MODE?").strip(),
           s.query(":WAVeform:FORMat?").strip(), s.query(":WAVeform:POINts?").strip())
    try:
        s.drain_errors()
        s.write(":WAVeform:FORMat ASCii")
        time.sleep(0.2)
        err = s.system_error()
        rb = s.query(":WAVeform:FORMat?").strip()
        rec("写 FORMat ASCii + 查错", err is None, f"syst_err={err}")
        rec("写 FORMat 回读比对", rb.upper().startswith("ASC"), f"回读 {rb!r}（写 ASCii）")
        s.write(":WAVeform:FORMat WORD")
        time.sleep(0.2)
        rb2 = s.query(":WAVeform:FORMat?").strip()
        rec("写回 FORMat WORD", rb2.upper().startswith("WORD"), f"回读 {rb2!r}")
    finally:
        s.write(f":WAVeform:SOURce {bak[0]}")
        s.write(f":WAVeform:MODE {bak[1]}")
        s.write(f":WAVeform:FORMat {bak[2]}")
        s.write(f":WAVeform:POINts {bak[3]}")
        time.sleep(0.2)
        now = (s.query(":WAVeform:SOURce?").strip(), s.query(":WAVeform:MODE?").strip(),
               s.query(":WAVeform:FORMat?").strip(), s.query(":WAVeform:POINts?").strip())
        rec("恢复原波形读取参数", _same_shape(bak, now), f"{bak} -> {now}")

    # ---------- §5 截屏 ----------
    print("\n§5 截屏", flush=True)
    png = OUT_DIR / f"mho_verify_{datetime.now():%Y%m%d_%H%M%S}.png"
    s.screenshot_png(png)
    head = png.read_bytes()[:8]
    rec("截屏 PNG 魔数", head == b"\x89PNG\r\n\x1a\n", f"{head!r}")
    rec("截屏体积合理", png.stat().st_size > 20000, f"{png.stat().st_size}B -> {png.name}")
    rec("非法截图格式被拒", _expect_raises(lambda: s.screenshot("TIFF")))

    # ---------- §6 RAW 内存波形 + 冻结态三格式交叉比对（字节序实证）----------
    print("\n§6 RAW 内存波形与冻结态交叉比对", flush=True)
    status_before = s.trigger_status()
    if not ALLOW_STOP:
        rec("非 STOP 时 RAW 被拒（护栏）", _expect_raises(lambda: s.get_waveform(1, mode="RAW")))
        print(f"      当前 {status_before}；RAW 与字节序实证需 --allow-stop（会短暂冻结采集）", flush=True)
    else:
        try:
            s.stop()
            time.sleep(0.8)
            rec("STOP 生效", s.trigger_status() == "STOP", f"status={s.trigger_status()}")
            # 冻结态：三次读的是**同一份**采集，此时才可做严格跨格式比对
            fb = s.get_waveform(1, points=1000, fmt="BYTE")
            fw = s.get_waveform(1, points=1000, fmt="WORD")
            fa = s.get_waveform(1, points=1000, fmt="ASCii")
            vb, vw, va = (_vpp(wf) for wf in (fb, fw, fa))
            d_bw = abs(vb - vw) / max(vw, 1e-9)
            d_wa = abs(vw - va) / max(va, 1e-9)
            # BYTE 是 8bit：yinc ≈ WORD 的 256 倍（实测 0.0683 V/code @2V/div），
            # 小信号只占个位数码值 → ±1 码就是百分之几十，**必须按量化容差判**。
            q_codes = vb / max(fb["yinc"], 1e-12)
            tol = max(0.02, 4 * fb["yinc"] / max(vb, 1e-9))     # 允许两端各 ±2 码
            rec("冻结态 BYTE/WORD Vpp 一致（按 8bit 量化容差）", d_bw < tol,
                f"{vb:.5g} vs {vw:.5g}（差 {d_bw:.1%}，信号仅 {q_codes:.1f} 码，容差 {tol:.0%}）")
            rec("冻结态 WORD/ASCii Vpp 一致（<2%，两者都是高分辨率）", d_wa < 0.02,
                f"{vw:.5g} vs {va:.5g}（差 {d_wa:.2%}）→ WORD 低字节在前成立")
            try:
                m_vpp = s.measure_item("VPP", 1)
                # 用 **WORD** 读数与设备测量比：BYTE 只有 8bit（本例信号仅 3 码），
                # 拿它比数值会得到"差 20%+"的假告警 —— 量值一律看 WORD/ASCii。
                d_m = abs(vw - m_vpp) / max(m_vpp, 1e-9)
                rec("冻结态 WORD Vpp vs 设备测量（<15%）", d_m < 0.15,
                    f"WORD={vw:.5g} meas={m_vpp:.5g}（差 {d_m:.1%}；BYTE 因量化仅 {vb:.4g}）")
            except ValueError as e:
                rec("冻结态 WORD Vpp vs 设备测量（<15%）", False, str(e)[:80])
            wf_raw = s.get_waveform(1, mode="RAW", fmt="BYTE", points=50000)
            rec("RAW 读取 50000 点", wf_raw["points"] == 50000,
                f"{wf_raw['points']} 点 xinc={wf_raw['xinc']:.4g}s vpp={_vpp(wf_raw):.5g}")
            # RAW 与深度/采样率的一致性：xinc 应等于 1/采样率
            sr = s.sample_rate()
            rec("RAW xinc 与采样率自洽", abs(wf_raw["xinc"] - 1.0 / sr) / (1.0 / sr) < 0.01,
                f"xinc={wf_raw['xinc']:.4g}s 1/sr={1.0 / sr:.4g}s（sr={sr:.4g}Sa/s）")
            raw_p = OUT_DIR / f"mho_raw_ch1_{datetime.now():%Y%m%d_%H%M%S}.csv"
            with open(raw_p, "w", newline="", encoding="utf-8") as f:
                f.write("time_s,voltage_v\n")
                f.writelines(f"{t:.9g},{v:.9g}\n" for t, v in zip(wf_raw["t"], wf_raw["v"]))
            rec("RAW CSV 落盘", raw_p.stat().st_size > 100000, f"{raw_p.name} {raw_p.stat().st_size}B")
        finally:
            if status_before.startswith("RUN"):
                s.run()
                time.sleep(0.5)
            rec("恢复原采集状态", True, f"{status_before} -> {s.trigger_status()}")

    # ---------- §7 MCP 工具层 ----------
    print("\n§7 MCP 工具层（server.mho_*）", flush=True)
    for name, call in (
        ("mho_status", lambda: server.mho_status()),
        ("mho_measure_item(VPP)", lambda: server.mho_measure_item("VPP", 1)),
        ("mho_measure_item(双信源)", lambda: server.mho_measure_item("RRPHase", 1, 2)),
        ("mho_get_waveform", lambda: server.mho_get_waveform(ch=1, points=1000)),
        ("mho_screenshot", lambda: server.mho_screenshot()),
        ("mho_autoset(无 confirm 被拒)", lambda: server.mho_autoset(confirm=False)),
    ):
        r = json.loads(call())
        if "无 confirm" in name:
            ok = r.get("error_type") == "confirm_required"
            detail = r.get("error_type")
        elif "双信源" in name:
            ok = bool(r.get("ok")) or r.get("error_type") in ("device_error", "param_validation")
            detail = str(r.get("result") or r.get("error"))[:100]
        else:
            ok = bool(r.get("ok"))
            detail = f"resource={r.get('resource')} " + str(r.get("result") or r.get("error"))[:90]
        rec(name, ok, detail)

    s.close()

    # ---------- 留痕 ----------
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"verify_mho_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    out.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "resource": res, "allow_stop": ALLOW_STOP,
        "mode": "只读（§4 写入即恢复；§6 仅在 --allow-stop 时 STOP/恢复）",
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 结果: {len(rows) - n_fail}/{len(rows)} PASS ==\n留痕: {out}")
    return 1 if n_fail else 0


def _vpp(wf: dict) -> float:
    return max(wf["v"]) - min(wf["v"])


def _same_shape(a: tuple, b: tuple) -> bool:
    """回读比对：短格式/大小写差异（NORM vs NORMal）视为相等。"""
    return all(x.upper().startswith(y.upper()[:4]) or y.upper().startswith(x.upper()[:4])
               for x, y in zip(a, b))


def _expect_raises(fn) -> bool:
    try:
        fn()
    except (ValueError, RuntimeError):
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
