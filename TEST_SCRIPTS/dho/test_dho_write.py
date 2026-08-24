"""DHO 写操作闭环验证：通道/时基/触发 备份→改→回读→恢复（不碰复位/输出）。"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dho_control import DHO, find_dho  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dho"
results = []


def rec(name, ok, detail=""):
    results.append({"item": name, "ok": ok, "detail": str(detail)[:200]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    resource = find_dho(hosts=["192.168.31.146"])
    with DHO(resource) as s:
        # ---- 备份 ----
        bk = {
            "ch2_scale": s.channel_scale(2),
            "ch2_offset": s.channel_offset(2),
            "ch2_coup": s.channel_coupling(2),
            "ch2_disp": s.channel_display(2),
            "tb": s.timebase_scale(),
            "edge_lev": s.edge_level(),
            "acq_type": s.acquire_type(),
        }
        rec("备份", True, json.dumps(bk, default=str))

        # ---- 通道垂直 ----
        s.channel_scale(2, 0.1)
        time.sleep(0.3)
        got = s.channel_scale(2)
        rec("CH2 SCALe 写 0.1", abs((got or 0) - 0.1) < 1e-9, f"回读 {got}")

        s.channel_coupling(2, "AC")
        time.sleep(0.3)
        rec("CH2 COUPling AC", s.channel_coupling(2) == "AC", s.channel_coupling(2))

        # ---- 时基 ----
        s.timebase_scale(1e-4)
        time.sleep(0.3)
        got_tb = s.timebase_scale()
        rec("TIMebase SCALe 写 100us", abs((got_tb or 0) - 1e-4) < 1e-12, f"回读 {got_tb}")

        # ---- 触发电平 ----
        s.edge_level(0.5)
        time.sleep(0.3)
        got_lv = s.edge_level()
        rec("EDGE LEVel 写 0.5", abs((got_lv or 0) - 0.5) < 1e-6, f"回读 {got_lv}")

        # ---- 采集类型 ----
        s.acquire_type("HRESolution")
        time.sleep(0.3)
        rec("ACQuire TYPE HRES", (s.acquire_type() or "").startswith("HRES"), s.acquire_type())

        # ---- 恢复 ----
        s.channel_scale(2, bk["ch2_scale"])
        s.channel_offset(2, bk["ch2_offset"])
        s.channel_coupling(2, bk["ch2_coup"])
        if bk["ch2_disp"] is False:
            s.channel_display(2, False)
        s.timebase_scale(bk["tb"])
        s.edge_level(bk["edge_lev"])
        if bk["acq_type"]:
            s.acquire_type(bk["acq_type"])
        time.sleep(0.5)

        ok = (
            abs((s.channel_scale(2) or 0) - (bk["ch2_scale"] or 0)) < 1e-9
            and s.channel_coupling(2) == bk["ch2_coup"]
            and abs((s.timebase_scale() or 0) - (bk["tb"] or 0)) < 1e-12
            and abs((s.edge_level() or 0) - (bk["edge_lev"] or 0)) < 1e-6
        )
        rec("恢复比对", ok)
        print("错误队列终态:", s.system_error() or "干净")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT_DIR / f"dho_write_verify_{stamp}.json"
    f.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_fail = sum(1 for r in results if not r["ok"])
    print(f"== 结果: {len(results) - n_fail}/{len(results)} PASS ==\n留痕: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
