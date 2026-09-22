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
    "mho": ("MHO", "RIGOL MHO900 系列示波器", "INSTRUMENT_MHO_RES"),
    "dg": ("DG8", "RIGOL DG800 系列信号源（DG832 基准）", "INSTRUMENT_DG_RES"),
    "psu": ("DH1766", "DH1766 三路可编程电源", "INSTRUMENT_PSU_RES"),
    # 3458A 的身份命令是 `ID?`（不是 *IDN?），返回含 3458；解析层只认这个串
    "ks3458a": ("3458", "HP/Keysight 3458A 八位半万用表", "INSTRUMENT_KS3458A_RES"),
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
    """按 *IDN? 文本判断属于哪类设备（匹配串见 DEVICE_KINDS）。"""
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
    """解析层已知地址映射（配置优先于缓存；只含 DEVICE_KINDS 里的合法条目）。"""
    out = {k: v for k, v in _load_json(CACHE_FILE).items()
           if k in DEVICE_KINDS and isinstance(v, str)}
    out.update({k: v for k, v in _load_json(CONFIG_FILE).items()
                if k in DEVICE_KINDS and isinstance(v, str)})
    return out


def is_visa_resource(value: str) -> bool:
    """粗略判断是否是完整资源串：VISA 资源串（含 `::`）或 SICL 短形式（`sicl:`）。

    覆盖 TCPIP/USB/ASRL/GPIB 以及 `visa://<gw>/TCPIP0::…` 别名形式——
    这些形态只有 VISA 解析器才认得全，**不要自己拼**：协议/端口/参数因设备而异
    （例如 DH1766 只认 raw 5025、DHO 只认 5555、SDS/SDG/DMM 走 VXI-11 inst0、
    USB 还要 vid/pid/serial），拼错一个字段就是"对未知设备发 SCPI"。

    `sicl:gpib0,9` 这类**本机 SICL 通路**同样算完整资源串：它含逗号、不含 `::`，
    若当成"裸主机名"就会拿它去探测网段（既无意义、又会对无关设备发 *IDN?）。
    """
    text = value or ""
    if text.strip().lower().startswith("sicl:"):
        return True
    return "::" in text


def canonicalize(kind: str, value: str) -> str:
    """把用户写的地址规范化为完整 VISA 资源串（**唯一允许"拼接"的入口**）。

    - 已是完整资源串（VISA 的 `::` 形态，或 SICL 的 `sicl:` 形态）→ 原样返回，
      不联网、不改写；
    - 裸主机名 / IP（如 `192.168.31.220`、`A-34461A-00000.local`）→
      ① 先看上次成功缓存里是否已有指向该 host 的资源（命中即用，不联网）；
      ② 否则按 LAN 多协议逐个探测（VXI-11 inst0 → HiSLIP → raw5025 → raw5555），
         命中后再用 `*IDN?` 核对设备类；
      全失败抛 RuntimeError（附可执行指引）。

    探测/校验都通过才返回——即"拼接"结果必须经仪器自证身份。
    """
    value = (value or "").strip()
    if not value:
        raise ValueError("地址不能为空")
    if kind not in DEVICE_KINDS:
        raise ValueError(f"未知设备类 {kind!r}，可选：{', '.join(DEVICE_KINDS)}")
    if is_visa_resource(value):
        return value
    token, label, _env = DEVICE_KINDS[kind]
    host = value

    # ① 缓存快路径：已知资源串里含该 host（不联网）
    cached = _load_json(CACHE_FILE).get(kind)
    if isinstance(cached, str) and host in cached:
        return cached

    # ② 联网探测（只读 *IDN?）
    from .discovery import identify_lan

    probe_err = None
    try:
        hit = identify_lan(host)
    except Exception as e:  # 探测层异常不直接透出，转成可执行指引
        hit, probe_err = None, f"{type(e).__name__}: {e}"
    if not hit:
        raise RuntimeError(
            f"地址 {host!r} 上未探测到可识别的仪器（VXI-11 inst0 / HiSLIP / "
            f"raw5025 / raw5555 全失败）。请确认设备在线、该地址正确，"
            f"或改用 instr_discover 重新发现。"
            + (f"（探测层异常：{probe_err}）" if probe_err else "")
        )
    res, idn = hit
    if token.upper() not in (idn or "").upper():
        raise RuntimeError(
            f"地址 {host!r} 上的设备 *IDN? = {idn!r}，不是目标设备"
            f"（{label}，期望含 {token!r}）——拒绝写入，以免误操作别的仪器。"
        )
    return res


def save_config(kind: str, resource: str) -> Path:
    """把某类设备的地址写进**用户配置文件**（本机专用，不入库）。

    值可以是完整 VISA 资源串，也可以是裸 host/IP——后者会先经 `canonicalize()`
    探测协议并核对 `*IDN?`，**只把规范化后的串落盘**（避免以后每次调用都重新探测，
    也避免把"半截地址"留在配置里）。保留文件里已有的其它键与说明字段。
    """
    if kind not in DEVICE_KINDS:
        raise ValueError(f"未知设备类 {kind!r}，可选：{', '.join(DEVICE_KINDS)}")
    if not resource or not resource.strip():
        raise ValueError("resource 不能为空")
    res = canonicalize(kind, resource)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_json(CONFIG_FILE)
    data[kind] = res
    _write_config(data)
    return CONFIG_FILE


def autofill_config(kinds: list[str] | None = None) -> dict[str, str]:
    """把解析层**已知**地址（缓存里 instr_discover 发现的结果）固化进配置文件。

    用于"设备都开着，把当前这套地址固定下来"：不联网，只搬运缓存里已有的条目。
    """
    cache = {k: v for k, v in _load_json(CACHE_FILE).items()
             if k in DEVICE_KINDS and isinstance(v, str)}
    picked = {k: v for k, v in cache.items() if not kinds or k in kinds}
    for kind, res in picked.items():
        save_config(kind, res)
    return picked


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
            "键 = 设备类（sds/sdg/dmm/dho/mho/dg/psu/ks3458a，见 resolver.DEVICE_KINDS）；"
            "值 = 完整资源串（VISA 的 `::` 形态，或 3458A 的 SICL 形态 `sicl:gpib0,9`）；"
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
        return canonicalize(kind, env.strip())
    cfg = _load_json(CONFIG_FILE).get(kind)
    if isinstance(cfg, str) and cfg.strip():
        res = canonicalize(kind, cfg.strip())
        if res != cfg.strip():
            # 自愈：配置里写的是裸 host/IP，探测出协议后把完整 VISA 串写回去，
            # 免得每次调用都重新探测（探测本身要连设备，只读 *IDN?）。
            try:
                save_config(kind, res)
            except Exception:
                pass
        return res
    cached = _load_json(CACHE_FILE).get(kind)
    if isinstance(cached, str) and cached.strip():
        return canonicalize(kind, cached.strip())

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
