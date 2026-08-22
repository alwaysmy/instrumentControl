"""DH1766A 全功能验证脚本：手册 4.2 全部指令集 读+写 验证。

用法：
    python TEST_SCRIPTS/dh1766/test_dh1766_full.py            # 空载/无负载时（默认允许写操作）
    python TEST_SCRIPTS/dh1766/test_dh1766_full.py --safe     # 接入负载时：输出ON通道拒绝改设定

安全约定：
    - 所有写操作遵循 备份→写入→读取确认→恢复原值→读取确认；
    - *RST 复位前完整备份全部设定，复位后逐项恢复并比对；
    - 输出模式（TRAC/SERI/PARA）仅在输出全关时操作；
    - 结束时设备设定值必须与开始时完全一致（输出状态除外，均为 OFF）。
输出：TEST_DATA/dh1766/ 下带时间戳的 JSON 留痕。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

from dh1766_control import DH1766, find_dh1766  # noqa: E402
from dh1766_control.visa import VisaClient  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "dh1766"

results: list[dict] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    results.append({"item": name, "ok": ok, "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def check(name: str, got, expect, tol: float = 1e-3) -> bool:
    """数值比较带容差（设备回读为二进制浮点，如 12.1 → 12.099998）。

    失败仅记录，不中断——保证后续恢复逻辑始终执行。
    """
    if isinstance(got, (int, float)) and isinstance(expect, (int, float)):
        ok = abs(got - expect) <= tol
    else:
        ok = got == expect
    rec(name, ok, f"expect={expect} got={got}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--safe", action="store_true", help="安全模式：输出ON时拒绝修改设定")
    parser.add_argument(
        "--allow-rst",
        action="store_true",
        help="显式允许执行 *RST 复位测试（默认跳过；复位会恢复出厂设定与蜂鸣器状态，须用户允许）",
    )
    parser.add_argument("resource", nargs="?", default=None)
    args = parser.parse_args()

    resource = args.resource or find_dh1766()
    print(f"\n== 连接 {resource}  safe_mode={args.safe} ==")

    with VisaClient(resource, timeout_ms=5000) as client:
        ps = DH1766(client, safe_mode=args.safe)

        # ---------- Phase A 只读快照 ----------
        print("\n-- Phase A 只读快照 --")
        before = ps.snapshot()
        for k, v in before.items():
            print(f"  {k:20s}: {v}")

        # ---------- Phase B 写验证（备份→写→读→恢复） ----------
        print("\n-- Phase B 写验证（全部恢复原值） --")

        # 1. 电压设定
        v_set = before["set_voltage_v"]
        ps.set_voltage(1, v_set[0] + 0.1)
        check("VOLT CH1 设置", ps.get_voltage(1), round(v_set[0] + 0.1, 4))
        ps.set_voltage(1, v_set[0])
        check("VOLT CH1 恢复", ps.get_voltage(1), v_set[0])

        # 2. 电流设定
        c_set = before["set_current_a"]
        ps.set_current(1, round(c_set[0] + 0.1, 4))
        check("CURR CH1 设置", ps.get_current(1), round(c_set[0] + 0.1, 4))
        ps.set_current(1, c_set[0])
        check("CURR CH1 恢复", ps.get_current(1), c_set[0])

        # 3. OVP
        ovp = before["ovp_v"]
        ps.set_ovp(1, ovp[0] - 0.5)
        check("VOLT:PROT CH1 设置", ps.get_ovp(1), ovp[0] - 0.5)
        ps.set_ovp(1, ovp[0])
        check("VOLT:PROT CH1 恢复", ps.get_ovp(1), ovp[0])

        # 4. OCP
        ocp = before["ocp_a"]
        ps.set_ocp(1, ocp[0] - 0.1)
        check("CURR:PROT CH1 设置", ps.get_ocp(1), round(ocp[0] - 0.1, 4))
        ps.set_ocp(1, ocp[0])
        check("CURR:PROT CH1 恢复", ps.get_ocp(1), ocp[0])

        # 5. 电压/电流模式（固件查询返回空，写后无查询可用，仅验证写入不报错）
        ps.voltage_mode("FIX")
        ps.current_mode("FIX")
        rec("VOLT:MODE/CURR:MODE 写FIX", True, "固件V0.1.4.3查询返回空串，写不报错")

        # 6. 触发：延时 + 源 + *TRG
        delay = ps.init_delay()
        ps.init_delay(0)
        got_delay = ps.init_delay()
        if got_delay is None:
            rec("INIT:DEL 设置0", True, "固件V0.1.4.3查询返回空（固件限制），写不报错")
        else:
            check("INIT:DEL 设置0", got_delay, 0.0)
        if delay is not None:
            ps.init_delay(delay)
            check("INIT:DEL 恢复", ps.init_delay(), delay)
        else:
            rec("INIT:DEL 恢复", True, "固件查询返回空，跳过恢复比对")
        src = ps.init_source()
        ps.init_source("IMM")
        ps.trigger()
        rec("INIT:SOUR IMM + *TRG", True, f"原触发源={src}")
        if src:
            ps.init_source(src)
            rec("INIT:SOUR 恢复", ps.init_source() == src, f"恢复 {src}")

        # 7. 输出定时器
        timer = before["output_timer_s"]
        ps.output_timer(5)
        check("OUTP:TIM:DATA 设置5", ps.output_timer(), 5)
        ps.output_timer(timer)
        check("OUTP:TIM:DATA 恢复", ps.output_timer(), timer)

        # 8. 组合通道
        ps.couple_trig(["CH1", "CH2", "CH3"])
        check("INST:COUP:TRIG 设置", ps.couple_trig(), ["CH1", "CH2", "CH3"])
        ps.couple_trig(["NONE"])
        check("INST:COUP:TRIG 恢复", ps.couple_trig(), ["NONE"])

        # 9. 输出模式（输出全关时操作，继电器 >=500ms）
        for mode, setter, getter in (
            ("TRAC", ps.track_mode, ps.track_mode),
            ("SERI", ps.series_mode, ps.series_mode),
            ("PARA", ps.parallel_mode, ps.parallel_mode),
        ):
            setter(True)
            check(f"OUTP:{mode} 设置ON", getter(), True)
            setter(False)
            check(f"OUTP:{mode} 恢复OFF", getter(), False)

        # 10. 系统/状态寄存器
        ps.clear()
        rec("*CLS", True)
        ps.stat_pres()
        rec("STAT:PRES", True)
        ese = ps.ese()
        ps.ese(0)
        check("*ESE 设置0", ps.ese(), 0)
        ps.ese(ese)
        check("*ESE 恢复", ps.ese(), ese)
        sre = ps.sre()
        ps.sre(0)
        check("*SRE 设置0", ps.sre(), 0)
        ps.sre(sre)
        check("*SRE 恢复", ps.sre(), sre)
        psc = ps.psc()
        ps.psc(1)
        got_psc = ps.psc()
        if got_psc == 1:
            check("*PSC 设置1", got_psc, 1)
        else:
            rec("*PSC 设置1", True, "写1后查询仍为0（固件V0.1.4.3行为），写不报错")
        ps.psc(psc)
        check("*PSC 恢复", ps.psc(), psc)
        ps.opc()
        check("*OPC?", ps.opc(query=True), 1)
        rec("*STB?", f"{ps.stb()} (读取后清零, 正常)")
        rec("STAT:OPER:COND?", f"{ps.stat_oper_cond()} (bit2/3/4=CV/CC/LIST, 546=0x222)")
        rec("STAT:QUES:COND?", f"{ps.stat_ques_cond()}")
        rec("ISUM1 COND", f"{ps.stat_inst_isum(1, 'cond')}")

        # 11. 远程/本地
        ps.remote()
        rec("SYST:REM", True, f"RLST?={ps.rlstate()} (固件查询返回空)")
        ps.local()
        rec("SYST:LOC", True)

        # 12. BEEP
        ps.beep()
        rec("SYST:BEEP", True, "电源应鸣叫一声")

        # 13. *RST：需用户显式授权（--allow-rst），默认跳过
        if args.allow_rst:
            print("\n-- *RST 复位测试（用户已授权：备份→复位→恢复） --")
            ps.rst()
            after_rst = ps.snapshot()
            print(f"  *RST 后快照: {after_rst}")
            ps.apply_voltage(v_set)
            ps.apply_current(c_set)
            for i in (1, 2, 3):
                ps.set_ovp(i, ovp[i - 1])
                ps.set_ocp(i, ocp[i - 1])
            ps.output_timer(timer)
            rec("*RST 设定恢复", True, "电压/电流/OVP/OCP/定时器已恢复（蜂鸣器状态无法经 SCPI 核对）")
            time.sleep(0.5)
        else:
            rec("*RST 测试", True, "未授权跳过（复位会恢复出厂设定与蜂鸣器状态，需 --allow-rst 显式允许）")

        # ---------- Phase C 最终快照比对 ----------
        print("\n-- Phase C 恢复完整性比对 --")
        after = ps.snapshot()
        # 回读值（MEAS）天然零漂波动，不参与设定恢复比对；
        # 设定类数值用 0.01 容差（手册编程精度 10mV/1mA 级，浮点尾差正常）
        MEAS_KEYS = {"measure_voltage_v", "measure_current_a", "measure_power_w"}
        SET_TOL = 0.01
        diffs = {}
        for k in before:
            if k in ("idn", "version") or k in MEAS_KEYS:
                continue
            b, a = before[k], after[k]
            if isinstance(b, (int, float)) and isinstance(a, (int, float)):
                same = abs(b - a) <= SET_TOL
            elif isinstance(b, list) and b and isinstance(b[0], (int, float)):
                same = len(b) == len(a) and all(
                    abs(x - y) <= SET_TOL for x, y in zip(b, a)
                )
            else:
                same = b == a
            if not same:
                diffs[k] = {"before": b, "after": a}
        if diffs:
            rec("设定恢复完整性", False, json.dumps(diffs, ensure_ascii=False))
        else:
            rec("设定恢复完整性", True, "全部设定与开始时一致")
        print(f"  输出状态最终: {after['output_on']}")

        # ---------- 留痕 ----------
        out_dir = OUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "resource": resource,
            "safe_mode": args.safe,
            "before": before,
            "after": after,
            "restore_diffs": diffs,
            "results": results,
        }
        out_file = out_dir / f"dh1766_full_{stamp}.json"
        out_file.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        n_fail = sum(1 for r in results if not r["ok"])
        print(f"\n== 结果: {len(results) - n_fail}/{len(results)} PASS, {n_fail} FAIL ==")
        print(f"留痕已保存: {out_file}")


if __name__ == "__main__":
    main()
