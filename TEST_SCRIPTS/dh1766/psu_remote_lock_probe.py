"""DH1766 远程锁定（Remote/Lock）只读探测——核实"是否只要远程连接就被锁"。

背景：用户报告"DH1766 好像只要远程连接就会被锁"。手册 4.2 的
`SYST:COMM:RLST:STAT?`（手册写法）在本机固件 V0.1.4.3 **无响应/超时**（见 docs/EXPERIENCE.md），
故本脚本用**只读查询**穷举候选状态查询形式，并对比多次独立会话（每次新建连接）
的响应差异，判断"连接本身"是否改变工作模式。

安全约束（本轮用户指定）：
  - 只开/关 VISA 会话 + 只读查询（SCPI-99 §6.2.3 查询无副作用）；
  - **不写任何命令**：不动电压/电流/输出开关/模式，不发送 SYST:REM/SYST:RWL/SYST:LOC；
  - 设备仍接负载（"还连着设备"），输出状态只用 APPL:OUTP? 查询读取；
  - 每条候选查询各起一个独立会话：避免"不响应命令"造成的响应错位污染后续判定。

留痕：TEST_DATA/dh1766/psu_lock_probe_<stamp>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402
from common.visa_client import VisaClient  # noqa: E402

# 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
RESOURCE = resolve("psu")
OUT_DIR = ROOT / "TEST_DATA" / "dh1766"

# 已知可用的只读查询（先验证会话本身工作）
BASELINE_QUERIES = ("*IDN?", "APPL:OUTP?", "APPL:VOLT?", "APPL:CURR?", "SYST:ERR?")

# 候选"工作模式/锁定状态"查询（全只读；正确形式未知，逐个试）
STATE_QUERIES = (
    "SYST:COMM:RLST:STAT?",
    "SYST:COMM:RLST?",
    "SYST:RLST:STAT?",
    "SYST:RLST?",
    "SYST:REM?",
    "SYST:RWL?",
    "SYST:LOC?",
    "STAT:OPER:COND?",
    "STAT:QUES:COND?",
)


def ask(cmds: tuple[str, ...], tag: str) -> dict:
    """新开会话 → 顺序只读查询 → 关闭。不写任何命令。"""
    out: dict = {"tag": tag, "queries": {}}
    try:
        c = VisaClient(RESOURCE, timeout_ms=1500, open_timeout_ms=3000)
    except Exception as e:
        out["connect_error"] = f"{type(e).__name__}: {e}"
        return out
    try:
        for cmd in cmds:
            try:
                out["queries"][cmd] = repr(c.query(cmd))
            except Exception as e:
                out["queries"][cmd] = f"<{type(e).__name__}>"
                break  # 本条不响应 → 后续可能错位，立即结束该会话
    finally:
        try:
            c.close()
        except Exception:
            pass
    return out


def local_restore_probe() -> dict:
    """单独验证 SYST:LOC 能否把 REM 拉回 LOC（唯一写命令，仅面板控制权，不碰输出）。

    手册 4.2：SYST:LOC 本地模式（面板可操作）/ SYST:REM 远程 / SYST:RWL 远程锁定。
    本函数**不发送** SYST:REM/SYST:RWL，也不触碰电压/电流/输出开关。
    """
    out: dict = {"tag": "local_restore", "queries": {}}
    try:
        c = VisaClient(RESOURCE, timeout_ms=2000, open_timeout_ms=3000)
    except Exception as e:
        out["connect_error"] = f"{type(e).__name__}: {e}"
        return out
    try:
        out["queries"]["SYST:COMM:RLST? (连接后)"] = repr(c.query("SYST:COMM:RLST?"))
        c.write("SYST:LOC")            # 恢复本地：面板可操作（不改变任何输出/设定）
        time.sleep(0.3)
        out["queries"]["wrote"] = "SYST:LOC"
        out["queries"]["SYST:COMM:RLST? (写 LOC 后)"] = repr(c.query("SYST:COMM:RLST?"))
        out["queries"]["APPL:OUTP? (输出状态复核)"] = repr(c.query("APPL:OUTP?"))
        out["queries"]["SYST:ERR?"] = repr(c.query("SYST:ERR?"))
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            c.close()
        except Exception:
            pass
    return out


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    record: dict = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "purpose": "核实 DH1766 是否存在“远程连接即锁定”（只读探测，零写入）",
        "resource": RESOURCE,
        "firmware_note": (
            "正确查询为 SYST:COMM:RLST?（返回 LOC/REM/RWL）；手册写的 "
            "SYST:COMM:RLST:STAT? 在本机 V0.1.4.3 **无响应（超时）**——"
            "注意不是“返回空串”（2026-09-13 更正）"
        ),
        "probes": [],
    }

    print("== 基线：新会话 + 已知只读查询 ==")
    base = ask(BASELINE_QUERIES, "baseline")
    record["probes"].append(base)
    for k, v in base["queries"].items():
        print(f"  {k:26s} -> {v}")
    if base.get("connect_error"):
        print(f"!! 连接失败: {base['connect_error']}")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"psu_lock_probe_{stamp}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    print("\n== 候选状态查询：每条各起一个新会话（每次都是“刚连接”状态） ==")
    results = {}
    for cmd in STATE_QUERIES:
        r = ask((cmd,), f"state:{cmd}")
        results[cmd] = r["queries"].get(cmd, r.get("connect_error", "<no response>"))
        record["probes"].append(r)
        print(f"  {cmd:26s} -> {results[cmd]}")

    readable = {k: v for k, v in results.items() if v not in ("''", "<VisaIOError>")
                and not v.startswith("<")}
    record["state_readable"] = readable

    print("\n== 会话内复测：连接后先做普通查询，再查状态（活动是否改变模式） ==")
    again = ask(("*IDN?", "SYST:COMM:RLST?"), "baseline_then_state")
    record["probes"].append(again)
    for k, v in again["queries"].items():
        print(f"  {k:26s} -> {v}")

    if "--with-local-restore" in sys.argv:
        print("\n== 恢复测试：连接后查状态 → 写 SYST:LOC → 复查（仅面板控制权） ==")
        lr = local_restore_probe()
        record["probes"].append(lr)
        for k, v in lr["queries"].items():
            print(f"  {k:34s} -> {v}")
        if lr.get("error"):
            print(f"  !! {lr['error']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / f"psu_lock_probe_{stamp}.json"
    f.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 可读状态查询: {readable or '（全部空串/无响应——固件不提供该观测）'}")
    print(f"留痕: {f}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
