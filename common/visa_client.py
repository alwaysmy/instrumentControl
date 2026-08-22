"""通用 VISA SCPI 客户端。

封装 pyvisa 的资源打开/查询/写入/关闭，统一超时与终止符。
所有仪器（USB TMC / 串口 / LAN）共用。
"""
from __future__ import annotations

import pyvisa


class VisaClient:
    """持有一个 VISA 资源连接的 SCPI 客户端。"""

    def __init__(
        self,
        resource: str,
        timeout_ms: int = 5000,
        read_termination: str = "\n",
        write_termination: str = "\n",
        chunk_size: int = 4096,
    ):
        self.resource = resource
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.timeout = timeout_ms
        self.inst.read_termination = read_termination
        self.inst.write_termination = write_termination
        self.inst.chunk_size = chunk_size

    def query(self, cmd: str) -> str:
        """发送 SCPI 查询命令并读取一行响应（去除首尾空白）。"""
        return self.inst.query(cmd).strip()

    def query_raw(self, cmd: str) -> bytes:
        """发送命令并读取原始字节（TMC 二进制块用）。

        新版 pyvisa 的 MessageBasedResource 已移除 query_raw，
        统一用 write + read_raw 组合。
        """
        self.inst.write(cmd)
        return self.inst.read_raw()

    def write(self, cmd: str) -> None:
        """发送 SCPI 命令，不读取响应。"""
        self.inst.write(cmd)

    def close(self) -> None:
        """关闭连接与资源管理器。幂等。"""
        try:
            self.inst.close()
        finally:
            self.rm.close()

    def __enter__(self) -> "VisaClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
