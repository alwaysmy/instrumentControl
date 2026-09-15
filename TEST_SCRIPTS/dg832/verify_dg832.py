"""DG832（RIGOL DG800 系列）真机验收：库 + MCP 工具，默认**只读**，留痕 TEST_DATA/dg832/。

用法：
    python TEST_SCRIPTS/dg832/verify_dg832.py                # 只读（不改任何设定）
    python TEST_SCRIPTS/dg832/verify_dg832.py --allow-write  # 追加写路径（改参数→回读→恢复）

覆盖：
    §1 身份与连接（*IDN?、解析层 kind=dg、资源串回填）
    §2 快照与只读查询（status/protect/APPL?/OUTP?/错误队列）
    §3 保护联锁（protect_required）——**只读地**验证"未开保护时写幅度被拒"
    §4 MCP 工具层（server.dg_*）
    §5 [--allow-write] 写路径：设保护→改频率→回读比对→恢复原频率与保护状态

安全：默认全程只读——不开关输出、不改波形/幅度/偏移/保护、不触发扫频；
§5 仍需操作者确认这台信号源当前**没有在驱动别人的实验**（输出可能已开）。
脚本不碰输出开关（`dg_output` 仅在 --allow-write 且显式 --allow-output 时才验证）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))
sys.path.insert(0, str(ROOT / "mcp_instruments"))

from common.resolver import resolve  # noqa: E402
from dg832_control import DG832, ProtectRequiredError, discover  # noqa: E402

# server 要在任何设备调用之前导入：导入会启动 VISA 预热线程，
# 与并发的首次 open_resource 竞争时可能瞬时 VI_ERROR_INV_OBJECT（见 MHO 验收注释）。
import server  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dg832"
ALLOW_WRITE = "--allow-write" in sys.argv
ALLOW_OUTPUT = "--allow-output" in sys.argv
rows: list[dict] = []


def rec(step: str, ok: bool, detail="") -> None:
    rows.append({"step": step, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {step:36s} {str(detail)[:120]}", flush=True)


def main() -> int:
    print("=== §1 发现与身份 ===", flush=True)
    found = [d for d in discover() if "DG8" in str(d.get("idn", "")).upper()]
    rec("VISA 发现 DG832", bool(found), str(found[0] if found else "未找到"))
    res = resolve("dg")                      # 解析层 kind=dg（不写死地址）
    print(f"      解析层 dg -> {res}", flush=True)
    g = DG832(resource=res)
    g.connect()
    idn = g.idn()
    rec("idn", "DG832" in idn.upper(), idn)
    rec("模型注册表", g.model in __import__("dg832_control").MODEL_REGISTRY, f"model={g.model}")

    print("\n=== §2 快照与只读查询 ===", flush=True)
    st = g.status()
    rec("status", "idn" in st and "ch1" in st,
        f"ch1={st['ch1']['shape']}@{st['ch1']['freq']} out={st['ch1']['output']} load={st['ch1']['load']}")
    rec("ch2 快照", "ch2" in st, f"ch2={st['ch2']['shape']}@{st['ch2']['freq']} out={st['ch2']['output']}")
    prot1 = g.get_voltage_limit(1)
    rec("电压保护查询", "state" in prot1,
        f"CH1 state={prot1['state']} high={prot1['high']} low={prot1['low']}")
    rec("只读 SCPI 查询", g.query("*IDN?").upper().startswith("RIGOL"), g.query(":OUTP1?"))
    errs = g.check_error()
    rec("错误队列", not errs, f"{errs or '空'}")

    print("\n=== §3 保护联锁（只读验证「未开保护 → 写幅度被拒」）===", flush=True)
    # 仅当保护确实未开时才验证（开了保护就不去动它，避免改变现场状态）
    if str(prot1["state"]).strip() not in ("1", "ON"):
        try:
            g.set_amp(1, 1.0)
            rec("未开保护写幅度被拒", False, "期望 ProtectRequiredError，实际写入成功")
        except ProtectRequiredError as e:
            rec("未开保护写幅度被拒", True, str(e)[:80])
    else:
        rec("保护联锁（跳过：CH1 保护已开）", True,
            "现场已开保护，不做'未开保护'路径验证以免改状态")

    print("\n=== §4 MCP 工具层（server.dg_*）===", flush=True)
    for name, call, expect_ok in (
        ("dg_status", lambda: server.dg_status(), True),
        ("dg_get_protect(CH1)", lambda: server.dg_get_protect(1), True),
        ("dg_query(:OUTP1?)", lambda: server.dg_query(":OUTP1?"), True),
        ("dg_query(多命令走私被拒)", lambda: server.dg_query("*IDN?;*RST"), False),
        ("dg_check_error", lambda: server.dg_check_error(), True),
        ("dg_output(无 confirm 被拒)", lambda: server.dg_output(1, True, confirm=False), False),
    ):
        r = json.loads(call())
        ok = bool(r.get("ok")) is expect_ok
        detail = str(r.get("result") or r.get("error"))[:110]
        if not expect_ok and r.get("error_type") not in ("confirm_required", "forbidden", "param_validation"):
            ok = False
        rec(name, ok, f"resource={r.get('resource')} {detail}")

    if ALLOW_WRITE:
        print("\n=== §5 写路径（改频率→回读→恢复；不动输出开关）===", flush=True)
        cfg0 = g.get_wave_config(1)
        prot0 = g.get_voltage_limit(1)
        try:
            if str(prot0["state"]).strip() not in ("1", "ON"):
                # 开保护要用足够宽的窗口，避免把当前幅度/偏移挡在外面
                hi = max(abs(float(cfg0["amp"] or 1)), abs(float(cfg0["offset"] or 0)), 1.0) * 2 + 1
                g.set_voltage_limit(1, high=hi, low=-hi, state=True)
                rec("开启保护（恢复用快照已存）", True, f"high={hi} low={-hi}")
            f0 = float(cfg0["freq"])
            f1 = f0 * 1.1 if f0 * 1.1 < 1e6 else f0 / 1.1
            r = g.set_freq(1, f1)
            back = float(g.query(":SOUR1:FREQ?"))
            rec("写频率 + 回读比对", abs(back - f1) / f1 < 1e-3, f"{f0:g} → 写 {f1:g} → 回读 {back:g}")
            rec("错误队列（写后）", not g.check_error(), "查错干净")
        finally:
            g.set_freq(1, float(cfg0["freq"]))
            if str(prot0["state"]).strip() not in ("1", "ON"):
                g.set_voltage_limit(1, high=float(prot0["high"]), low=float(prot0["low"]),
                                    state=False)
            cfg2 = g.get_wave_config(1)
            rec("恢复原配置", abs(float(cfg2["freq"]) - float(cfg0["freq"])) < 1e-6,
                f"freq {cfg0['freq']} -> {cfg2['freq']}；保护 state={g.get_voltage_limit(1)['state']}")
        if ALLOW_OUTPUT:
            rec("dg_output 路径", False, "需显式授权：本脚本默认不碰输出开关（请按需单独执行）")

    g.close()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"verify_dg832_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    out.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "resource": res, "allow_write": ALLOW_WRITE, "allow_output": ALLOW_OUTPUT,
        "mode": "只读（§5 仅在 --allow-write 时改频率并恢复）",
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 结果: {len(rows) - n_fail}/{len(rows)} PASS ==\n留痕: {out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
