"""VISA 客户端（dh1766_control 库内置，自包含不依赖项目 common）。

Windows 平台约定：USB TMC 设备一律走厂商 VISA 运行时（visa32.dll），
禁止使用 pyusb/libusb 直接访问（除非设备安装 WinUSB/libusb 驱动）。

镜像副本：本项目 common/visa_client.py。两份代码体（class 及其方法、含
docstring）保持逐行一致，修改任一份必须同步另一份；模块 docstring 的
库级上下文说明（Windows 平台约定等）是唯一允许的差异。
"""
from __future__ import annotations

import pyvisa


class VisaClient:
    """持有一个 VISA 资源连接的 SCPI 客户端。

    默认配置 \\n 读写终止符——raw socket 设备（如 DH1766 的 5025 口）响应
    以 \\n 结尾，不设终止符时 read() 会等待 EOF 导致永久超时（即使设备
    已应答；pyvisa-py 后端尤其明显）。直连 open_resource 的调用方必须
    自行配置同等终止符。
    """

    def __init__(
        self,
        resource: str,
        timeout_ms: int = 5000,
        read_termination: str = "\n",
        write_termination: str = "\n",
        chunk_size: int = 4096,
        open_timeout_ms: int = 3000,
    ):
        self.resource = resource
        self.rm = pyvisa.ResourceManager()
        # open_timeout 与读超时分开：离线资源的 TCP 连接阶段不受 inst.timeout
        # 控制，不设会走系统默认（可达 60s+）
        self.inst = self.rm.open_resource(resource, open_timeout=open_timeout_ms)
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
