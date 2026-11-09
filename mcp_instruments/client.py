"""MCP 单例通用调用器（**产品侧**）：连 streamable-http 单例，调一个工具并回结果。

为什么在产品里：验收脚本、DSH/opencode 之外的自动化、以及"用真实 MCP 调用路径
验证某个工具"都需要它。原先只有 `TEST_SCRIPTS/common/mcp_call_tool_20261008.py`
一份 —— 属于"测试里才有、产品里反而缺"的能力，测试脚本现在只是本模块的薄壳。

用法::

    from mcp_instruments.client import call_tool
    r = call_tool("instr_discover")
    print(r["ok"], r["text"])

    # 或命令行（等价于旧的 mcp_call_tool.py）
    #   python -m mcp_instruments.client instr_discover
    #   python -m mcp_instruments.client sds_measure --args '{"item":"FREQ"}'

**只读友好**：本模块不做任何过滤，调什么由调用方决定 —— 调用写类工具前请自行确认授权。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Optional

DEFAULT_URL = "http://127.0.0.1:8765/mcp"


async def call_tool_async(tool: str, args: Optional[dict] = None, *,
                          url: str = DEFAULT_URL) -> dict[str, Any]:
    """调一个 MCP 工具，返回 ``{server, tool, args, ok, text}``。

    ``ok`` 取自返回体 JSON 的 ``ok`` 字段；解析不出来时为 ``None``
    （不是所有工具都返回 JSON，此时不应判为失败）。
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    params = dict(args or {})
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            result = await session.call_tool(tool, params)
            text = "".join(c.text for c in result.content if hasattr(c, "text"))
    try:
        ok = json.loads(text).get("ok")
    except Exception:                                          # noqa: BLE001
        ok = None
    return {
        "server": f"{init.serverInfo.name} v{init.serverInfo.version}",
        "tool": tool,
        "args": params,
        "ok": ok,
        "text": text,
    }


def call_tool(tool: str, args: Optional[dict] = None, *,
              url: str = DEFAULT_URL) -> dict[str, Any]:
    """``call_tool_async`` 的同步封装（供脚本 / REPL 用）。"""
    return asyncio.run(call_tool_async(tool, args, url=url))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mcp_instruments.client",
                                 description="调一个 MCP 工具并打印结果")
    ap.add_argument("tool", help="MCP 工具名，如 instr_discover / sds_status")
    ap.add_argument("--args", default="{}", help="JSON 对象形式的工具参数")
    ap.add_argument("--url", default=DEFAULT_URL, help=f"MCP 端点（默认 {DEFAULT_URL}）")
    a = ap.parse_args(argv)
    r = call_tool(a.tool, json.loads(a.args), url=a.url)
    print(f"# server={r['server']} tool={r['tool']} "
          f"args={json.dumps(r['args'], ensure_ascii=False)}")
    print(r["text"])
    return 0 if r["ok"] is not False else 1


if __name__ == "__main__":
    sys.exit(main())
