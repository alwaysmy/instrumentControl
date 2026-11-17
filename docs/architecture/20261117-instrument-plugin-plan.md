# 仪器插件化（Instrument Plugins）改造计划

> **状态：计划阶段，只写方案，不动代码。**（2026-11-17）
>
> 关联：`docs/architecture/20261109-instrument-console.md`（中控本体架构）。
> 本文只讨论「每台仪器做成可安装的插件」这一件事，不重述中控的分层与同步模型。

## 一、目标与非目标

### 目标

1. **新增一台仪器 = 装一个包**，不再改主仓的 4 个地方（驱动注册表、类规范、实例规范、MCP 工具面）。
2. 插件可**独立发版、独立测试、独立下线**，不必跟着主仓一起发。
3. 外协单位/第三方能只交**一个目录**就算交付。
4. 拆掉「加一台仪器要改 5 个文件」这个最容易出错的点。

### 非目标

* **不做热插拔**。插件在启动期一次性加载，运行期不卸载。
* **不放宽 `core/` 只用标准库**这条铁律（`verify_console_layering.py` 会断言）。
* **不做远程下载执行**。插件必须已经在本地（内置 / 已安装 / 显式放行目录）。
* **不改 71 个 MCP 工具的名字与参数**——那是对外契约，改名会让基线整体换版（见 §九.1）。

## 二、现状：一台仪器被拆在 5 个地方

| # | 落点 | 现状 | 证据 |
|---|---|---|---|
| 1 | 驱动注册 | `drivers/__init__.py` 里一个**硬编码元组** `_REGISTRATIONS`，10 条 | `instrument_console/drivers/__init__.py` |
| 2 | 类规范 | `spec/classes/*.json`，9 个（按**命令族**拆，不按品类） | `core/spec.py:56` `CLASS_DIR` |
| 3 | 实例规范 | `spec/instruments/*.json`，10 个 | `core/spec.py:57` `INSTANCE_DIR` |
| 4 | MCP 工具面 | `mcp_instruments/server.py`（3053 行）里 71 个 `@device_tool()` 函数 | `server.py:780` / `:806` / `:812` |
| 5 | 设备/安全映射 | `instrument_runtime.DEVICE_BY_PREFIX`（10 条）+ `server.py:297` `_risk_of_tool()` | `instrument_runtime/__init__.py:22` |

三处关键硬编码：

```python
# instrument_console/core/spec.py:55-57
SPEC_ROOT = Path(__file__).resolve().parent.parent / "spec"
CLASS_DIR = SPEC_ROOT / "classes"
INSTANCE_DIR = SPEC_ROOT / "instruments"
```

```python
# instrument_console/drivers/__init__.py
_REGISTRATIONS: tuple[tuple[str, type], ...] = (
    ("psu", PsuDriver), ("sds", SdsDriver), ("dho", DhoDriver), ("mho", MhoDriver),
    ("sdg", SdgDriver), ("dg832", Dg832Driver), ("dmm3446x", Dmm3446xDriver),
    ("dmm3458a", Dmm3458aDriver), ("emoe", EmoeDriver), ("fake", FakeDriver),
)
```

`DEVICE_BY_PREFIX` 实测：`dg->dg832, sds->sds, sdg->sdg, dmm->dmm, dho->dho, mho->mho, psu->psu, ks3458a->ks3458a, instr->instr, usb->usb`。

### 两个现成的接缝（好消息）

* `core/spec.py:457` `def load_all(root: Path | None = None, ...)` —— **已经能换 root**，多目录加载只需改成列表。
* `core/driver.py` `DRIVERS` + `register_driver(name, cls)` —— 已做重名检查，只需把「谁来调它」从元组改成自动发现。

## 三、目标形态

### 3.1 一个插件 = 一个目录

```
instruments/dg832/
├── plugin.json           # 清单（唯一入口，缺它不加载）
├── driver.py             # BaseDriver 子类，@op 标注操作
├── tools.py              # 可选：MCP 工具面（函数 + @device_tool）
├── spec/
│   ├── class.signal_source_dg.json
│   └── instance.dg.json
└── tests/
    └── test_driver.py
```

命名空间用 `instruments/`，**不要用 `plugins/`** —— 后者已经被 DSH / OpenChamber 的 UI 插件占用
（`plugins/dsh-instrument-console/`、`plugins/openchamber-instrument-console/`），混在一起会让人
以为 UI 插件也是仪器。

### 3.2 清单字段

```json
{
  "id": "dg832",
  "name": "RIGOL DG832",
  "version": "0.2.0",
  "console_api": ">=1,<2",
  "driver": "dg832",
  "driver_class": "driver:Dg832Driver",
  "specs": {
    "classes":   ["spec/class.signal_source_dg.json"],
    "instances": ["spec/instance.dg.json"]
  },
  "resolver_kind": "dg",
  "mcp": { "prefix": "dg_", "tools": "tools:iter_tools" },
  "requires": ["pyvisa>=1.14"],
  "platform": ["win32"],
  "enabled": true
}
```

几个字段的理由：

* `console_api` —— 宿主版本闸。不匹配就**整插件拒绝加载**，不给半加载状态（半加载是最难查的故障）。
* `resolver_kind` —— 声明它消费 `common.resolver` 的哪个 kind；插件**不能**自己猜地址。
* `mcp.prefix` —— 现在 `DEVICE_BY_PREFIX` 靠工具名前缀反推设备，前缀只能在这里声明一次。
* `platform` —— `keysight_3458a` 只在 Windows 有意义，没必要在 Linux CI 上假装能加载。

### 3.3 发现顺序（优先级从低到高，同 id 后者覆盖前者会让**启动失败**）

1. **内置**：`instrument_console/instruments/`，随宿主安装，10 台原样搬进来。
2. **站点包**：`importlib.metadata.entry_points(group="instrument_console.plugins")`。
3. **本机目录**：`%LOCALAPPDATA%\instrumentControl\plugins\`，给现场临时加一台用；
   需要显式开关 `INSTRUMENT_ALLOW_LOCAL_PLUGINS=1`（见 §七）。

同 id 出现两次 → **拒绝启动并打印两个来源的路径**。不静默覆盖——现场两版驱动混用会出
「同一台表有时能读有时不能」这种最难查的故障。

`enabled: false` 的插件**不加载代码**（只记一条日志），这样临时停用一台不必卸包。

### 3.4 加载流程

```
for root in search_paths:                 # 内置 → 站点包 → 本机目录
    for entry in scan(root):
        manifest = read(entry/"plugin.json")
        check_version(manifest.console_api, HOST_API)   # 不匹配 → 跳过 + 记日志
        check_platform(manifest.platform)
        detect_conflict(manifest.id)                     # 冲突 → 抛错，整进程退出
        load_driver(manifest)                            # register_driver
        load_specs(manifest)                             # 收集到 spec 搜索路径
        load_tools(manifest)                             # 只收集，装配留给宿主
classes, instruments, catalog = spec.load_all(roots=[...])
```

顺序很关键：**先注册驱动，再加载规范**——`load_all` 里的 `build_catalog` 需要通过
`driver_lookup` 找到驱动类的 `@op` 声明来生成操作目录（见 `core/spec.py:498`）。

## 四、契约：谁提供什么

| 归宿主（`instrument_console/core`） | 归插件 |
|---|---|
| `DriverContext` / `BaseDriver` / `@op()` / `register_driver` | 一个 `BaseDriver` 子类 |
| `load_all()` / 规范校验 / `field_overrides` 校验 | 类规范 + 实例规范 JSON |
| 风险等级语义、`confirm`、回读纪律、审计、session lock | `@op(risk=...)` 的**声明**（判定权在宿主） |
| MCP 装配（`mcp.tool()` + `_register_runtime_operation`） | 工具函数本身 |
| 面板渲染 / widget | **什么都不用写**（这是现有设计能维护的原因） |

三条铁律**不变**（见 `core/driver.py` 文档串）：

1. 驱动里**不做安全判断**——黑名单 / confirm / 回读属于 `instrument_runtime` 与规范层。
2. **签名即 schema**：`def _output(self, ch: int, on: bool, expect_mode: str)` 就是参数表。
3. **资源串由外部解析**后传进来（`DriverContext.resource`），驱动不猜地址。

插件化只改「谁来注册」，不改这三条。

## 五、分五期（每期都能独立回滚）

| 期 | 内容 | 行为变化 | 粗估 |
|---|---|---|---|
| **P1 去硬编码** | `_REGISTRATIONS` 元组 → 模块自注册；`DEVICE_BY_PREFIX` → 清单字段；`SPEC_ROOT` 单根 → 搜索路径列表 | **无** | 1–2 天 |
| **P2 目录化** | 建 `instruments/`，10 台原样搬进去；`drivers/__init__.py` 变薄壳 | **无**（回归必须全绿） | 2–3 天 |
| **P3 加载器** | entry points + 本机目录 + 冲突检测 + 版本闸 + `enabled` 开关 | 新增能力 | 1–2 天 |
| **P4 工具面搬进插件** | `dg_*` 试点 → `sds_*` → 其余按族 | 无（名字/参数不变） | 3–5 天 |
| **P5 第三方试点 + 文档** | 交一个「只写 JSON」的插件样例；补 `docs/` | 新增能力 | 1 天 |

合计约 **2 周**（不含真机复验）。

### P1 的验收标准

* `python -c "import instrument_console.drivers"` 后 `len(DRIVERS) == 10`，且**不 import pyvisa**
  （`verify_console_layering.py` 已有这条断言）。
* `verify_registry_parity.py` 71 条仍全绿。
* `TEST_SCRIPTS/common/regression_offline.ps1` 27 套件全绿。

### P1 具体怎么改

```python
# 改前：drivers/__init__.py 末尾
_REGISTRATIONS = (("psu", PsuDriver), ...)
def register_all(): ...

# 改后：drivers/*.py 各自在模块底部自注册
from ..core.driver import register_driver
register_driver("psu", PsuDriver)          # 每个驱动模块一行

# drivers/__init__.py 只做「把子模块都 import 一遍」
import pkgutil, importlib
for m in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{m.name}")
```

注意：自注册会让**导入顺序**变成隐式的。可接受的替代是保留一个显式的 `_BUILTIN` 列表但由
`plugin.json` 生成——不要既想要隐式又抱怨难查，二选一，建议**先自注册**（简单、可回滚）。

## 六、最难的一块：MCP 工具面（P4）

`mcp_instruments/server.py` 3053 行、71 个工具，每个 `@device_tool()` 一次干三件事
（`server.py:780-866`）：

```python
@device_tool(budget_s=300.0)
def dg_set_dc(...): ...
    # 1) mcp.tool()(wrapper)                      → FastMCP 注册（:806）
    # 2) _register_runtime_operation(...)         → instrument_runtime 注册（:812）
    # 3) schema / description 漂移断言            → :838-856，与 FastMCP 注册路径逐字比对
```

第 3 条是**唯一的契约守卫**：它保证「运行时自描述的 schema」与「FastMCP 真正注册的 schema」
不会分叉。插件化之后，这个断言**必须留在宿主**——插件不能自己声明"我的 schema 是对的"。

建议：`@device_tool()` 保持原样，只把**函数从哪来**改成插件提供：

```python
for plugin in plugins:
    for fn in plugin.tool_functions():        # tools.py 里 @device_tool 装饰好的函数
        device_tool(budget_s=...)（fn）        # 宿主负责装配与断言
```

风险点：`device_tool` 目前靠 `device_for_tool(fn.__name__)`（前缀反查）拿设备名。插件化后
应改成**显式传参** `device_tool(device="dg832", ...)`，把 `DEVICE_BY_PREFIX` 这条隐式规则删掉。
否则插件改个函数名就会静默落到 `instr` 分组里。

分批：先 `dg_*`（12 个，单一命令族、无 GPIB、无子进程，最干净）→ `sds_*`（13）→ 其余按族。
**`ks3458a` 放最后**：它有 worker 子进程隔离（`INSTRUMENT_KS3458A_WORKER`）、SICL 回退、
IFC 总线影响，是所有里最容易搬坏的。

## 七、安全与信任

插件 = 任意 Python 代码，一旦 `import` 就拥有进程的全部权限。所以：

1. **默认只允许内置 + 已安装（entry point）**。本机目录必须显式 `INSTRUMENT_ALLOW_LOCAL_PLUGINS=1`，
   且启动时把加载了哪些本机插件逐条打进日志。
2. **风险等级由插件声明、宿主裁决**。`@op(risk="destructive")` 是声明，`confirm` 的生成、
   `_risk_of_tool()` 的最终值、审计写入都留在宿主。插件不能自报"我很安全"。
3. **破坏性操作清单不开放给插件配置**（`ks3458a_reset`、`psu.power_cycle` 这类），
   沿用现有 `instrument_runtime` 的表。
4. **审计收口不变**：`server.py:430` 的 `_call.audited()` 是唯一出口，插件绕过它就等于绕过审计。
5. **版本闸失败 = 不加载**，不要 try/except 之后继续跑——半加载的插件会让人查一天。

## 八、测试与 CI

新增 `/` 扩充的套件：

| 套件 | 断言 |
|---|---|
| `verify_plugin_manifest.py`（新） | 清单字段齐全、`console_api` 可解析、`driver_class` 可解析、spec 路径存在 |
| `verify_plugin_contract.py`（新） | 每个插件的 `@op` 声明与 `ops.py` catalog 一致；无重复 op 名；无重复 mcp 前缀 |
| `verify_plugin_isolation.py`（新） | 只 import 一个插件不拉起别的插件的设备库；`import instrument_console.drivers` 仍不引入 pyvisa |
| `verify_console_layering.py`（已有） | core 只用标准库 |
| `verify_registry_parity.py`（已有） | 71 条工具描述逐字一致（**基线不许改**，见 §九.1） |
| `regression_offline.ps1`（已有） | 27 套件全绿 |

插件自带的 `tests/` 由宿主统一跑：`python -m pytest instruments/*/tests`（或沿用项目现有的
`TEST_SCRIPTS/` 风格，二选一，不要混）。

## 九、风险与未决

1. **71 个工具名是对外契约**。`verify_registry_parity.py` 逐字比对
   `TEST_DATA/common/mcp_tools_baseline_v2dev.json`（captured_at 2026-10-29T00:11:35，71 条）。
   插件化**不得**改工具名/参数/描述——否则基线整体换版，历史对比全断。P4 的验收就是
   「基线一字不动、71 条仍全绿」。

2. **仓库目前没有 `pyproject.toml`**（只有 `requirements.txt`）。entry point 那套要能生效，
   得先打包发布。短期替代：本机目录 + `sys.path` 注入即可先跑通 P3，entry point 留到有发布
   渠道再说。**不要**为了插件化顺手引入一套打包体系——那是另一个工程。

3. **`common.resolver` 的 kind 是写死的**。插件要声明新 kind（例如新厂商的 `tcpip-socket`），
   `resolver` 得支持动态注册。这一条 P3 之前必须先落，否则插件只能复用已有的 10 个 kind。

4. **循环依赖**：`instrument_console` 依赖 `common.resolver`；插件若反向依赖 `instrument_console`
   的 core，要注意 import 方向（`core` 只用标准库这条铁律会挡住大部分坏方向，是好事）。

5. **横切逻辑不动**：`_mirror_console`、`session_lock`、审计、`budget_s` 预算、
   `_PREWARM_DONE` 那套仍在 `mcp_instruments/`，不跟着插件走。

6. **每机配置不能进插件**：`devices.json` / `last_good_resources.json` 是现场状态，
   插件只声明 `resolver_kind`，**绝不打包地址**。否则换台机器就要改插件包。

7. **权限模型未定**：第三方插件能不能声明 `risk="destructive"`？现在的答案是「能声明、但
   破坏性清单由宿主把关」，够用；真要开放给外部，需要一份签名/白名单策略。

## 十、建议的起点

如果只做一件事：**照 `dg832` 做样板**。

理由：12 个工具、单一命令族（`signal_source_dg`）、USB/VISA 直连、无 GPIB 特殊路径、
无 worker 子进程、无总线副作用。拿它把「清单 → 驱动 → 规范 → 工具面 → 测试」整条链打通，
剩下 9 台就是复制粘贴 + 各自处理特殊性。

反过来，**别从 `ks3458a` 开始**：它是全项目最复杂的一台（非 SCPI、非标准 VISA、worker 隔离、
SICL 回退、IFC 影响整条总线），拿它做样板会把「插件机制的问题」和「3458A 的问题」混在一起。

## 附：本文不涉及的事

* 中控的分层、四个同步、工作集与占用 → 见 `20261109-instrument-console.md`。
* MCP 服务的 profile（compact/legacy）、安全门、启动自检 → 见 `skills/instrument-mcp/SKILL.md`。
* DSH / OpenChamber 的 UI 插件（`plugins/dsh-instrument-console/`）——那是**界面**插件，
  与本文的**仪器**插件不是一回事，命名空间要分开（见 §3.1）。
* 硬编码审计的既有结论 → 见 `docs/hardcode_audit_20261109.md`。

---

**下一步（待用户确认后再动）**：先做 P1（纯去硬编码、零行为变化），跑全量回归；
P1 绿了再决定 P2 要不要一次搬完 10 台。
