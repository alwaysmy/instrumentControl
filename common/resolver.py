"""设备地址解析层：**不写死 IP**，统一按优先级解析仪器资源串。

仪器地址是**环境相关**的：DHCP 续租会换 IP、换网段/换交换机端口会不可达、
USB 换口会换资源串、串口 ASRL 编号会漂移。因此任何"把某个地址当成设备固定资源"
的写法都是缺陷——地址只能是"上次发现/上次成功"的缓存，并由发现层持续刷新。

解析顺序（`resolve(kind, resource)`）：

    ① 显式入参 resource                （最高优先，调用方明确指定）
    ② 环境变量 INSTRUMENT_<KIND>_RES   （如 INSTRUMENT_SDS_RES，适合容器/CI）
    ③ 用户配置 <配置目录>/devices.json  （{"sds": "TCPIP0::…::inst0::INSTR", …}）
    ④ 上次成功缓存 <配置目录>/last_good_resources.json
       —— `instr_discover` 发现成功后按 *IDN? 回写；任何工具/脚本连接成功后也回写
    ⑤ 自动发现 common.find_device(idn_contains=…, allow_scan=False)
       —— 只查 VISA 已注册资源（秒级）；LAN 未注册设备请先跑 instr_discover
       —— 需要"工具调用时自动扫网段"的部署可设 INSTRUMENT_ALLOW_SCAN=1

配置目录默认 `%LOCALAPPDATA%\\instrumentControl`（其他平台退 XDG_CACHE_HOME / ~/.cache），
不落仓库源码树。MCP 服务器与 `TEST_SCRIPTS/` 共用本模块，避免两套地址来源。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# kind -> (IDN 匹配串, 人类可读名, 环境变量名)
DEVICE_KINDS: dict[str, tuple[str, str, str]] = {
    "sds": ("SDS", "Siglent SDS800X HD 示波器", "INSTRUMENT_SDS_RES"),
    "sdg": ("SDG", "Siglent SDG2000X 信号源", "INSTRUMENT_SDG_RES"),
    "dmm": ("34465A", "Keysight 34465A 万用表", "INSTRUMENT_DMM_RES"),
    "dho": ("DHO", "RIGOL DHO800/900 示波器", "INSTRUMENT_DHO_RES"),
    "psu": ("DH1766", "DH1766 三路可编程电源", "INSTRUMENT_PSU_RES"),
}

CACHE_DIR = Path(
    os.environ.get("LOCALAPPDATA")
    or os.environ.get("XDG_CACHE_HOME")
    or (Path.home() / ".cache")
) / "instrumentControl"
CONFIG_DIR = CACHE_DIR  # 配置与缓存同目录（本机专用，不入库）
CACHE_FILE = CACHE_DIR / "last_good_resources.json"
CONFIG_FILE = CONFIG_DIR / "devices.json"


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def remember(kind: str, resource: str) -> None:
    """记下某类设备本次成功的地址（下次优先直连；缓存失败不影响主流程）。"""
    if not resource:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = _load_json(CACHE_FILE)
        data[kind] = resource
        tmp = CACHE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CACHE_FILE)  # 原子替换：多实例/脚本并发时不丢更新
    except Exception:
        pass


def idn_kind(idn: Optional[str]) -> Optional[str]:
    """按 *IDN? 文本判断属于哪类设备（SDS/SDG/34465A/DHO/DH1766）。"""
    if not idn:
        return None
    up = idn.upper()
    for kind, (token, _label, _env) in DEVICE_KINDS.items():
        if token.upper() in up:
            return kind
    return None


def resource_rank(resource: str) -> int:
    """多协议命中时的优选顺序：VXI-11 inst0 > HiSLIP > 其他 INSTR > raw SOCKET。"""
    up = resource.upper()
    if up.endswith("::INST0::INSTR"):
        return 0
    if "HISLIP" in up:
        return 1
    if up.endswith("::INSTR"):
        return 2
    return 3


def remember_candidates(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """把 [(resource, idn)] 里可识别的设备按优选顺序回写缓存；返回本次识别结果。

    `instr_discover` / 各库 `find_*()` 结果都可直接喂进来。
    """
    best: dict[str, tuple[int, str]] = {}
    for res, idn in pairs:
        kind = idn_kind(idn)
        if not kind or not res:
            continue
        rank = resource_rank(res)
        if kind not in best or rank < best[kind][0]:
            best[kind] = (rank, res)
    for kind, (_rank, res) in best.items():
        remember(kind, res)
    return {k: v[1] for k, v in best.items()}


def known_resources() -> dict[str, str]:
    """解析层已知地址映射（配置优先于缓存；只含 5 类设备的合法条目）。"""
    out = {k: v for k, v in _load_json(CACHE_FILE).items()
           if k in DEVICE_KINDS and isinstance(v, str)}
    out.update({k: v for k, v in _load_json(CONFIG_FILE).items()
                if k in DEVICE_KINDS and isinstance(v, str)})
    return out


def save_config(kind: str, resource: str) -> Path:
    """把某类设备的地址写进**用户配置文件**（本机专用，不入库）。

    配置文件优先级高于缓存与自动发现，适合"这套仪器在本机的固定/默认地址"；
    保留文件里已有的其它键与注释字段（只增改目标键）。
    """
    if kind not in DEVICE_KINDS:
        raise ValueError(f"未知设备类 {kind!r}，可选：{', '.join(DEVICE_KINDS)}")
    if not resource or not resource.strip():
        raise ValueError("resource 不能为空")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_json(CONFIG_FILE)
    data[kind] = resource.strip()
    _write_config(data)
    return CONFIG_FILE


def clear_config(kind: str) -> Path:
    """删除配置文件里的某类设备条目（删除后回落到缓存/自动发现）。"""
    data = _load_json(CONFIG_FILE)
    data.pop(kind, None)
    _write_config(data)
    return CONFIG_FILE


def _write_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


def config_template() -> dict:
    """配置文件骨架（只放说明与示例，不放真实键——留空即回落到自动发现）。"""
    return {
        "_说明": (
            "仪器地址配置文件（本机专用，不入库、可随时手改）。"
            "键 = 设备类 sds/sdg/dmm/dho/psu；值 = 完整 VISA 资源串；"
            "删除某键 = 该项回落到『上次成功缓存 → 自动发现』。"
            "优先级：显式入参 > 环境变量 INSTRUMENT_<KIND>_RES > 本文件 > 缓存 > 自动发现。"
            "写入用 `python mcp_instruments/config_cli.py set <kind> <resource>`，"
            "查看用 `... config_cli.py show`。"
        ),
        "_示例（勿照抄，按实际改）": {
            "sds": "TCPIP0::192.0.2.10::inst0::INSTR",
            "psu": "TCPIP0::192.0.2.11::5025::SOCKET",
        },
    }


def explain(kind: str) -> dict:
    """列出某类设备的解析链现状（**不做设备 I/O**：不触发自动发现）。"""
    token, label, env_name = DEVICE_KINDS[kind]
    env = os.environ.get(env_name)
    cfg = _load_json(CONFIG_FILE).get(kind)
    cached = _load_json(CACHE_FILE).get(kind)
    if isinstance(env, str) and env.strip():
        src, val = "env", env.strip()
    elif isinstance(cfg, str) and cfg.strip():
        src, val = "config", cfg.strip()
    elif isinstance(cached, str) and cached.strip():
        src, val = "cache", cached.strip()
    else:
        src, val = None, None
    return {"kind": kind, "label": label, "idn_match": token, "env_var": env_name,
            "env": env if isinstance(env, str) and env.strip() else None,
            "config": cfg if isinstance(cfg, str) and cfg.strip() else None,
            "cache": cached if isinstance(cached, str) and cached.strip() else None,
            "source": src, "resource": val}


def resolve(kind: str, resource: Optional[str] = None) -> str:
    """解析设备资源串：显式 > env > 用户配置 > 上次成功缓存 > 自动发现。

    全失败时抛 RuntimeError，文案给出可执行指引（跑 instr_discover / 设 env / 写配置）。
    """
    if kind not in DEVICE_KINDS:
        raise ValueError(f"未知设备类 {kind!r}，可选：{', '.join(DEVICE_KINDS)}")
    if resource:
        return resource
    _token, label, env_name = DEVICE_KINDS[kind]

    env = os.environ.get(env_name)
    if env and env.strip():
        return env.strip()
    cfg = _load_json(CONFIG_FILE).get(kind)
    if isinstance(cfg, str) and cfg.strip():
        return cfg.strip()
    cached = _load_json(CACHE_FILE).get(kind)
    if isinstance(cached, str) and cached.strip():
        return cached.strip()

    try:
        from .discovery import find_device

        try:
            hit = find_device(_token, allow_scan=False, timeout_ms=2000)
        except Exception:
            # 默认不扫网段（find_device 的设计取向：扫描是最后手段，代理 fake-IP 会误报）
            if os.environ.get("INSTRUMENT_ALLOW_SCAN", "").strip() not in ("1", "true", "True"):
                raise
            hit = find_device(_token, allow_scan=True, timeout_ms=2000)
    except Exception as e:
        raise RuntimeError(
            f"未确定 {label} 的资源地址（自动发现失败：{type(e).__name__}）。"
            f"仪器地址会随 DHCP/换网段/换口变化，请先调用 instr_discover 重新发现"
            f"（发现结果会自动记住）；也可设环境变量 {env_name}，"
            f"或把地址写进配置文件 {CONFIG_FILE}（键名 {kind}）。"
            f"若希望调用时自动扫描网段，可设 INSTRUMENT_ALLOW_SCAN=1。"
        ) from e
    remember(kind, hit.resource)
    return hit.resource
