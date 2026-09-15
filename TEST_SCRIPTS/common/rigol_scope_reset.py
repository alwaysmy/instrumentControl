"""受控复位脚本：RIGOL 示波器（DHO800/900 与 MHO900）的重启 / 恢复出厂。

**为什么单独做成脚本而不是库方法**：这两条命令属 AGENTS.md §二「禁止复位类命令」
（重启会让设备离线、屏上采集全丢；恢复出厂会清掉现场别人的设定）。为了让 AI/Agent
不会"顺手"调到，**库内不提供公开方法**，MCP 也不暴露——需要时用本脚本，且必须显式
加 `--allow-reset` 才能真发命令。命令常量本身保留在 `*_control/commands.py`
（`SYST_RESET` / `RST`），那里有逐条语义与风险说明。

⚠ 两个命令语义不同（手册原文核对，两系列一致）：
    :SYSTem:RESet  = 使系统重新上电（**重启**，不是恢复出厂）
    *RST           = 恢复出厂默认状态（**清掉全部设定**）

用法：
    python TEST_SCRIPTS/common/rigol_scope_reset.py --kind mho --info              # 只打印语义与风险，不发命令
    python TEST_SCRIPTS/common/rigol_scope_reset.py --kind mho --allow-reset --reboot
    python TEST_SCRIPTS/common/rigol_scope_reset.py --kind dho --allow-reset --factory

`--info` 无需授权、不碰设备，可随时用来查"这两条到底是什么语义、风险在哪"。
真发命令时需要：① `--allow-reset`（代表你已获授权）；② 明确选 `--reboot` 或 `--factory`
（不给就只打印说明，不会猜）。留痕写 `TEST_DATA/<kind>/scope_reset_<stamp>.json`。
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

KINDS = {"dho": ("dho_control", "DHO", ":SYSTem:RESet", "*RST"),
         "mho": ("mho_control", "MHO", ":SYSTem:RESet", "*RST")}

INFO = """两条复位命令的语义（按手册原文核对，DHO800/900 与 MHO900 一致）：

  :SYSTem:RESet  「使系统重新上电」→ **重启仪器**，不是恢复出厂设置
                  （手册 DHO 3.24.11 / MHO 3.24.12；旧 dho.py 曾误写"恢复出厂默认"）
  *RST           「将仪器恢复至出厂默认状态」→ **这才是恢复出厂**
                  （手册两系列 3.12.2）

风险：
  --reboot   ：设备离线数十秒 → 远程会话断开、需重连核对 *IDN?；
               屏上正在进行的采集/测量全部丢失；面板前有人会看到仪器突然重启。
  --factory  ：通道/时基/触发/测量配置**全部清零**——共享实验台上会把别人调好的
               设置一起清掉，属破坏性操作。

授权要求（AGENTS.md §二）：除用户显式要求，或用户声明"只有你在用这台设备"外，
不要执行。MCP 通用写口已黑名单拦截这两条命令，本脚本是唯一受控入口。"""


def main(argv: list[str]) -> int:
    args = set(argv)
    kind = "mho"
    for i, a in enumerate(argv):
        if a == "--kind" and i + 1 < len(argv):
            kind = argv[i + 1].lower()
    if kind not in KINDS:
        print(f"未知 --kind {kind!r}（可选 {', '.join(KINDS)}）")
        return 2

    lib, cls_name, cmd_reboot, cmd_factory = KINDS[kind]
    print(INFO)
    print(f"\n目标设备类：{kind}（库 {lib}）")

    if "--reboot" not in args and "--factory" not in args and "--info" not in args:
        print("\n（未指定 --reboot / --factory，仅打印说明，未发任何命令）")
        return 0
    if "--info" in args and "--reboot" not in args and "--factory" not in args:
        return 0
    if "--allow-reset" not in args:
        print("\n⚠ 拒绝执行：需要 --allow-reset（代表你已获授权）。上面是语义与风险说明。")
        return 2

    which = "reboot" if "--reboot" in args else "factory"
    cmd = cmd_reboot if which == "reboot" else cmd_factory
    print(f"\n=== 执行 {which}：发送 {cmd} ===")
    print("（注意：重启/复位后设备可能立即断开，下一次查询失败属预期）")

    res = resolve(kind)
    print(f"解析层 {kind} -> {res}")
    mod = __import__(lib)
    scope = getattr(mod, cls_name)(res)
    scope.connect()
    rows = [{"step": "idn_before", "ok": True, "detail": scope.idn()}]

    delivered, note = False, ""
    try:
        scope.write(cmd)
        delivered = True
        time.sleep(1.0)
        # 复位类命令通常立刻断连：能读到就记录，读不到不算失败
        try:
            note = f"复位后 *IDN? = {scope.idn()}"
        except Exception as e:
            note = f"复位后查询失败（预期内）：{type(e).__name__}"
    except Exception as e:
        note = f"发送异常（命令可能已送达）：{type(e).__name__}: {e}"
    finally:
        try:
            scope.close()
        except Exception:
            pass

    rows.append({"step": f"send:{which}", "ok": delivered, "detail": f"{cmd} → {note}"})
    out = ROOT / "TEST_DATA" / kind
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = out / f"scope_reset_{stamp}.json"
    f.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"),
                             "kind": kind, "resource": res, "action": which, "cmd": cmd,
                             "authorized": True, "rows": rows}, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"\n== 结果: {'已发送' if delivered else '未确认'} ==\n留痕: {f}")
    if which == "reboot":
        print("提示：设备重启需数十秒。之后请重新 `resolve(kind)` / 重连并核对 *IDN?。")
    else:
        print("提示：已恢复出厂——通道/时基/触发配置全部清零，需重新设置。")
    return 0 if delivered else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
