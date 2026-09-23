"""compact profile 的**实机**冒烟测试（只读）——补上"设备路径未验证"这个缺口。

为什么需要它：阶段 1–4 的验证全部是离线的（假 registry / 假 executor），证明的是调度、
作用域、错误传播这些逻辑，**不是 VISA 行为**。而阶段 5 要把 compact 切成默认，那会改变
日常使用的仪器接口 —— 在没验证过的地面上改默认接口不合适。本脚本就是补这一刀。

安全设计（都写进代码，不靠使用者记）：

1. **必须在命令行显式确认**才会运行（`--i-know-this-touches-hardware`）；缺少即退出，
   所以它不可能被误触发（例如被别的脚本批量调用时）。
2. **只调用只读操作**：每个候选 op 都要过 `instrument_runtime` 的安全分级
   （`catalog.RISK_BY_TOOL`），`risk != "read_only"` 一律拒绝。这不是"约定"，是运行期检查。
3. **不写任何设备状态**：不设档位、不开关输出、不改触发、不发复位。全部是测量/查询。
4. 通过 MCP stdio 走**真实协议**（不是进程内直调），因此验证的是客户端真正看到的那条路。

用法（**会碰真实仪器，需先获得授权**）：
    python TEST_SCRIPTS/common/verify_compact_live.py --i-know-this-touches-hardware
    # 可选：--device sds|dmm|dg|psu|mho|sdg   只测指定设备族
    # 可选：--repeat 3                         batch 里重复读几次

不碰仪器的那部分（tools/list、search、describe、拒绝路径）已经在 verify_compact_mcp.py 里覆盖，
本脚本只补"真实调用"这一段。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "mcp_instruments" / "server.py"
PY_EXE = sys.executable
sys.path.insert(0, str(ROOT))

fails: list[str] = []


def _ascii(text) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {_ascii(name):52s} {_ascii(detail)[:110]}", flush=True)
    if not ok:
        fails.append(name)


class Probe:
    def __init__(self, profile: str = "compact", timeout: float = 300.0) -> None:
        env = dict(os.environ)
        env["INSTRUMENT_MCP_PROFILE"] = profile
        self.timeout = timeout
        self.proc = subprocess.Popen([PY_EXE, str(SERVER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     bufsize=0, cwd=str(ROOT), env=env)

    def send(self, obj: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def read_line(self, timeout: float | None = None) -> str:
        assert self.proc.stdout is not None
        box: dict = {}
        th = threading.Thread(
            target=lambda: box.update(l=self.proc.stdout.readline().decode("utf-8", "replace")),
            daemon=True)
        th.start()
        th.join(timeout if timeout is not None else self.timeout)
        return box.get("l", "")

    def handshake(self) -> None:
        self.send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                              "clientInfo": {"name": "compact-live", "version": "1"}}})
        self.read_line()
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call(self, name: str, args: dict, timeout: float | None = None) -> dict:
        self.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": name, "arguments": args}})
        line = self.read_line(timeout)
        if not line.strip():
            return {"_transport": "timeout"}
        obj = json.loads(line)
        if "error" in obj:
            return {"_rpc_error": obj["error"]}
        content = (obj.get("result") or {}).get("content") or []
        try:
            return json.loads(content[0]["text"]) if content else {}
        except Exception:                                        # noqa: BLE001
            return {"_raw": content[0].get("text") if content else ""}

    def close(self) -> str:
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except Exception:                                        # noqa: BLE001
            self.proc.kill()
        assert self.proc.stderr is not None
        return self.proc.stderr.read().decode("utf-8", "replace")


def _read_only_probe_op(device: str | None) -> tuple[str, dict] | None:
    """挑一个**只读**的、不需要复杂参数的探测操作。

    逐个候选都过安全分级（catalog.RISK_BY_TOOL）；任何一个不是 read_only 就跳过。
    """
    from instrument_runtime import RISK_BY_TOOL

    # (op_id, args)：全部为只读状态查询，不改变设备任何设置
    candidates = [
        ("dmm.status", {}),
        ("sds.status", {}),
        ("dg.status", {}),
        ("psu.status", {}),
        ("mho.status", {}),
        ("sdg.status", {}),
        ("ks3458a.status", {}),
    ]
    for op_id, args in candidates:
        tool = op_id.replace(".", "_")
        if device and op_id.split(".")[0] != device:
            continue
        if RISK_BY_TOOL.get(tool) != "read_only":
            continue        # 运行期强制：只碰只读操作
        return op_id, args
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="compact profile live smoke test (read-only)")
    ap.add_argument("--i-know-this-touches-hardware", dest="ack", action="store_true",
                    help="显式确认：本脚本会与真实仪器通信（只读）")
    ap.add_argument("--device", default=None, help="只测指定设备族")
    ap.add_argument("--repeat", type=int, default=3, help="batch 内重复读次数")
    args = ap.parse_args()

    if not args.ack:
        # 这几行是**给人看的**，保持 ASCII：中文在部分控制台代码页下会变乱码，
        # 而"为什么被拒绝、怎么继续"恰恰是最不能看不懂的信息。
        print("REFUSED: this script talks to real instruments.")
        print("Confirm the target device and impact, then re-run with:")
        print("    --i-know-this-touches-hardware")
        print("It only calls operations classified read_only in the catalog;")
        print("no device state is changed (no output/range/trigger/reset writes).")
        return 2

    from instrument_runtime import RISK_BY_TOOL

    probe_op = _read_only_probe_op(args.device)
    if probe_op is None:
        print(f"no eligible read-only probe operation found (device={args.device})")
        return 2
    op_id, op_args = probe_op
    print(f"== compact live smoke (read-only) ==\nprobe op: {op_id} args={op_args} "
          f"| batch repeats={args.repeat}\n")

    p = Probe()
    try:
        p.handshake()

        print("S1 single read-only call (instr_call)")
        r = p.call("instr_call", {"op": op_id, "args": op_args})
        ok = bool(r.get("ok"))
        check(f"instr_call({op_id}) returns ok", ok, str(r)[:100])
        check("response carries model (device layer really reached)",
              bool(r.get("model")) or not ok, str(r.get("model")))
        check("read-only op did not require confirm",
              r.get("error_type") != "confirm_required", str(r.get("error_type")))

        print("\nS2 batch read-only (instr_batch, whole batch = one job)")
        plan = {"plan_version": 1, "on_error": "stop",
                "max_leaf_steps": max(2, args.repeat + 1),
                "max_nesting_depth": 0,
                "steps": ([{"op": op_id, "args": op_args,
                            "capture": {"var": "r", "source": "result"}}]
                          + [{"op": op_id, "args": op_args} for _ in range(args.repeat - 1)])}
        b = p.call("instr_batch", {"plan": plan}, timeout=400)
        check("instr_batch completed", b.get("status") == "completed", str(b.get("status")))
        check(f"all {args.repeat} leaves succeeded",
              b.get("success_count") == args.repeat, str(b.get("success_count")))
        check("capture recorded exactly one entry", len(b.get("capture_log") or []) == 1,
              str(len(b.get("capture_log") or [])))
        check("run summary persisted to an artifact",
              bool(b.get("result_artifact")), str(b.get("result_artifact"))[:80])

        print("\nS3 consistency between the two paths")
        check("batch reported no unexpected warnings (contention-only allowed)",
              all("另一个进程" in (w.get("message") or "") for w in (b.get("warnings") or []))
              or not (b.get("warnings")), str((b.get("warnings") or [])[:1])[:90])

        print("\nS4 read-only self-proof")
        check("probe op is classified read_only in the catalog",
              RISK_BY_TOOL.get(op_id.replace(".", "_")) == "read_only",
              str(RISK_BY_TOOL.get(op_id.replace(".", "_"))))
        p.close()
    finally:
        try:
            p.close()
        except Exception:                                        # noqa: BLE001
            pass

    print(f"\n== result: {'all PASS' if not fails else f'{len(fails)} FAIL'} ==")
    for f in fails:
        print(f"  - {_ascii(f)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
