"""真机判定：仪器是否接受 `;` 串联的多命令消息，以及"查询消息里夹带写命令"是否真会执行。

背景：护栏里有一条"查询口只收纯查询消息"的判据，用户质疑"不存在把命令塞进查询的情况"
（认为 SCPI 靠换行符划分命令）。规范层已确认 `;` 分隔的是**同一条消息内的多个命令单元**，
本脚本用 DG832（当前无人使用）做行为判定：

    A. 纯查询串联：`:SOUR1:APPL?;:SOUR2:APPL?`       → 设备是否两个都答？
    B. 查询 + 写：`:SOUR1:PHAS?;:SOUR1:PHAS 123`     → 写单元是否真的生效？（改后立即恢复）
    C. 串联被拒/无响应时的错误队列                                  → 设备怎么报

安全：只改 CH1 相位（当前输出 OFF，无物理影响），逐项 try/finally 恢复 + 校验。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve  # noqa: E402
from dg832_control import DG832  # noqa: E402


def main() -> int:
    g = DG832(resource=resolve("dg"))
    g.connect()
    print("IDN:", g.idn())
    phas0 = g.query(":SOUR1:PHAS?").strip()
    print(f"【备份】CH1 PHAS = {phas0}；错误队列（先清）: {g.check_error() or '空'}")
    try:
        # ---- A. 纯查询串联：设备是否把两个单元都当命令处理 ----
        print("\n=== A. 纯查询串联 `:SOUR1:APPL?;:SOUR2:APPL?` ===")
        out1, out2 = None, None
        try:
            out1 = g.query(":SOUR1:APPL?;:SOUR2:APPL?").strip()
            print(f"  第一行应答: {out1!r}")
        except Exception as e:
            print(f"  发送/读取异常: {type(e).__name__}: {str(e)[:80]}")
        # 若设备为第二个单元也排队了应答，再读一行就能看到
        try:
            out2 = g.instr.read().strip()
            print(f"  第二行应答: {out2!r}   ← 说明两个单元都被当作命令执行")
        except Exception as e:
            print(f"  无第二行应答（{type(e).__name__}）→ 该机可能只解析首单元或只答一次")
        print(f"  错误队列: {g.check_error() or '空'}")

        # ---- B. 查询 + 写：写单元是否真的生效 ----
        print("\n=== B. 查询夹带写 `:SOUR1:PHAS?;:SOUR1:PHAS 123` ===")
        try:
            r = g.query(":SOUR1:PHAS?;:SOUR1:PHAS 123").strip()
            print(f"  查询应答: {r!r}")
        except Exception as e:
            print(f"  异常: {type(e).__name__}: {str(e)[:80]}")
        time.sleep(0.4)
        now = g.query(":SOUR1:PHAS?").strip()
        wrote = abs(float(now) - 123.0) < 1e-3
        print(f"  写单元是否生效: {wrote}（PHAS 现为 {now}，原为 {phas0}）")
        print(f"  错误队列: {g.check_error() or '空'}")
        print("\n结论:", "**夹带的写命令确实被执行了**（走私通道真实存在）" if wrote
              else "该机忽略了后续写单元（走私不成立，或需其它写法）")
    finally:
        g.write(f":SOUR1:PHAS {phas0}")
        time.sleep(0.3)
        back = g.query(":SOUR1:PHAS?").strip()
        print(f"\n【恢复】CH1 PHAS -> {back}（期望 {phas0}）；错误队列: {g.check_error() or '空'}")
        print(f"CH1/CH2 现状: {g.query(':SOUR1:APPL?')} | {g.query(':SOUR2:APPL?')}")
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
