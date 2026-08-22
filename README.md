# instrumentControl

集合仪表设备控制项目：统一封装 VISA/SCPI 控制层，按设备分目录管理专用驱动与实测脚本。

## 目录结构

```
instrumentControl/
├── common/                 # 通用部分：VISA 客户端与设备发现（多设备共用）
├── dh1766_control/         # DH1766 控制库（独立可安装：pip install -e ./dh1766_control）
│   ├── src/dh1766_control/ # 驱动 + SCPI 命令常量 + VISA 客户端（自包含）
│   └── docs/               # 手册提取 / 命令速查 / 经验总结
├── devices/                # 设备专用文档（驱动已迁入 dh1766_control）
├── archive/                # 历史版本归档（旧版驱动等，可回溯）
├── TEST_SCRIPTS/           # 实测脚本（按设备分目录，输出带时间戳留痕）
├── TEST_DATA/              # 实测留痕数据（JSON，时间戳命名）
└── requirements.txt
```

## 使用

```bash
pip install -r requirements.txt
pip install -e ./dh1766_control

# DH1766 实测：识别 + 读电压电流 + 开关通道演示
python TEST_SCRIPTS/dh1766/test_dh1766_read.py

# DH1766 全功能验证：手册 4.2 全部指令读写（备份-恢复式）
python TEST_SCRIPTS/dh1766/test_dh1766_full.py            # 空载时
python TEST_SCRIPTS/dh1766/test_dh1766_full.py --safe     # 接入负载时（输出ON通道拒绝改设定）
```

## 实测记录

- 2026-08-17：DH1766A-1 识别为 `USB0::0x0957::0xA007::100260004670::INSTR`，
  `*IDN?` = `BJDH,DH1766A-1,0,V0.1.4.3`；三路读回电压/电流正常，输出开关命令验证通过。
  注：该设备 VID=0x0957（Keysight ID），为国产仪器兼容 VISA 驱动常见做法，以 `*IDN?` 为准。
- 2026-08-17：手册 4.2 全部指令集 40/40 读写验证通过（`test_dh1766_full.py`，留痕见
  `TEST_DATA/dh1766/dh1766_full_*.json`）。全部写操作备份-恢复，设备设定与测试前一致。
  实测发现的固件差异（V0.1.4.3 vs 手册基于的 V0.1.2.8）见 `dh1766_control/docs/EXPERIENCE.md`。
- 2026-08-17：`dh1766_control` 库建立（src 布局，pip 可安装），DH1766 系列完整手册
  （43 页）经 read-pdf 提取归档至 `dh1766_control/docs/`，供后续查阅核对。
- 2026-08-23：`common/` 统一发现层上线（`find_device`：显式 resource → hosts 自动选协议 →
  已有资源列表 → CIDR 网段扫描，`--allow-scan` 默认关）。实测要点：纯 VISA 扫 /24 需 510s，
  加 TCP 端口预筛(111/4880/5025/5555) 后 ~8s；DH1766A-1 经网线可达
  `TCPIP0::192.168.31.144::5025::SOCKET`（raw socket 会话必须配 `\n` 终止符）；
  RIGOL DHO924S 示波器可达 `TCPIP0::192.168.31.146::5555::SOCKET`（Rigol SCPI raw 口）。
  带载(CH1 ON 12V/0.31A)下显式 LAN 直连读取正常，CH1 保持 ON 未做开关动作。留痕见
  `TEST_DATA/common/discovery_smoke_*.json` 与 `TEST_SCRIPTS/common/test_discovery.py`
  （T1~T5 全 PASS，扫描同时识别电源+示波器且 IDN 过滤不误配）。
- 2026-08-23：全网段探测（`TEST_SCRIPTS/common/probe_all.py`）新发现三台在线仪器：
  Keysight 34465A 万用表(`.123`，VXI-11)、Siglent SDG2122X 信号源(`.206`，VXI-11)、
  Siglent SDS824X HD 示波器(`.220`，VXI-11)。`dho_control` 库建立（DHO800/DHO900 系列
  通用，波形 BYTE/WORD TMC 解析 + 电压换算 `(raw-YORigin-YREFerence)*YINCrement`），
  手册提取至 `dho_control/docs/DHO800编程手册_output/`（418 页），hosts 直连验证通过。
  待办：SDS800X HD / SDG2000X 编程手册已在 E 盘定位待提取；34465A 编程手册缺需下载。

## 安全模式（接入负载后使用）

`DH1766(client, safe_mode=True)`：目标通道输出 ON 时拒绝修改电压/电流/OVP/OCP 及
输出模式（TRAC/SERI/PARA，继电器联动）；输出开关本身不拦截。
