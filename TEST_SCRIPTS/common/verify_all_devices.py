"""五台设备 MCP 全链路**只读**验收（真机）：发现 → 地址解析 → 身份校验 → 快照/测量。

覆盖：
  ① instr_discover：LAN + VISA 发现，检查是否 5 台齐全、缓存回写、DH1766 面板归还；
  ② 各设备专用工具（只读类）：sds_status/sdg_status/dmm_status/dho_status/psu_status；
  ③ 只读附加探针：sds_diagnose、sds_get_waveform（摘要）、sds_screenshot（存 PNG）、
     dmm_measure(volt_dc)、dmm_nplc（查询）、sdg_counter（查询）、dho_measure_item(VPP)；
  ④ 解析层：resolve() 来源（config/cache/discovery）、返回体 resource 回填。

**安全**：不调用任何状态变更命令——不开关输出、不改模式/档位/触发、不复位、不关机；
电源仅在 psu_status 收尾由 server 自动补 SYST:LOC（归还面板，不动输出）。
留痕：TEST_DATA/common/verify_all_devices_<stamp>.json
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

import server  # noqa: E402
from common.resolver import explain  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"
rows: list[dict] = []


def rec(name: str, r: str, note: str = "", ok: bool | None = None) -> dict:
    """记录一步结果（r 为工具返回的 JSON 字符串）。"""
    try:
        d = json.loads(r)
    except Exception as e:
        d = {"ok": False, "error": f"非法 JSON: {e}"}
    if ok is None:
        ok = bool(d.get("ok"))
    label = "PASS" if ok else "FAIL"
    res = d.get("resource")
    err = d.get("error") or d.get("result") or ""
    if isinstance(err, dict):
        err = json.dumps(err, ensure_ascii=False)[:120]
    print(f"  [{label}] {name:22s} {note} {str(err)[:110]}", flush=True)
    row = {"step": name, "ok": bool(ok), "note": note, "resource": res,
           "error_type": d.get("error_type"), "detail": str(err)[:300]}
    rows.append(row)
    return d


def main() -> int:
    print("=== ① 发现（LAN 扫描 + VISA；可能 10-60s）===", flush=True)
    t0 = time.monotonic()
    dis = rec("instr_discover", server.instr_discover())
    took = time.monotonic() - t0
    if dis.get("ok"):
        r = dis["result"]
        print(f"      耗时 {took:.1f}s | cidr={r.get('cidr')} lan={len(r.get('lan', {}))} "
              f"visa={len(r.get('visa', []))}", flush=True)
        print(f"      resolved={json.dumps(r.get('resolved', {}), ensure_ascii=False)}", flush=True)
        print(f"      recognised_now={json.dumps(r.get('recognised_now', {}), ensure_ascii=False)}", flush=True)
        print(f"      psu_local_restored={r.get('psu_local_restored')} "
              f"warning={str(r.get('warning'))[:80]}", flush=True)
        rows[-1]["elapsed_s"] = round(took, 1)
        rows[-1]["recognised_now"] = r.get("recognised_now")
        rows[-1]["resolved"] = r.get("resolved")

    print("\n=== ② 地址解析来源（config/cache/…）===", flush=True)
    for kind in ("sds", "sdg", "dmm", "dho", "psu"):
        e = explain(kind)
        print(f"  {kind:4s} {str(e['source']):8s} {e['resource']}", flush=True)
        rows.append({"step": f"resolve:{kind}", "ok": bool(e["resource"]),
                     "note": e["source"], "resource": e["resource"]})

    print("\n=== ③ 各设备只读快照 ===", flush=True)
    for name, fn in (("sds_status", server.sds_status), ("sdg_status", server.sdg_status),
                     ("dmm_status", server.dmm_status), ("dho_status", server.dho_status),
                     ("psu_status", server.psu_status)):
        rec(name, fn())

    print("\n=== ④ 只读附加探针 ===", flush=True)
    rec("sds_diagnose", server.sds_diagnose())
    rec("sds_get_waveform", server.sds_get_waveform(ch=1, points=2000))
    rec("sds_screenshot", server.sds_screenshot())
    rec("dmm_measure(volt_dc)", server.dmm_measure("volt_dc"))
    rec("dmm_nplc(query)", server.dmm_nplc())
    rec("sdg_counter(query)", server.sdg_counter())
    rec("dho_measure_item", server.dho_measure_item("VPP", 1))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / f"verify_all_devices_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    f.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"),
                             "mode": "只读验收（无任何状态变更命令）",
                             "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 结果: {len(rows) - n_fail}/{len(rows)} PASS ==\n留痕: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
