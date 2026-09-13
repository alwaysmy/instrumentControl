"""设备发现：薄壳转发 common 统一发现引擎（USB/LAN + fallback 可开关）。

运行环境要求：sys.path 需含项目根目录（以便 import common）。
"""
from __future__ import annotations

import json
import os
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

# 运行期缓存放**用户级缓存目录**，不写进包源码树（此前落在包目录内，污染安装目录、
# 且 pip 安装到 site-packages 时可能无写权限）。Windows 用 %LOCALAPPDATA%，
# 其他平台退回 XDG_CACHE_HOME / ~/.cache。
_CACHE_DIR = Path(
    os.environ.get("LOCALAPPDATA")
    or os.environ.get("XDG_CACHE_HOME")
    or (Path.home() / ".cache")
) / "instrumentControl"
_LAST_GOOD_FILE = _CACHE_DIR / "last_good_resource.json"
# 旧位置（包目录内）——只读兼容：一次性迁移到新位置后不再写入
_LEGACY_FILE = Path(__file__).resolve().parent / ".last_good_resource.json"


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _remember(key: str, resource: str) -> None:
    """记住上次成功地址（下次 find 同 key 设备优先直连，省扫描时间）。

    写入用户级缓存目录（`%LOCALAPPDATA%\\instrumentControl\\last_good_resource.json`）。
    """
    _LAST_GOOD[key] = resource
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _LAST_GOOD_FILE.write_text(
            json.dumps(_LAST_GOOD, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass  # 缓存失败不影响主流程


def _recall(key: str) -> Optional[str]:
    if key in _LAST_GOOD:
        return _LAST_GOOD[key]
    data = _load_json(_LAST_GOOD_FILE)
    if not data and _LEGACY_FILE.exists():  # 旧位置兼容：读到即迁移
        data = _load_json(_LEGACY_FILE)
        if data:
            try:
                _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _LAST_GOOD_FILE.write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8"
                )
                _LEGACY_FILE.unlink(missing_ok=True)
            except Exception:
                pass
    _LAST_GOOD.update(data)
    return data.get(key)


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
