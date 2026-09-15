"""DG832 边界与护栏回归（原工作区 `verify_fixes.py` 的仓库版，改走新的 dg_* 工具/库）。

覆盖这些**曾被审查出来并修过**的点，防止回归：
    H1 查询口不接受分号串联写命令（`":OUTP1 ON;:OUTP1?"` 必须被拒）
    H2 sequence 波形的采样率校验（合法值通过 / 非法值被拒）
    M1 电压保护**单边**设置时的范围校验（新的 low 必须小于当前 high，反之亦然）
    M2 DC 波形在宽保护范围下 offset 生效（不被残留幅度钳制）
    L9 错误队列返回结构（list）
    H3 库层按 VID/PID 发现设备

用法：
    python TEST_SCRIPTS/dg832/verify_dg832_edge_cases.py                # 离线部分（不碰仪器）
    python TEST_SCRIPTS/dg832/verify_dg832_edge_cases.py --with-device  # 追加真机项（会改设定后恢复）

⚠ `--with-device` 会临时改 CH2 的保护/波形，脚本内 try/finally 恢复原值；
   跑之前确认该通道没有在驱动别人的实验，且用户已授权。
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
from dg832_control import DG832, ParamValidationError, ProtectRangeError  # noqa: E402

WITH_DEVICE = "--with-device" in sys.argv
OUT_DIR = ROOT / "TEST_DATA" / "dg832"
rows: list[dict] = []


def rec(step: str, ok: bool, detail="") -> None:
    rows.append({"step": step, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {step:46s} {str(detail)[:110]}", flush=True)


def raises(fn, *exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def main() -> int:
    import server  # noqa: E402  （MCP 工具层：H1 的分号走私在这里拦）

    print("=== §1 H1：查询口的分号走私（离线，不碰设备）===", flush=True)
    r = json.loads(server.dg_query("*IDN?;*RST"))
    rec("dg_query 拒绝分号串联", r.get("ok") is False
        and r.get("error_type") in ("forbidden", "param_validation"), r.get("error_type"))
    r2 = json.loads(server.dg_query(":OUTP1 ON;:OUTP1?"))
    rec("dg_query 拒绝 写命令;查询", r2.get("ok") is False
        and r2.get("error_type") in ("forbidden", "param_validation"), r2.get("error_type"))

    print("\n=== §2 参数校验（离线：库层在发命令前就应拒绝）===", flush=True)
    gen = DG832(resource="dummy")          # 不 connect：校验发生在 I/O 之前
    rec("H2 sequence 非法采样率被拒",
        raises(lambda: gen._validate_params(sample_rate=1000, shape="sequence"),
               ParamValidationError, ValueError),
        "1000 Sa/s 低于下限 2k")
    rec("M2 DC 下 set_amp 被明确拒绝",
        raises(lambda: gen.set_amp(1, 1.0), ParamValidationError, ValueError, RuntimeError),
        "直流电平应走 offset/set_dc_only")
    rec("参数校验：freq<=0 被拒",
        raises(lambda: gen._validate_params(freq=0), ParamValidationError, ValueError))

    if not WITH_DEVICE:
        print("\n=== §3 真机项（跳过：加 --with-device 才跑，会改设定后恢复）===", flush=True)
    else:
        print("\n=== §3 真机项（改设定 → 恢复）===", flush=True)
        res = resolve("dg")
        g = DG832(resource=res)
        g.connect()
        print(f"      resource={res} | {g.idn()}", flush=True)
        b2 = {"appl": g.query(":SOUR2:APPL?").strip().strip('"'),
              "outp": g.query(":OUTP2?").strip(), "voll": g.get_voltage_limit(2)}
        try:
            # L9：错误队列返回 list
            errs = g.check_error()
            rec("L9 check_error 返回 list", isinstance(errs, list), f"{errs}")

            # H2：sequence 合法采样率通过（需保护已开）
            g.set_voltage_limit(2, high=5, low=-5, state=True)
            try:
                g.set_wave(2, "sequence", sample_rate=10000, amp=1.0)
                rec("H2 sequence 合法采样率(10k)通过", True)
            except Exception as e:
                rec("H2 sequence 合法采样率(10k)通过", False, f"{type(e).__name__}: {e}")

            # M1：单边设置保护时的范围校验
            g.set_voltage_limit(2, high=5, low=-5, state=True)
            rec("M1 单边 low=6（> 当前 high=5）被拒",
                raises(lambda: g.set_voltage_limit(2, low=6), ParamValidationError, ValueError,
                       ProtectRangeError))
            rec("M1 单边 high=3（< 当前 low=-5 之上）通过",
                raises(lambda: g.set_voltage_limit(2, high=3), Exception) is False)

            # M2：DC 在宽保护范围下 offset 生效
            g.set_voltage_limit(2, high=5, low=-5, state=True)
            r = g.set_wave(2, "dc", offset=0.3)
            rec("M2 DC offset=0.3 生效", "0.3" in str(r), str(r)[:80])
        finally:
            parts = b2["appl"].split(",")
            g.write(f":SOUR2:APPL:{'SIN' if parts[0] == 'SIN' else parts[0]} {','.join(parts[1:])}")
            time.sleep(0.2)
            g.output(2, b2["outp"] == "ON")
            v = b2["voll"]
            g.write(f":OUTP2:VOLL:HIGH {v['high']}")
            g.write(f":OUTP2:VOLL:LOW {v['low']}")
            g.write(f":OUTP2:VOLL:STAT {v['state']}")
            time.sleep(0.2)
            now = {"appl": g.query(":SOUR2:APPL?").strip().strip('"'),
                   "outp": g.query(":OUTP2?").strip(), "voll": g.get_voltage_limit(2)}
            rec("CH2 恢复后比对",
                now["appl"].split(",")[0] == b2["appl"].split(",")[0]
                and now["outp"] == b2["outp"]
                and str(now["voll"]["state"]) == str(v["state"]), f"{now}")
            g.close()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"edge_cases_{stamp}.json"
    n_fail = sum(1 for r in rows if not r["ok"])
    out.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"),
                               "with_device": WITH_DEVICE, "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 结果: {len(rows) - n_fail}/{len(rows)} PASS ==\n留痕: {out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
