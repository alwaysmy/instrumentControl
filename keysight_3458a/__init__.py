"""keysight_3458a — HP/Keysight 3458A 八位半万用表控制库（**非 SCPI**，专用实现）。

```python
from keysight_3458a import DMM3458A, find_3458a

hit = find_3458a()                       # 逐个候选探测，用 ID? 核对身份（不写死地址）
with DMM3458A(hit["resource"]) as d:
    print(d.idn())                       # HP3458A
    d.configure_dcv(10.0, 10.0)          # 10V 档 / 10 PLC（换档后自动丢首读数）
    print(d.read_dcv())                  # 单次 DCV（TARM SGL,1）
    burst = d.read_burst(1000, sample_interval_s=10e-6)   # 100k rdg/s 二进制突发
```

两条传输通路（`transport.make_transport` 按资源串自动选）：

    `GPIB0::9::INSTR` / `visa://<host>/GPIB0::9::INSTR` → PyVisaTransport
    `sicl:gpib0,9` / `gpib0,9`                          → SiclTransport（本机 SICL）

命令白名单与出处见 `commands.py` 与 `docs/COMMANDS_3458A.md`；已知坑见 `README.md`。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 与 keysight_3446x 同口径：保证 `common`（发现/解析层）可导入，无论从哪启动
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from .commands import (  # noqa: E402
    BURST_MAX_READINGS,
    DCV_10V_OVERLOAD_V,
    DCV_RANGES,
    DEFAULT_APERTURE_S,
    DEFAULT_SAMPLE_INTERVAL_S,
)
from .discovery import candidate_resources, find_3458a  # noqa: E402
from .dmm3458a import DMM3458A, is_error_clear  # noqa: E402
from .transport import (  # noqa: E402
    PyVisaTransport,
    SiclTransport,
    Transport,
    TransportError,
    is_sicl_resource,
    make_transport,
    parse_sicl_addr,
)

__all__ = [
    "BURST_MAX_READINGS",
    "DCV_10V_OVERLOAD_V",
    "DCV_RANGES",
    "DEFAULT_APERTURE_S",
    "DEFAULT_SAMPLE_INTERVAL_S",
    "DMM3458A",
    "PyVisaTransport",
    "SiclTransport",
    "Transport",
    "TransportError",
    "candidate_resources",
    "find_3458a",
    "is_error_clear",
    "is_sicl_resource",
    "make_transport",
    "parse_sicl_addr",
]
