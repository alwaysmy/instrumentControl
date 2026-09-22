"""3458A / 82357B 分层诊断与恢复 CLI（**可复用运维工具**，专治"连不上"）。

为什么要有它（2026-09-23 接口卡死事故复盘 `docs/3458a_wedge_postmortem_20260923.md`）：
`viOpen`/`viRead`/`viWrite` 一旦卡在 `ioGPIB` 里，**同进程内无法中断**（超时/`finally`
都执行不到）→ 会把整套工具堵死。所以本工具默认把自己放到**子进程**里跑，
`--watchdog`（默认 30 s）超时就 kill——卡死在子进程里，调用方毫发无伤。

分层判据（逐层缩小范围，每层都给"下一步该干什么"）：

    1. 驱动层  PnP(82357B 状态/问题码) + ktvisa32.dll  + IO Libraries      → 缺驱动就提示装
    2. 枚举层  Keysight VISA list_resources（**不碰硬件**，只看配置/缓存）  → 空=接口没带起来
    3. 会话层  viOpen(GPIB0::9::INSTR)                                   → 崩/0xE06D7363=适配器卡死
    4. 应答层  **只发一条 viRead**（不写任何命令）：有字节=表在流数据；
               RSRC_NFOUND/TMO 无字节=**地址上没仪器**（上电/线/地址）
    5. 身份层  （`--id`）viWrite("ID?") + 读 → `HP3458A` 为正常
    6. 恢复层  （`--recover`）文档化恢复：clear + `TARM HOLD`/`TRIG HOLD` + 有界 drain
               + `END ALWAYS`/`INBUF ON`/`TRIG AUTO`（**不发 RESET、不改档位/NPLC/功能**）

用法::

    python -m keysight_3458a.preflight                 # 只读分层检查（默认，不写设备）
    python -m keysight_3458a.preflight --id            # 追加一条 ID?（写+读，仍不改测量配置）
    python -m keysight_3458a.preflight --recover       # 卡在流数据时用：文档化恢复后再 ID?
    python -m keysight_3458a.preflight --no-watchdog   # 直接在当前进程跑（排障用，慎用）
    python -m keysight_3458a.preflight --watchdog 45   # 自定义看门狗秒数

**重启后的标准动作**（2026-09-23 实测有效，见复盘文档）：
    ① 重启系统 → ② 若仍连不上：**拔插 82357B + 打开 Keysight Connection Expert**
    （让它重新发现接口）→ ③ 等适配器名字从 "<...> Initializing" 变回正常（~20-30 s）
    → ④ 跑本工具确认。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESOURCE = "GPIB0::9::INSTR"


def _ascii(text) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


def say(msg: str = "") -> None:
    print(_ascii(msg), flush=True)


# --------------------------------------------------------------------------
# 各层检查（都在调用方进程内跑；由外部看门狗保证不会拖垮会话）
# --------------------------------------------------------------------------
def layer_driver() -> dict:
    from keysight_3458a.driver_check import check_gpib_driver

    info = check_gpib_driver(use_cache=False)
    say(f"[1] 驱动层 : verdict={info.get('verdict')}  {info.get('message')}")
    for d in info.get("devices") or []:
        say(f"            设备 {d.get('instance_id')} status={d.get('status')} "
            f"problem={d.get('problem')}")
    say(f"            ktvisa32 = {info.get('ktvisa32')}")
    return info


def layer_enum() -> list[str]:
    out: dict = {"done": False, "res": [], "err": None}

    def work():
        try:
            import pyvisa

            from keysight_3458a.transport import keysight_visa_core, prepare_keysight_visa

            prepare_keysight_visa()
            core = keysight_visa_core()
            rm = pyvisa.ResourceManager(core) if core else pyvisa.ResourceManager()
            out["res"] = list(rm.list_resources())
            rm.close()
        except Exception as e:                                # noqa: BLE001
            out["err"] = f"{type(e).__name__}: {str(e)[:120]}"
        finally:
            out["done"] = True

    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(20.0)
    if not out["done"]:
        say("[2] 枚举层 : 超时(>20s) —— VISA 层无响应")
        return []
    gpib = [r for r in out["res"] if "GPIB" in r.upper()]
    say(f"[2] 枚举层 : {len(out['res'])} 个资源，GPIB={gpib or '无'}"
        + (f"  err={out['err']}" if out["err"] else ""))
    return gpib


def layer_session_and_answer(resource: str, do_id: bool, do_recover: bool) -> int:
    """会话层 + 应答层（+ 可选 ID?/恢复）。返回进程退出码（0=正常）。"""
    from keysight_3458a.transport import KeysightVisaTransport, TransportError

    t = KeysightVisaTransport(resource, timeout_s=6.0)
    try:
        t.open()
        say(f"[3] 会话层 : viOpen({resource}) OK")
    except Exception as e:                                    # noqa: BLE001
        msg = f"{type(e).__name__}: {str(e)[:130]}"
        say(f"[3] 会话层 : viOpen 失败 -> {msg}")
        if "0xE06D7363" in msg or "0xe06d7363" in msg or "0xC0000005" in msg:
            say("            => 适配器接口卡死（跨进程/跨拔插存活）。处置：杀相关进程 →")
            say("               重置适配器节点(usb_reset) → 仍不行就重启整机；期间不要重试")
        elif "RSRC_NFOUND" in msg:
            say("            => 该地址当前没有可打开的资源：接口没带起来，或仪器不在总线上")
        return 2

    try:
        # 应答层：**只读**——不写任何命令，只看有没有字节
        try:
            data = t.read(timeout_s=4.0)
            say(f"[4] 应答层 : viRead **有数据** {len(data)} 字符 -> {data[:80]!r}")
            say("            => 表活着但在持续输出（被上次会话留在流数据）")
            verdict = "streaming"
        except Exception as e:                                # noqa: BLE001
            msg = f"{type(e).__name__}: {str(e)[:110]}"
            say(f"[4] 应答层 : viRead 无数据 -> {msg}")
            if "RSRC_NFOUND" in msg or "TMO" in msg.upper():
                say("            => **地址上没有仪器**：查 3458A 是否上电 / GPIB 电缆两端"
                    "是否插牢 / 面板 GPIB 地址是否=9")
            verdict = "absent"

        if do_recover:
            say("[6] 恢复层 : clear + TARM/TRIG HOLD + 有界 drain + END/INBUF/TRIG AUTO"
                "（不发 RESET、不改档位/NPLC/功能）")
            t.clear()
            t.write("TARM HOLD")
            t.write("TRIG HOLD")
            t.drain(2, 250)
            t.write("END ALWAYS")
            t.write("INBUF ON")
            t.write("TRIG AUTO")
            say("            恢复命令已下发")

        if do_id:
            try:
                t.write("ID?")
                val = t.read(timeout_s=6.0)
                say(f"[5] 身份层 : ID? -> {val!r}")
                if "3458" in val.upper():
                    say("            => **通路完全正常**")
                    return 0
                # Talk Only（只讲不听）判别：手册 p.159 —— 前面板把 ADDRESS 设成 31 会进入
                # 该模式（TALK 指示灯亮、地址存连续内存、断电不丢），此时表**只输出读数、
                # 不理任何命令** → 每条查询都会"回"一个电压读数。
                try:
                    float(val.split()[-1])
                    is_num = True
                except (ValueError, IndexError):
                    is_num = False
                if is_num:
                    say("            => **疑似 Talk Only 模式（只讲不听）**：手册 p.159 —— "
                        "前面板 ADDRESS 被设成 31 时进入该模式（TALK 指示灯亮），"
                        "表只输出读数、不理命令；**地址存连续内存，断电不丢**。")
                    say("               处置（前面板）：把 **ADDRESS 改成 31 以外的值**（如 9）；"
                        "或按 Reset 键（Reset 会一并回到开机测量配置）")
                    return 5
                say("            => 有响应但不像 3458A，注意地址/设备是否搞错")
                return 1
            except Exception as e:                            # noqa: BLE001
                say(f"[5] 身份层 : ID? 失败 -> {type(e).__name__}: {str(e)[:110]}")
                return 1
        return 0 if verdict == "streaming" or do_recover else 1
    finally:
        try:
            t.close()
        except Exception:                                     # noqa: BLE001
            pass


def run_volts(args: argparse.Namespace) -> int:
    """**最小电压测试**：只恢复总线/触发态 + 读 N 次 DCV + 回读当前设定。

    不做任何配置变更：不发 `RESET`/`PRESET`、不设档位/NPLC/功能、不跑突发/ACV。
    只发：clear + `TARM HOLD`/`TRIG HOLD` + 有界 drain + `END ALWAYS`/`INBUF ON`/`TRIG AUTO`
    （都是总线/触发状态，不影响测量配置），然后 `TARM SGL,1` × N。
    """
    from keysight_3458a.transport import KeysightVisaTransport

    t = KeysightVisaTransport(args.resource, timeout_s=10.0)
    t.open()
    say(f"  已开会话 {args.resource}")
    # 恢复总线态（**不动测量配置**）
    t.clear()
    t.write("TARM HOLD")
    t.write("TRIG HOLD")
    t.drain(2, 250)
    t.write("END ALWAYS")
    t.write("INBUF ON")
    t.write("TRIG AUTO")
    say("  已恢复总线态（TARM/TRIG HOLD → END ALWAYS/INBUF ON/TRIG AUTO）")

    def ask(cmd: str, tmo: float = 8.0) -> str:
        t.write(cmd)
        return t.read(timeout_s=tmo).strip()

    print(f"  ID?      : {ask('ID?')!r}")
    for q in ("FUNC?", "RANGE?", "NPLC?", "ARANGE?"):
        try:
            print(f"  {q:9s}: {ask(q)!r}")
        except Exception as e:                                # noqa: BLE001
            print(f"  {q:9s}: 读失败 {type(e).__name__}")
    vals = []
    for i in range(int(args.volts)):
        try:
            raw = ask("TARM SGL,1", 15.0)
            v = float(raw.split()[-1]) if raw.split() else float("nan")
            vals.append(v)
            print(f"  read #{i + 1}  : {raw!r}  -> {v:.9e} V")
        except Exception as e:                                # noqa: BLE001
            print(f"  read #{i + 1}  : 失败 {type(e).__name__}: {str(e)[:90]}")
    try:
        print(f"  ERRSTR?  : {ask('ERRSTR?')!r}")
    except Exception:                                         # noqa: BLE001
        pass
    try:
        t.close()
    except Exception:                                         # noqa: BLE001
        pass
    if vals:
        say(f"== 电压功能正常：{len(vals)} 次读数，最近一次 {vals[-1]:.9e} V ==")
        return 0
    say("== 未能取到电压读数（见上）==")
    return 1


def run_child(args: argparse.Namespace) -> int:
    """在子进程里执行（--child），输出直接透传。"""
    if args.volts:
        return run_volts(args)
    info = layer_driver()
    gpib = layer_enum()
    if not info.get("ok") and info.get("verdict") in ("driver_missing", "iolib_missing"):
        say("== 结论：驱动不齐 -> 装 Keysight IO Libraries Suite ==")
        return 3
    rc = layer_session_and_answer(args.resource, args.id, args.recover)
    if rc == 0 and args.id:
        say("== 结论：3458A 通路正常 ==")
    elif rc == 2:
        say("== 结论：会话层失败（见上）==")
    elif rc == 1:
        say("== 结论：会话开得起来但仪器不应答（见上）==")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description="3458A/82357B 分层诊断与恢复")
    ap.add_argument("--resource", default=RESOURCE)
    ap.add_argument("--id", action="store_true", help="追加一条 ID?（写+读）")
    ap.add_argument("--recover", action="store_true",
                    help="下发文档化恢复（停流数据；不发 RESET）")
    ap.add_argument("--volts", nargs="?", const=3, default=0, type=int,
                    help="**最小电压测试**：恢复总线态 + 读 N 次 DCV（默认 3），不改任何设置")
    ap.add_argument("--watchdog", type=float, default=30.0, help="看门狗秒数（默认 30）")
    ap.add_argument("--no-watchdog", action="store_true", help="本进程直接跑（慎用）")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.child or args.no_watchdog:
        return run_child(args)

    # 默认：把危险动作放进子进程，超时 kill —— 卡在 DLL 里也拖不垮调用方
    cmd = [sys.executable, "-m", "keysight_3458a.preflight",
           "--child", "--resource", args.resource]
    if args.id:
        cmd.append("--id")
    if args.recover:
        cmd.append("--recover")
    if args.volts:
        cmd += ["--volts", str(args.volts)]
    say(f"（看门狗 {args.watchdog:.0f}s；子进程执行，卡死即 kill）")
    p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    try:
        out, _ = p.communicate(timeout=args.watchdog)
        sys.stdout.write(out or "")
        return p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
        sys.stdout.write(out or "")
        say(f"!! 看门狗超时（>{args.watchdog:.0f}s）→ 已 kill 子进程："
            f"DLL 层卡死，接口可能被占 —— 见 docs/3458a_wedge_postmortem_20260923.md")
        return 4


if __name__ == "__main__":
    sys.exit(main())
