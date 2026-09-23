# 外部项目怎么用 3458A：SuperResistanceBridge（SRB V0.3）范式与契约

来源：`D:\MyProjects\EmoeR_D\NIM\SuperResistanceBridge\1_FW\SuperResistanceBridge_V0.3_fw_ad7190\`
（`CLAUDE.md` 坑 8、`scripts/tests/voltage_inl_transfer.py`、`docs/gpt_qa/20260919-voltage-test-spec.md`）
——它是本库 `keysight_3458a` 的**第一个真实下游用户**，2026-09-23 的适配器卡死事故就发生在这里。

## 1. 干什么用：把 3458A 当"源的实测真值"（传递法）

| 项 | 做法 |
|---|---|
| 被测 | SRB V0.3 的 ADC 前端（AD7190 / LHA9954），测**电压 INL / 传输线性度** |
| 激励 | EmoeCalibrator（±10 V 档），逐点设值 |
| **3458A 的角色** | **逐点同步回读源的"实际输出"**，INL 拟合的 x 轴用 `V_3458A`，而不是源设定值 |
| 为什么要它 | 传递法扣掉源的非线性 → 残差只反映 ADC 自身 INL；源设定值只作控制/诊断 |
| 采样口径 | 每个测试点等建立时间；全程 **aperture/NPLC 固定**；扫描做 ascending / descending / randomized 三组（查迟滞） |
| 时长/平均 | 0 V 连续记录 1~2 h 做 Allan deviation 定平均时间 |

**逐点数据 = （ADC 码值 `MEAS:CODE?`，3458A 读数 `V_3458A`）**，两者配对后拟合。

## 2. 他们调本库的固定顺序（`voltage_inl_transfer.py::_3458a_selfcheck`）

```python
# ① PATH 必须在 import keysight_3458a **之前**注入（他们的硬要求，见 §3 坑 1）
for d in (r"C:\Program Files\Keysight\IO Libraries Suite\bin",
          r"C:\Program Files\IVI Foundation\VISA\Win64\bin",
          r"C:\Program Files\IVI Foundation\VISA\Win64\ktvisa\ktbin"):
    if os.path.isdir(d):
        os.environ["PATH"] = d + ";" + os.environ.get("PATH", "")

from keysight_3458a import DMM3458A as _D      # 延迟 import：PATH 就绪后才加载 DLL
d = _D("GPIB0::9::INSTR")
d.connect(recover=True)                        # ② **强制完整恢复**（他们的原话：
                                               #    "free-run 时轻量路径会写超时"）
assert "3458" in d.idn().upper()               # ③ 身份校验
err = d.error_string()                         # ④ 错误队列必须干净（0,"NO ERROR"）
d.configure_dcv(range_v, nplc)                 # ⑤ 按测试口径配置（固定 NPLC）
# ⑥ 与另一台表（N90）在同一点对读核对 → 任一步失败**中止**，不静默降级
```

**扫描/传递类测试只用 `TARM SGL,1` 单次读数**（他们的明文规定），**不用** `ks3458a_burst`。

## 3. 他们踩过的坑 → 对我们库的要求

| # | 他们的记录（`CLAUDE.md` 坑 8） | 我们现在的状态 |
|---|---|---|
| 1 | **必须 import 前把 Keysight/IVI 目录注入 `PATH`**，否则 `viOpen` 在 `ktvisa32.dll` 内抛 **`0xE06D7363`**（而 `viOpenDefaultRM`/`viFindRsrc` 却成功，极难定位）；"MCP 进程自带该 PATH，所以 MCP 一直能用而脚本不能" | 本库 `prepare_keysight_visa()` 已**自己在内部做**（`add_dll_directory` + `SetDllDirectoryW(套件 bin)` + 预加载 `ioGPIB.dll`/`ioGpibIntfc.dll`）→ **脚本不必再手动改 PATH**；保留兼容（脚本愿意注入也不冲突） |
| 2 | **`ks3458a_burst` 会在 `ioGPIB` 层卡死**（n=10 也卡）并让 82357B 进异常态：之后任何会话 `viOpen` 都抛 `0xE06D7363`，`pnputil /restart-device` 无效（系统要求重启），**须拔插 USB** | 已三层加固：① burst 超时按 `n×采样间隔` 有界（10~180 s）② 收尾/`PRESET NORM` 进 `finally` ③ **I/O 跑在可 kill 的 worker 子进程**（超时 `kill` → 句柄回收 → 自动重启）。**但仍建议扫描类测试用单次读数**（他们的口径） |
| 3 | 排障口径：`viOpen` 成功 + `viReadSTB` 返回 **`-1073807343 (RSRC_NFOUND)`** ⇒ 接口卡正常但**该地址无设备**（查表电源/GPIB 排线）；返回 **`-1073807339 (TMO)`** ⇒ 设备在但不应答（多因被留在 free-run，用 `connect(recover=True)`） | 已写进 `preflight` 的分层判据与 skill（第 [4] 应答层） |
| 4 | 自检**任一步失败即中止，不静默降级** | 与本库原则一致（读数非数值一律报错，不返回 0 兜底） |

## 4. 给下游项目的最短接入建议（对应他们的痛点）

```python
from keysight_3458a.remote import RemoteDMM          # 进程外代理（推荐给长驻/混合用途的脚本）
with RemoteDMM("GPIB0::9::INSTR") as d:              # 或 RemoteDMM(..., deadline_s=...)
    d.connect(recover=True)                          # 扫描类：完整恢复更稳
    v = d.read_dcv()                                 # 单点；多点用 d.read_series(n)
```

* **同一脚本内还要用别的 VISA 仪器（pyvisa）** → 必须用 `RemoteDMM`：进程内混用两套 VISA 会串味
  （见 `docs/3458a_wedge_postmortem_20260923.md` §10）；
* **只读单点/短序列** → `DMM3458A` 直连即可（少了 ~0.4 s 进程开销）；
* 需要"每点同步配对"（源设值 + ADC 码 + 3458A 读数）时：**一次会话内循环 `read_dcv()`**，
  不要每点重连（`connect` 约 0.27 s，重连会拖慢 201 点扫描）。
