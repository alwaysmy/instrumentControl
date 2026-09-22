"""3458A 的资源定位——**不写死 IP / host**（沿用 `common/resolver.py` 的哲学）。

仪器地址不是固定资产：远端 VISA server 的 IP 会变、GPIB 卡换口会换接口号、SICL 是否
可用取决于本机装了哪套 Keysight IO 库。所以这里只做两件事：

    ① `candidate_resources()` —— **纯函数**，按优先级列出候选资源串（不联网、不打开设备）；
    ② `find_3458a()` —— 逐个候选打开会话，用 **`ID?`**（3458A 没有 `*IDN?`）核对身份，
       成功即返回并回写解析层缓存。

候选顺序：显式入参 → 解析层已知地址（env/配置/缓存，远端 VISA server 串通常在这里）
→ `hosts` 里的每个 host（`visa://<host>/GPIB0::<addr>::INSTR`）→ 本机
`GPIB0::<addr>::INSTR` → `sicl:gpib0,<addr>`。

最后一个是 EmoeCalibrator 现场的实战通路：Keysight VISA 打不开 82357B USB/GPIB 卡上的
`GPIB0::<addr>::INSTR`（`VI_ERROR_INTF_NUM_NCONFIG`），SICL 能通。
"""
from __future__ import annotations

from typing import Optional

from .dmm3458a import DMM3458A
from .transport import is_sicl_resource

DEFAULT_GPIB_ADDR = 9
IDN_TOKEN = "3458"          # ID? 里必须出现的串（HP3458A / 3458A 都含它）
RESOLVER_KIND = "ks3458a"     # common/resolver.py 的 DEVICE_KINDS 键
DEFAULT_TIMEOUT_S = 5.0     # 逐候选探测超时（探测要快，真读数走各工具自己的超时）


def candidate_resources(resource: Optional[str] = None, addr: int = DEFAULT_GPIB_ADDR,
                        hosts: Optional[list[str]] = None,
                        known: Optional[str] = None) -> list[str]:
    """按优先级生成候选资源串（**纯函数**：不联网、不打开任何设备，可离线断言）。

    `known` = 解析层已知地址（`resolve("ks3458a")` 的来源：环境变量
    `INSTRUMENT_KS3458A_RES` / devices.json / 上次成功缓存）。远端 VISA server 串
    （`visa://<host>/GPIB0::9::INSTR`）通常从这个入参进来——**不在这里拼 host**。
    """
    candidates: list[str] = []
    if resource:
        candidates.append(str(resource).strip())
    if known:
        candidates.append(str(known).strip())
    for host in (hosts or []):
        text = str(host or "").strip()
        if text:
            candidates.append(f"visa://{text}/GPIB0::{int(addr)}::INSTR")
    candidates.append(f"GPIB0::{int(addr)}::INSTR")
    candidates.append(f"sicl:gpib0,{int(addr)}")
    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _known_resource() -> Optional[str]:
    """解析层已知地址（只读本地文件/环境变量，**不触发自动发现**）。"""
    try:
        from common.resolver import explain

        return explain(RESOLVER_KIND).get("resource")
    except Exception:                                # noqa: BLE001 —— 发现层不可用不该阻断
        return None


def find_3458a(resource: Optional[str] = None, addr: int = DEFAULT_GPIB_ADDR,
               hosts: Optional[list[str]] = None, allow_scan: bool = False,
               timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """定位 3458A 并用 `ID?` 校验身份。

    返回 `{"resource", "idn", "transport", "tried"}`：

        - `resource`：命中的资源串（可直接喂给 `DMM3458A(resource)`）；
        - `idn`：`ID?` 原文（作为"确实是 3458A"的证据）；
        - `transport`：`"sicl"` 或 `"visa"`；
        - `tried`：之前失败的候选与原因（**留痕**：为什么最后选了这条通路）。

    `allow_scan=True` 时额外把本机 VISA 已注册的 **GPIB 资源**加进候选（最后手段；
    注意**不做网段扫描**——3458A 挂在 GPIB，不是 LAN 设备，扫网段没有意义）。
    全部候选失败抛 `RuntimeError`，文案列出每个候选的失败原因。
    """
    known = None if resource else _known_resource()
    candidates = candidate_resources(resource, addr, hosts, known)

    tried: list[dict] = []
    for candidate in list(candidates):
        hit = _probe(candidate, timeout_s, tried)
        if hit:
            _remember(hit["resource"])
            hit["tried"] = tried
            return hit

    if allow_scan:
        for scanned in _gpib_resources():
            if scanned in candidates:
                continue
            candidates.append(scanned)
            hit = _probe(scanned, timeout_s, tried)
            if hit:
                _remember(hit["resource"])
                hit["tried"] = tried
                return hit

    detail = "；".join(f"{item['resource']} → {item['error']}" for item in tried) or "（无候选）"
    raise RuntimeError(
        f"未找到可用的 3458A（{len(tried)} 个候选全部失败：{detail}）。"
        f"排查：① 设备是否开机、GPIB 地址是否为 {addr}；② 远端 VISA server 是否在线"
        f"（用环境变量 INSTRUMENT_KS3458A_RES=visa://<host>/GPIB0::{addr}::INSTR 或 "
        f"`config_cli.py set ks3458a <地址>` 固定地址）；③ 本机 SICL 是否可用"
        f"（需要 Keysight IO Libraries Suite）。"
    )


def _probe(candidate: str, timeout_s: float, tried: list[dict]) -> Optional[dict]:
    """试一个候选：连接 + `ID?` + 身份核对。失败把原因记进 `tried` 并返回 None。"""
    dmm = DMM3458A(candidate, timeout_s=timeout_s)
    idn = None
    error = None
    try:
        dmm.connect()
        idn = dmm.idn()
    except Exception as e:                           # noqa: BLE001 —— 探测失败即换下一个
        error = f"{type(e).__name__}: {e}"
    finally:
        try:
            dmm.close()
        except Exception:                            # noqa: BLE001
            pass
    if error is not None:
        tried.append({"resource": candidate, "error": error})
        return None
    if IDN_TOKEN not in (idn or "").upper():
        tried.append({"resource": candidate,
                      "error": f"ID? = {idn!r} 不含 {IDN_TOKEN!r}（不是 3458A，拒绝使用）"})
        return None
    return {"resource": candidate, "idn": idn,
            "transport": "sicl" if is_sicl_resource(candidate) else "visa"}


def _gpib_resources() -> list[str]:
    """本机 VISA 已注册资源里的 GPIB 条目（**只读列表，不打开设备**）。"""
    try:
        from common.discovery import list_resources

        return [r for r in list_resources() if "GPIB" in str(r).upper()]
    except Exception:                                # noqa: BLE001
        return []


def _remember(resource: str) -> None:
    """把命中的地址回写解析层缓存（下次优先直连；失败不影响主流程）。"""
    try:
        from common.resolver import remember

        remember(RESOLVER_KIND, resource)
    except Exception:                                # noqa: BLE001
        pass
