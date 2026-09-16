"""MCP 工具**元信息**协议级验收（离线；只做 JSON-RPC 握手，绝不接触仪器）。

为什么要有这条：2026-09-16 用户报"instrument MCP 的 12 个工具缺 description
（49 个里 37 个有）"。查证结果是**已退役的 DG832 独立服务器**（`instrument_*` 命名、
13 个工具里 12 个没写 docstring）的老进程还在跑——统一服务器（本仓
`mcp_instruments/server.py`）里 57 个工具**全部**有 description。
本文件把这套核对固化成断言，将来"新增工具忘写 docstring"或"客户端连到了退役服务器"
都能一眼分辨。

    python TEST_SCRIPTS/common/verify_mcp_tools_meta.py

断言：
    §1 握手与工具表：initialize / tools/list 正常，名字唯一，数量达到下限
    §2 **每个工具的 description 非空**（FastMCP 取自函数 docstring）
    §3 每个工具都有 object 型 inputSchema（入参 schema 未被装饰器吃掉）
    §4 关键工具在列（覆盖 7 类设备的代表 + 护栏/兜底）
    §5 启动自检行打到 stderr（含工具数与 description 缺口统计）——且 **stdout 无污染**
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "mcp_instruments" / "server.py"
PY_EXE = sys.executable

fails: list[str] = []


def _is_jsonrpc(line: str) -> bool:
    """stdout 上的一行是否合法 JSON-RPC（协议流纯度判据）。"""
    try:
        obj = json.loads(line)
    except ValueError:
        return False
    return isinstance(obj, dict) and ("jsonrpc" in obj or "result" in obj or "error" in obj)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:56s} {str(detail)[:110]}", flush=True)
    if not ok:
        fails.append(name)


def main() -> int:
    proc = subprocess.Popen([PY_EXE, str(SERVER)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", bufsize=1, cwd=str(ROOT))

    def send(obj: dict) -> None:
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def read_line(timeout: float = 120.0) -> str:
        box: dict = {}
        th = threading.Thread(target=lambda: box.update(l=proc.stdout.readline()), daemon=True)
        th.start()
        th.join(timeout)
        return box.get("l", "")

    print("§1 握手与工具表", flush=True)
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "meta-check", "version": "1"}}})
    line = read_line()
    ok_init = bool(line.strip()) and "result" in (json.loads(line) if line.strip() else {})
    check("initialize 正常返回", ok_init, line[:80])
    send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    raw = read_line()
    tools = json.loads(raw)["result"]["tools"] if raw.strip() else []
    names = [t["name"] for t in tools]
    check("tools/list 返回工具表", len(tools) > 0, f"{len(tools)} 个工具")
    check("工具名无重复", len(names) == len(set(names)),
          f"{len(names)} 个名字 / {len(set(names))} 个唯一")
    check("工具数达到下限（≥50；当前统一服务器 57）", len(tools) >= 50, f"实际 {len(tools)}")

    print("\n§2 description 覆盖（FastMCP 取自函数 docstring）", flush=True)
    no_desc = [t["name"] for t in tools if not (t.get("description") or "").strip()]
    check("**每个工具都有非空 description**", not no_desc,
          f"缺 {len(no_desc)} 个：{no_desc}" if no_desc else f"{len(tools)}/{len(tools)} 全有")

    print("\n§3 inputSchema 完整", flush=True)
    bad_schema = [t["name"] for t in tools
                  if (t.get("inputSchema") or {}).get("type") != "object"]
    check("每个工具都有 object 型 inputSchema（装饰器未吃签名）", not bad_schema, str(bad_schema))

    print("\n§4 关键工具在列（七类设备 + 护栏 + 兜底）", flush=True)
    expect = ["instr_discover", "instr_query", "instr_write", "usb_reset",
              "sds_status", "sds_auto_scale", "sds_measure", "sdg_set_wave", "sdg_output",
              "dmm_measure", "dho_status", "dho_measure_item",
              "mho_status", "mho_measure_item", "mho_channel", "mho_fit_channel",
              "mho_timebase", "mho_trigger", "psu_status", "psu_output",
              "dg_status", "dg_protect", "dg_output"]
    missing = [n for n in expect if n not in names]
    check("代表工具齐全", not missing, f"缺 {missing}" if missing else f"核对 {len(expect)} 个")

    print("\n§5 启动自检行（stderr；stdout 必须是干净协议流）", flush=True)
    # stdout 纯净性：协议流里除 JSON-RPC 外不许有任何东西（历史事故：库里的 print
    # 打进协议通道 → 客户端 Connection closed）。先排空剩余行逐行验 JSON。
    extra: list[str] = []

    def drain() -> None:
        while True:
            line = proc.stdout.readline()
            if not line:
                return
            extra.append(line.rstrip("\n"))

    th = threading.Thread(target=drain, daemon=True)
    th.start()
    th.join(2.0)
    bad = [l for l in extra if l.strip() and not _is_jsonrpc(l)]
    check("stdout 只有合法 JSON-RPC（无 print 污染）", not bad, str(bad[:2]))
    proc.stdin.close()
    try:
        proc.wait(timeout=15)
    except Exception:
        proc.kill()
    err = proc.stderr.read()
    lines = [l for l in err.splitlines() if "启动自检" in l]
    check("启动自检行出现", bool(lines), lines[0][:100] if lines else "(无)")
    if lines:
        check("自检里报了工具数与 description 缺口",
              "工具" in lines[-1] and "description" in lines[-1], lines[-1][:120])
    print(f"\n== 结果: {'全部 PASS' if not fails else f'{len(fails)} 项 FAIL'} ==")
    for f in fails:
        print(f"  - {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
