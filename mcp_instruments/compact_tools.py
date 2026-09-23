"""compact profile 的 MCP 前端——4 个按需发现工具。

背景（docs/gpt_qa/2026-09-23-instrument-gateway-arch.md，方案 C 阶段 3）：
legacy profile 把 68 个工具定义全部塞进每次请求（实测 ≈19.8k token，占该 harness
静态注入的 44%），而多数会话根本不碰仪器。compact profile 只暴露 4 个稳定工具，
把"有哪些能力"变成**按需数据**：

    instr_devices()                     当前有哪些仪器（复用 legacy 的网络发现）
    instr_search(query, device, limit)  按关键词找操作
    instr_describe(ids)                 取某个操作的完整 schema/说明/安全属性
    instr_call(op, args)                执行一次操作

三点设计约定：

* **名字不与 legacy 冲突**：legacy 的 `instr_discover` 是"扫网段发现设备"，
  与"列出仪器"语义相近但参数不同；compact 下用 `instr_devices` 指代后者，
  避免两个 profile 之间出现同名不同义的陷阱。
* **执行语义完全复用 legacy**：`instr_call` 经注入的 `run_fn` 走同一个执行器
  （单 worker 串行、device_busy 闸门、墙钟预算），**不另起一条执行路径**——
  否则"compact 下超时行为不一样"这类差异会极难排查。
* **安全不经前端**：`instr_call` 不做任何放行判断，护栏仍在操作实现与 policy 层
  （`instr_query`/`instr_write`/`dg_query` 自带黑名单，DG832 的保护联锁在库里）。
  所以绕过 compact 前端直接调 `instr_call` 也不会跳过任何门——这正是"护栏下沉"
  的意义（阶段 2）。前端只负责**入参校验**，把参数错误在离开模型时就说清楚。
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from instrument_runtime.validate import format_issues, validate_for_operation

__all__ = ["register", "COMPACT_TOOL_NAMES"]

#: compact profile 暴露的工具名（legacy 与之互斥，由 profile 决定注册哪一套）。
COMPACT_TOOL_NAMES = ("instr_devices", "instr_search", "instr_describe", "instr_call")

_MAX_DESCRIBE = 8   # 单次 describe 的操作数上限（防止一次拉回半张表）
_MAX_LIMIT = 20     # search 返回条数上限


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _score(op, query: str) -> int:
    """极简关键词打分（68 个操作的规模不需要 embeddings，见讨论存档 §2.3）。"""
    q = query.lower().strip()
    if not q:
        return 0
    score = 0
    if q == op.id.lower() or q == op.tool_name.lower():
        return 1000
    if q in op.id.lower() or q in op.tool_name.lower():
        score += 50
    for word in q.replace(",", " ").split():
        if not word:
            continue
        if word in op.tool_name.lower():
            score += 20
        if word in (op.summary or "").lower():
            score += 8
        if word in (op.description or "").lower():
            score += 3
        if word in op.device.lower():
            score += 10
        if any(word == k for k in op.keywords):
            score += 6
    return score


def register(mcp, *, registry, run_fn: Callable[[str, dict], Awaitable[str]],
             devices_op: str = "instr_discover") -> tuple[str, ...]:
    """把 4 个 compact 工具注册到给定的 FastMCP 实例，返回工具名元组。

    run_fn(op_id, args) 由 server.py 注入——它负责用**既有执行器**跑操作并回填
    统一返回体；本模块不碰设备、不碰执行器。
    """

    @mcp.tool()
    async def instr_devices() -> str:
        """列出当前可用的仪器（扫描本机各网段与已注册地址）。

        等价于 legacy profile 的 `instr_discover`，但**不含 cidr 参数**——compact 下
        默认扫全部本机网段即可。返回各设备的标识、地址与状态；不做任何设备操作。
        """
        return await run_fn(devices_op, {})

    @mcp.tool()
    async def instr_search(query: str, device: str | None = None,
                           limit: int = 8) -> str:
        """搜索可用的仪器操作，返回规范 id 与一句话摘要（不返回完整参数表）。

        query: 自然语言或关键词，例如 "扫频 信号源"、"measure vpp"、"output on"；
        device: 可选，限定设备族（dg832/sds/sdg/dmm/dho/mho/psu/ks3458a/instr/usb）；
        limit: 返回条数上限（1-20，默认 8）。

        拿到 id 后用 `instr_describe` 取完整参数表，再用 `instr_call` 执行。
        """
        try:
            n = int(limit)
        except (TypeError, ValueError):
            return _json({"ok": False, "error_type": "param_validation",
                          "error": f"limit 必须是整数，收到 {limit!r}"})
        if not 1 <= n <= _MAX_LIMIT:
            return _json({"ok": False, "error_type": "param_validation",
                          "error": f"limit 超出范围 1-{_MAX_LIMIT}：{n}"})
        ops = list(registry)
        if device:
            ops = [o for o in ops if o.device == device]
        ranked = sorted(((_score(o, query), o) for o in ops),
                        key=lambda p: (-p[0], p[1].id))
        hits = [o for s, o in ranked if s > 0][:n]
        if not hits:
            return _json({"ok": True, "query": query, "device": device, "count": 0,
                          "results": [],
                          "hint": "没有匹配的操作；可换关键词，或用 instr_search "
                                  "查设备族名（如 'sds'）列出该设备全部操作。"})
        return _json({
            "ok": True, "query": query, "device": device, "count": len(hits),
            "results": [{"id": o.id, "tool_name": o.tool_name, "device": o.device,
                         "risk": o.safety.risk,
                         "requires_confirm": o.safety.requires_confirm,
                         "summary": o.summary} for o in hits],
        })

    @mcp.tool()
    async def instr_describe(ids: str) -> str:
        """取操作的完整定义：参数表（JSON Schema）、说明、安全属性与关键约束。

        ids: 一个或多个操作 id / 工具名，逗号分隔，例如
             "sdg.set_wave" 或 "sds_measure,dmm_measure"（单次最多 8 个）。

        执行前应先 describe——说明里含该操作的强制前置条件与实测设备行为
        （例如 dg_protect 必须先于设幅度/开输出），跳过它会得到 protect_required 之类的拒绝。
        """
        wanted = [x.strip() for x in (ids or "").split(",") if x.strip()]
        if not wanted:
            return _json({"ok": False, "error_type": "param_validation",
                          "error": "ids 不能为空；传操作 id 或工具名，逗号分隔"})
        if len(wanted) > _MAX_DESCRIBE:
            return _json({"ok": False, "error_type": "param_validation",
                          "error": f"单次最多 {_MAX_DESCRIBE} 个，收到 {len(wanted)} 个"})
        found, missing = [], []
        for key in wanted:
            op = registry.get(key) or registry.by_id(key)
            if op is None:
                missing.append(key)
                continue
            found.append({
                "id": op.id, "tool_name": op.tool_name, "device": op.device,
                "summary": op.summary, "description": op.description,
                "parameters": dict(op.schema),
                "safety": {"risk": op.safety.risk,
                           "requires_confirm": op.safety.requires_confirm,
                           "raw_scpi": op.safety.raw_scpi,
                           "verify": list(op.safety.verify)},
                "notes": op.safety.note or None,
            })
        out: dict = {"ok": True, "count": len(found), "operations": found}
        if missing:
            out["not_found"] = missing
            out["hint"] = "未知 id；用 instr_search 找正确的 id。"
        return _json(out)

    @mcp.tool()
    async def instr_call(op: str, args: dict | None = None) -> str:
        """执行一次仪器操作。

        op: 操作 id 或工具名，例如 "sdg.set_wave"、"sds_measure"（先用 instr_search 找）；
        args: 参数字典，键名与 instr_describe 返回的 parameters 一致，例如
              {"ch": 1, "shape": "sine", "freq": 1000, "amp": 2.0}。

        省略有默认值的参数即用默认值；必填参数缺失或类型不符会**在本地直接拒绝**，
        不会下发到设备。返回值与 legacy profile 下同名工具完全一致（同一执行路径）。
        有副作用的操作（改输出/关机/复位）仍需按该操作的说明显式传 confirm=True。

        组合与循环（扫频、批量采集）请勿用本工具的多次调用堆叠——逐次调用会带来
        大量往返；那类任务属于后续阶段的 `instr_run`（受限代码执行）。
        """
        target = registry.get(op) or registry.by_id(op)
        if target is None:
            return _json({"ok": False, "error_type": "param_validation",
                          "error": f"未知操作 {op!r}；用 instr_search 查找正确的 id。"})
        payload = {} if args is None else args
        issues = validate_for_operation(target, payload)
        if issues:
            return _json({"ok": False, "error_type": "param_validation",
                          "error": f"入参校验未通过：{format_issues(issues)}",
                          "issues": [{"param": i.param, "message": i.message} for i in issues],
                          "expected": list((target.schema.get("properties") or {}).keys()),
                          "required": list(target.schema.get("required") or [])})
        return await run_fn(target.tool_name, dict(payload))

    return COMPACT_TOOL_NAMES
