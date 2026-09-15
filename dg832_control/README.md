# dg832_control — RIGOL DG800 系列信号源（DG832 基准）

本目录是 **DG832 控制的唯一维护点**（2026-09-15 合并）。

| 文件 | 说明 |
|---|---|
| `dg832.py` | 驱动器本体（原样迁入，未改一行；含保护联锁 / DC 快照 / 扫频 / 频率计 / CLI） |
| `__init__.py` | 对外导出（`DG832` / `discover` / 异常类 / `MODEL_REGISTRY`） |
| `docs/DG832使用笔记.md` | 使用笔记（型号对照、快速上手、踩坑记录） |
| `docs/00_快速指南.txt`、`01_用户手册.txt`、`02_编程手册.txt` | 原厂手册文本（**命令出处的审计参照物**：`02_编程手册.txt`） |

## 迁移说明（为什么只有这一份）

合并前同一份 `dg832.py` 存在**三处副本**（逐字节相同，md5 `d1e33622d2a8…`）：

1. `D:\ChatWorkspace\DG832使用\dg832.py`
2. `D:\ChatWorkspace\DG832使用\skill\dg832-control\scripts\dg832.py`
3. `C:\Users\dell\.agents\skills\dg832-control\scripts\dg832.py`

三份 + 两个 MCP 包装（`mcp_dg832/server.py` 与 skill 内的 `mcp_server.py`）正是
`AGENTS.md` 待办里"skill/scripts 双副本需人工同步"的来源。现统一为：

- **库**：本目录 `dg832.py`；
- **MCP**：并入 `mcp_instruments/server.py` 的 `dg_*` 工具（不再单独跑 `instrument` 服务器）；
- **skill**：`~/.agents/skills/dg832-control/SKILL.md` 改为指向本仓（不再带脚本副本）；
- **旧位置**：`D:\ChatWorkspace\DG832使用\` 的 `mcp_dg832/`、`skill/`、以及 skill 内的
  `scripts/` 均已退役删除（用户 2026-09-15 指示"这个就不再单独维护"）。

## 与仓库其它库的差异（有意保留）

- **模型注册表**：DG800 全系列同命令集（DG811/812/821/822/831/832），故工具带 `model`
  参数（默认 `DG832`，未登记型号返回 `model_unsupported`）。
- **保护联锁（protect）**：设置幅度/偏移、打开输出前必须已开启有效电压保护
  （`state=True` 且 `high>low`），否则 `protect_required`；这是本库自带的**硬件防超压**设计，
  合并时原样保留（比仓库其它信号源的 `expect_load` 声明更强）。
- **DC 切换**：`set_dc_only()` 返回切换前快照，切回时要求**显式**传参，不做隐式恢复。

## 台面基线（原工作区 `reset_baseline.py` 记录的现场状态）

收工想把设备还原成"接手时那样"，就按这个来（原脚本已随工作区归档，值抄在这里）：

| 通道 | 波形 | 参数 | 电压保护 |
|---|---|---|---|
| CH1 | DC | 电平 2 V | **ON** |
| CH2 | SIN | 1 kHz / 5 Vpp | OFF |

对应命令（先开保护再设波形，库内联锁）：

```python
gen.set_voltage_limit(1, state=True)      # CH1 保护 ON
gen.set_wave(1, "dc", offset=2.0)         # DC 电平走 offset
gen.set_wave(2, "sine", 1000, 5.0)        # 5 Vpp（保护 OFF 时设幅度会被拒 → 先开再关）
gen.set_voltage_limit(2, high=5, low=-5, state=True)
gen.set_wave(2, "sine", 1000, 5.0)
gen.set_voltage_limit(2, state=False)     # CH2 保护 OFF
```

现成的写路径回归（会改设定并自动恢复）：`TEST_SCRIPTS/dg832/test_dg832_write_matrix.py --allow-write`。

## 安全约定（与 AGENTS.md 一致）

- 输出开关（MCP `dg_output`）**需 `confirm=True`**：关断同样可能打断正在进行的测试；
- 改变输出状态前先 `dg_status` 查通道配置/输出开关/负载；
- 脚本必须 `try/finally` 恢复被改设定并关闭输出；留痕到 `TEST_DATA/dg832/`。
