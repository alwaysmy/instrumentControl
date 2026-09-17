"""通用 VISA SCPI 客户端。

封装 pyvisa 的资源打开/查询/写入/关闭，统一超时与终止符。
所有仪器（USB TMC / 串口 / LAN）共用。

镜像副本：dh1766_control/src/dh1766_control/visa.py（该库需独立 pip 安装，
不能 import common）。两份代码体（class 及其方法）保持逐行一致，修改任一份
必须同步另一份；模块 docstring 的各自上下文说明是唯一允许的差异。
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

        ⚠ 只读**一次**——大块（如整屏 PNG）在 raw socket 上会被 TCP 分段截断，
        需要完整块请用 `query_block()`（2026-09-17 实测：MHO 截图 97471 字节，
        socket 上单次 read_raw 只拿到 6 字节）。
        """
        self.inst.write(cmd)
        return self.inst.read_raw()

    def query_block(self, cmd: str, max_reads: int = 2000) -> bytes:
        """发送命令并**把 TMC 大块读完**，返回数据体（无 TMC 头则原样返回）。

        为什么需要：VXI-11/HiSLIP 有消息分帧（一次 read 拿到整条消息），而
        **raw socket 没有帧**——大块会按 TCP 分段到达，单次 `read_raw` 只能拿到
        第一段（实测 97 KB 截图拿到 6 字节）。这里按 TMC 头声明的长度循环读到齐，
        并在长度不符时明确报错（不静默返回截断数据）。
        """
        data = self.query_raw(cmd)
        if not data[:1] == b"#":
            return data
        if len(data) < 2 or not data[1:2].isdigit():
            return data
        ndigits = int(data[1:2])
        if len(data) < 2 + ndigits:
            raise ValueError(f"TMC 头不完整: {data[:12]!r}")
        length = int(data[2:2 + ndigits])
        body = data[2 + ndigits:]
        reads = 0
        while len(body) < length and reads < max_reads:
            try:
                chunk = self.inst.read_raw()
            except Exception as e:      # noqa: BLE001
                raise ValueError(
                    f"TMC 块读取中断: 期望 {length} 字节，读得 {len(body)}（{type(e).__name__}）") from e
            if not chunk:
                break
            body += chunk
            reads += 1
        if len(body) < length:
            raise ValueError(f"TMC 数据不完整: 期望 {length} 字节，实得 {len(body)}")
        return body

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
