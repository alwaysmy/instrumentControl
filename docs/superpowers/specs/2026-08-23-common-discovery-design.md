# 设计：common 统一发现层（USB/LAN + fallback）

日期：2026-08-23
状态：已批准（傅师傅，2026-08-23）
范围：instrumentControl 主项目 + dg832-control（独立 git 仓库）

## 1. 背景与目标

当前设备发现仅靠 `pyvisa.ResourceManager().list_resources()`（USB 资源会列出，
未配置的 TCPIP 设备不会自动出现）。USB 掉线时无备用路径。

目标：
- 支持网络（TCPIP/VXI-11）显式指定与网段扫描发现；
- 允许指定接口（完整资源串或 host 列表）；
- 自动 fallback 可开关，默认关闭（最后手段）；
- 统一收口到 `common/` 层，dh1766_control 与 dg832 均接入。

已知网络环境：局域网内除 DH1766A-1、DG832 外**还有一台示波器**——扫描必须
按 `idn_contains` 过滤跳过非目标设备，并把所有在线设备的 `*IDN?` 打印留痕。

## 2. 已确认的决策

| 决策点 | 结论 |
|---|---|
| 功能落点 | common 统一层，两个设备库都依赖 |
| 打包方式 | dh1766_control 暂不做可安装包；common 裸目录 + sys.path 引用；将来统一工具化时再设计 |
| 发现深度 | 显式指定（resource/host）+ 网段扫描 |
| fallback | 默认关闭，作为最后手段显式开启 |
| 实现形态 | 方案 A：纯函数参数式，CLI 参数透传（不做配置文件/环境变量） |

## 3. 架构与模块划分

```
instrumentControl/
├── common/
│   ├── __init__.py            # 导出 find_device / FindResult / list_resources / identify / scan
│   ├── discovery.py           # 重写：发现引擎（本次核心）
│   └── visa_client.py         # 不动
├── dh1766_control/src/dh1766_control/discovery.py   # 薄壳化，转发 common
├── dg832-control/DG832使用/dg832.py                 # find_resource 接引擎
└── TEST_SCRIPTS/dh1766/*.py                        # 加接口参数透传
```

明示技术债：运行时靠 sys.path 同时插入项目根（为 common）与库 src。
测试脚本各加一行 insert。将来统一工具化时解决。

## 4. API 设计

```python
@dataclass
class FindResult:
    resource: str      # 命中的 VISA 资源串
    idn: str           # *IDN? 响应原文
    source: str        # explicit | listed | scanned

def find_device(
    idn_contains: str,               # *IDN? 子串匹配，大小写不敏感
    resource: str | None = None,     # 层① 完整资源串（USB/TCPIP 均可）
    hosts: list[str] | None = None,  # 层② IP/host 列表 → TCPIP0::{ip}::inst0::INSTR
    proto: str = "inst0",            # inst0 | hislip0
    allow_scan: bool = False,        # 层③④ 最后手段开关，默认 False
    cidr: str | None = None,         # 层④ 网段；None 时自动探测本机 /24
    timeout_ms: int = 3000,
) -> FindResult
```

查找顺序：① 显式 resource → ② 显式 hosts → ③ list_resources 全扫 → ④ CIDR 并发扫。
③④ 仅在未给显式参数、或显式全失败且 allow_scan=True 时执行。

安全语义：
- 显式指定**连上但 IDN 不匹配** → ValueError（附实际 IDN），任何情况下不静默换设备；
- 显式指定**连不上** → allow_scan=True 才降级下一层，否则失败；
- 每层尝试记录 (层名, 目标, 结果/异常摘要)，最终失败 RuntimeError 打印完整链路。

## 5. 网段扫描实现

- `ipaddress` 解析 CIDR；cidr=None 且 allow_scan 时经 UDP socket 路由探测本机 IP 取 /24，
  打印探测结果再开扫；多网卡建议显式传 cidr；
- ThreadPoolExecutor(max_workers=32)，每 IP 短超时 1500ms；单 IP 异常吞掉只计数；
- 在线命中立即打印 `[scan] <resource> -> <IDN>`（实时留痕）；
- 只走 VISA open_resource + *IDN?，不做裸 socket 端口探测；
- 非目标设备（如示波器）打印后继续扫，不命中不报错。

## 6. 接入点改造

- dh1766_control/discovery.py：`find_dh1766(resource=None, hosts=None, cidr=None,
  allow_scan=False)` 转发 `find_device(idn_contains="DH1766", ...)`；
- TEST_SCRIPTS 两脚本：argparse 加 `--resource/--host(多次)/--cidr/--allow-scan`；
  顺手修复 P1 bug（get_voltage_set/get_current_set → 现 API apply_voltage()/apply_current()）；
- dg832.py：`DG832.__init__` 加 hosts/allow_scan/cidr；connect() 内 USB VID/PID 匹配
  失败且 allow_scan 时走通用引擎；改动前独立仓库先 commit 保护现状；
- MCP server 本期不动。

## 7. 测试计划

冒烟（无设备/离线场景，TEST_SCRIPTS/common/test_discovery.py，JSON 留痕至 TEST_DATA/common/）：

| 场景 | 预期 |
|---|---|
| 指定不存在 IP | 快速失败，错误链路完整 |
| 显式 resource IDN 不匹配 | ValueError，不 fallback |
| USB 在线无参调用 | listed 命中（行为同现状）|
| LAN --host | explicit 命中（需设备接网线）|
| --allow-scan --cidr 小测试段 | scanned 命中并留痕 |

实机验证按设备在线情况执行，结果记录到 TEST_DATA/common/（时间戳命名）。
