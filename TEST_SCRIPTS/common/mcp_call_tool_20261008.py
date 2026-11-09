"""MCP 单工具调用器（薄壳）：实现在 `mcp_instruments/client.py`（产品侧）。

保留本文件是为了不动既有验收脚本/文档里的调用方式。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp_instruments.client import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
