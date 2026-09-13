# dh1766_control

北京大华 DH1766 系列三路可编程直流电源控制库（SCPI over VISA）。

## 安装

```bash
pip install -e ./dh1766_control
# 依赖：pyvisa>=1.13.0 + 厂商 VISA 运行时（NI-VISA / Keysight IO Libraries，Windows 提供 visa32.dll）
```

> **自包含范围**：`DH1766` / `VisaClient` / `commands` 不依赖项目其他代码，pip 安装后可
> 独立使用（显式传资源串即可）。`find_dh1766` 则依赖项目根目录的 `common` 包在
> sys.path（见 `src/dh1766_control/discovery.py` 头注），脱离项目根使用时请改传
> 显式 resource。另：`visa.py` 是 `common/visa_client.py` 的镜像副本（原因同上），
> 两份须同步修改。

## 用法

```python
from dh1766_control import DH1766, VisaClient, find_dh1766

with VisaClient(find_dh1766()) as client:
    ps = DH1766(client)                    # 接入负载时用 DH1766(client, safe_mode=True)
    print(ps.idn())                        # BJDH,DH1766A-1,0,V0.1.4.3
    print(ps.measure_voltage_all())        # 回读三路电压
    print(ps.measure_current_all())        # 回读三路电流
    print(ps.apply_voltage())              # 三路电压设定值
    ps.set_output(1, True, "NORM")         # 打开 CH1（expect_mode 必填，仅校验不设置）
    ps.set_output_all([True, False, False], "NORM")
```

> **远程模式说明（2026-09-13 实测，固件 V0.1.4.3）**：任何远程会话（USB/LAN）都会把电源
> 置为 **REM**（远程模式）——新建会话第一条 `SYST:COMM:RLST?` 即返回 `REM`，这也是
> "一连接就进远程模式"的原因。需要把面板控制权交还现场时发 `ps.local()`（`SYST:LOC`），
> **不影响输出/电压/模式设定**；MCP 的 DH1766 工具每次调用收尾会自动补发一次。
> 注意：手册写法 `SYST:COMM:RLST:STAT?` 在本机**无响应（超时）**，应使用 `SYST:COMM:RLST?`；
> REM（远程模式）与手册的"远程锁定 RWL"（面板 Lock 键不可切回）是两个概念。
> 详见 docs/EXPERIENCE.md §3.1。

## 包结构

```
dh1766_control/
├── pyproject.toml
├── src/dh1766_control/
│   ├── __init__.py      # 导出 DH1766 / VisaClient / find_dh1766
│   ├── dh1766.py        # 驱动：系统/状态/通道/电压/电流/触发/输出/测量/复合/IEEE-488
│   ├── commands.py      # SCPI 命令常量与协议说明（SCPI-99 合规要点）
│   ├── visa.py          # VISA 客户端（自包含）
│   └── discovery.py     # 资源枚举与 *IDN? 识别
└── docs/
    ├── DH1766 系列三路可编程直流电源用户手册.md   # 完整手册提取（43 页，read-pdf）
    ├── SCPI_COMMANDS_DH1766A.md                 # DH1766A 命令速查（V2.1 手册）
    └── EXPERIENCE.md                            # 实测经验总结（固件差异/时序/坑）
```

## 平台注意

Windows 上 USB TMC 访问依赖厂商 VISA 运行时；禁止 pyusb/libusb 直接访问仪器
（除非设备已装 WinUSB/libusb 驱动）。详见 docs/EXPERIENCE.md。
