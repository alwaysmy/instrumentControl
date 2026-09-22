"""ks3458a MCP 工具真机验收（只读 + 同值 configure；不跑 burst/acv/reset）。

覆盖：ks3458a_status / read / read_avg / read_stats / configure(同值) / reset 门。
留痕：TEST_DATA/ks3458a/verify_mcp_ks3458a_live_<stamp>.json
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

import server  # noqa: E402

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="ascii", errors="replace")
    except Exception:
        pass

rows: list[dict] = []


def run(tool: str, fn, expect_ok: bool = True, note: str = "") -> dict:
    raw = fn()
    try:
        d = json.loads(raw)
    except Exception as e:
        d = {"ok": False, "error": f"bad json: {e}"}
    ok = bool(d.get("ok")) == expect_ok
    detail = d.get("result") if d.get("ok") else d.get("error")
    print(f"  [{'PASS' if ok else 'FAIL'}] {tool:34s} {str(detail)[:96]}", flush=True)
    rows.append({"tool": tool, "ok": ok, "expected_ok": expect_ok, "note": note,
                 "result": detail if isinstance(detail, (dict, list, str, int, float, type(None))) else str(detail)})
    return d


def main() -> int:
    run("ks3458a_status", server.ks3458a_status)
    run("ks3458a_read", server.ks3458a_read)
    run("ks3458a_read_avg(n=3)", lambda: server.ks3458a_read_avg(n=3))
    run("ks3458a_read_stats(n=3)", lambda: server.ks3458a_read_stats(n=3))
    run("ks3458a_configure(0.1,10) 同值", lambda: server.ks3458a_configure(dcv_range=0.1, nplc=10))
    run("ks3458a_read (configure 后)", server.ks3458a_read)
    run("ks3458a_reset 无 confirm -> 拒绝", server.ks3458a_reset, expect_ok=False)
    run("ks3458a_read_avg n=0 -> 参数校验", lambda: server.ks3458a_read_avg(n=0), expect_ok=False)

    out_dir = ROOT / "TEST_DATA" / "ks3458a"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = out_dir / f"verify_mcp_ks3458a_live_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    f.write_text(json.dumps({
        "when": datetime.now().isoformat(timespec="seconds"),
        "note": "live: status/read/read_avg/read_stats/configure(同值) + reset 门；未跑 burst/acv/reset",
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== result: {len(rows) - n_fail}/{len(rows)} PASS ==\nevidence: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
