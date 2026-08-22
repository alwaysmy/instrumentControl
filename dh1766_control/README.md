# dh1766_control

北京大华 DH1766 系列三路可编程直流电源控制库（SCPI over VISA）。

## 安装

```bash
pip install -e ./dh1766_control
# 依赖：pyvisa>=1.13.0 + 厂商 VISA 运行时（NI-VISA / Keysight IO Libraries，Windows 提供 visa32.dll）
```

## 用法

```python
from dh1766_control import DH1766, VisaClient, find_dh1766

with VisaClient(find_dh1766()) as client:
    ps = DH1766(client)                    # 接入负载时用 DH1766(client, safe_mode=True)
    print(ps.idn())                        # BJDH,DH1766A-1,0,V0.1.4.3
    print(ps.measure_voltage_all())        # 回读三路电压
    print(ps.measure_current_all())        # 回读三路电流
    print(ps.apply_voltage())              # 三路电压设定值
    ps.set_output(1, True)                 # 打开 CH1
    ps.set_output_all([True, False, False])
```

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
