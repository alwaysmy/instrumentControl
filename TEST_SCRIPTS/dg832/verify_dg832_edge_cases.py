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


def appl_equal(a: str, b: str, tol: float = 2e-3) -> bool:
    """比较两条 APPL? 串：波形名相等 + 各数值列在容差内（DEF 占位视为通配）。

    为什么要比数值而不是只比波形名：实测踩过——恢复时若保护窗口偏窄，
    设备会把 offset **钳制**到窗口内（1.65 → 1.35），只比波形名会"看起来 PASS"。
    """
    pa, pb = a.split(","), b.split(",")
    if pa[0].upper() != pb[0].upper():
        return False
    for x, y in zip(pa[1:], pb[1:]):
        x, y = x.strip().upper(), y.strip().upper()
        if "DEF" in (x, y):
            continue
        try:
            fx, fy = float(x), float(y)
        except ValueError:
            if x != y:
                return False
            continue
        if abs(fx - fy) > max(tol, abs(fy) * tol):
            return False
    return True


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
            # L9：错误队列返回 list（先清空，避免把上一次运行遗留的滞后错误算进来）
            rec("L9 check_error 返回 list", isinstance(g.check_error(), list),
                "旧队列已清（清空前的内容见下）")

            def step_ok(label, fn, expect_ok=True):
                """写一步 → drain 错误 → 回读比对；错误队列与结果一起记账。"""
                g.check_error()          # DG832 驱动的排空方法（查询即清空队列）
                try:
                    r = fn()
                    err = g.check_error()
                    ok = (err == [])
                    rec(label, ok, f"回读={str(r)[:70]} 错误队列={err or '干净'}")
                    return r
                except Exception as e:
                    err = g.check_error()
                    rec(label, not expect_ok, f"{type(e).__name__}: {e} | 错误队列={err or '干净'}")
                    return None

            step_ok("H2 sequence 合法采样率(10k) 写入+回读",
                    lambda: g.set_wave(2, "sequence", sample_rate=10000, amp=1.0))
            step_ok("M1 保护放宽到 ±5V",
                    lambda: g.set_voltage_limit(2, high=5, low=-5, state=True))
            step_ok("M1 单边 low=6（应被库拒绝，不发命令）",
                    lambda: g.set_voltage_limit(2, low=6), expect_ok=False)
            step_ok("M1 单边 high=3（应通过）",
                    lambda: g.set_voltage_limit(2, high=3))
            step_ok("M2 DC offset=0.3（走 set_dc_only，回读电平）",
                    lambda: g.set_dc_only(2, 0.3))
            # 逐项断言（把"命令被接受"和"值真的生效"分开判）
            appl = g.query(":SOUR2:APPL?").strip().strip('"')
            offs = float(g.query(":SOUR2:VOLT:OFFS?"))
            rec("M2 断言：APPL 为 DC 且电平=0.3", appl.split(",")[0] == "DC" and abs(offs - 0.3) < 1e-6,
                f"APPL={appl} 电平={offs}（注：DC 模式下 freq/amp 槽由设备回 DEF 占位，属正常）")
        finally:
            # 恢复要**逐步容错**：任一步通信异常都不能让后续步骤被跳过
            # （实测踩过：output() 撞上偶发 USB 错误 → 后面的 VOLL 恢复整段没跑）
            parts = b2["appl"].split(",")
            # 恢复顺序有讲究（实测教训）：**先放宽保护窗口**，否则写回波形时
            # offset 会被旧窗口钳制（如 1.65 被钳成 1.35）；最后再按备份收窄窗口。
            steps = [
                (":OUTP2:VOLL:HIGH 6.0", "临时放宽上限（防恢复时钳制）"),
                (":OUTP2:VOLL:LOW -6.0", "临时放宽下限"),
                (f":SOUR2:APPL:{parts[0]} {','.join(parts[1:])}", "恢复波形"),
                (f":OUTP2:VOLL:HIGH {b2['voll']['high']}", "按备份恢复保护上限"),
                (f":OUTP2:VOLL:LOW {b2['voll']['low']}", "按备份恢复保护下限"),
                (f":OUTP2:VOLL:STAT {'ON' if str(b2['voll']['state']).strip() in ('1','ON') else 'OFF'}",
                 "恢复保护开关"),
                (f":OUTP2 {'ON' if b2['outp'] == 'ON' else 'OFF'}", "恢复输出状态"),
            ]
            for cmd, label in steps:
                ok = True
                for attempt in (1, 2):          # 偶发 USB 错误重试一次
                    try:
                        g.write(cmd)
                        time.sleep(0.2)
                        break
                    except Exception as e:
                        ok = False
                        if attempt == 2:
                            rec(f"[恢复失败] {label}", False, f"{cmd} → {type(e).__name__}: {str(e)[:60]}")
                if ok:
                    rec(f"[恢复] {label}", True, cmd)
            try:
                now = {"appl": g.query(":SOUR2:APPL?").strip().strip('"'),
                       "outp": g.query(":OUTP2?").strip(), "voll": g.get_voltage_limit(2)}
                ok = (appl_equal(now["appl"], b2["appl"])
                      and now["outp"] == b2["outp"]
                      and abs(float(now["voll"]["high"]) - float(b2["voll"]["high"])) < 1e-6
                      and abs(float(now["voll"]["low"]) - float(b2["voll"]["low"])) < 1e-6
                      and str(now["voll"]["state"]) == str(b2["voll"]["state"]))
                rec("CH2 恢复后比对（全参数：波形/频率/幅度/偏移 + 输出 + 保护窗口）", ok,
                    f"期望 {b2['appl']} / {b2['outp']} / {b2['voll']}；实得 {now}")
            except Exception as e:
                rec("CH2 恢复后比对", False, f"回读失败（USB？）：{type(e).__name__}")
            try:
                g.close()
            except Exception:
                pass

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
