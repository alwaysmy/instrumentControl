"""设备发现：薄壳转发 common 统一发现引擎（USB/LAN + fallback 可开关）。

运行环境要求：sys.path 需含项目根目录（以便 import common）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from common.discovery import (  # noqa: F401  (re-export)
    FindResult,
    find_device,
    identify,
    list_resources,
    scan,
)


_LAST_GOOD: dict[str, str] = {}
_LAST_GOOD_FILE = Path(__file__).resolve().parent / ".last_good_resource.json"


def _remember(key: str, resource: str) -> None:
    """记住上次成功地址（下次 find 同 key 设备优先直连，省扫描时间）。"""
    _LAST_GOOD[key] = resource
    try:
        _LAST_GOOD_FILE.write_text(
            json.dumps(_LAST_GOOD, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass  # 缓存失败不影响主流程


def _recall(key: str) -> Optional[str]:
    if key in _LAST_GOOD:
        return _LAST_GOOD[key]
    try:
        data = json.loads(_LAST_GOOD_FILE.read_text(encoding="utf-8"))
        _LAST_GOOD.update(data)
        return data.get(key)
    except Exception:
        return None


def find_dh1766(
    resource: Optional[str] = None,
    hosts: Optional[list[str]] = None,
    cidr: Optional[str] = None,
    allow_scan: bool = False,
    timeout_ms: int = 3000,
) -> str:
    """发现 *IDN? 含 'DH1766' 的设备，返回资源地址；未找到抛 RuntimeError。

    查找链：显式 resource → 上次成功地址缓存 → 显式 hosts(TCPIP 自动选协议) →
    已有 VISA 资源列表 → CIDR 网段扫描（仅 allow_scan=True 时作为最后手段）。
    显式指定在线但 IDN 不匹配时抛 ValueError（拒绝静默换设备）。
    """
    hit = find_device(
        "DH1766",
        resource=resource or _recall("DH1766"),
        hosts=hosts,
        allow_scan=allow_scan,
        cidr=cidr,
        timeout_ms=timeout_ms,
    )
    _remember("DH1766", hit.resource)
    return hit.resource
