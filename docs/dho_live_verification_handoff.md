# DHO 真机复验交接单（MHO/DHO 合并后）

> **给"有 DHO 的那一侧"的测试单**。本次合并把 DHO800/900 与 MHO900 并到了同一内核
> `rigol_scope/`（依据见 `docs/rigol_scope_compare_20260915.md`），但**合并这台机器上
> 没有 DHO**（LAN 扫描只有 MHO 192.168.1.55），所以 DHO 路径只做了离线验证
> （`TEST_SCRIPTS/common/verify_rigol_scope_shared.py`，假传输回放，74 断言）。
> 请在接有 DHO 的机器上按本单跑一遍，把结果回填到 §四。

## 一、准备

```bash
cd <仓库根>
pip install -r requirements.txt          # pyvisa（完整版 NI-VISA）
python mcp_instruments/config_cli.py show                 # 看解析链现状
python mcp_instruments/config_cli.py set dho <DHO的IP>    # 裸 IP 会自动探测协议 + 核对 *IDN? 后落库
# 或者：先跑一次 instr_discover（发现结果会按 *IDN? 自动回写缓存）
```

DHO 常见资源串形态（不要手拼，交给 `config_cli.py set`）：

```
TCPIP0::<host>::5555::SOCKET     # RIGOL raw socket（DHO 实测只认这个口）
TCPIP0::<host>::inst0::INSTR     # 部分固件也开 VXI-11
USB0::0x1AB1::<pid>::<serial>::INSTR
```

**先跑离线回归**（不碰仪器，确认代码本身没问题）：

```bash
python TEST_SCRIPTS/common/verify_rigol_scope_shared.py    # 期望：全部 PASS（74 断言）
python TEST_SCRIPTS/common/verify_audit_extractor.py       # 期望：全部 PASS
```

## 二、推荐做法：一条命令跑完（脚本已写好）

```bash
python TEST_SCRIPTS/dho/verify_dho_after_merge.py                # 默认只读
python TEST_SCRIPTS/dho/verify_dho_after_merge.py --allow-write  # 追加会改设定的 2 项（自动恢复）
python TEST_SCRIPTS/dho/verify_dho_after_merge.py --allow-stop   # 追加 RAW（短暂冻结采集）
```

脚本逐项判定并写留痕 `TEST_DATA/dho/verify_dho_after_merge_<stamp>.json`；
**哪一项不符，脚本会直接在输出里告诉你改 `rigol_scope/families.py` 的哪个字段**（见 §三）。
把该 JSON 按 §四 回填即可；地址没找到时它会打印定位设备的命令，而不是抛栈。

下面的 6 项明细就是它检查的内容，想手工核对时按此表逐步做。

## 二·附、6 项检查明细（合并带来的 DHO 行为变更）

> 这些是合并后 **DHO 侧行为有变化** 的地方。逐条跑、逐条记结果；任何一条不符，
> 按 §三 的说明改 `rigol_scope/families.py` 一个字段即可，不必改内核。

| # | 检查项 | 怎么跑 | 期望 |
|---|---|---|---|
| ① | 清测量命令 | `dho_measure_item(VPP,1)` 打开一项，再 `python -c "import sys;sys.path.insert(0,'.');from dho_control import DHO;from common.resolver import resolve;s=DHO(resolve('dho'));s.connect();s.measure_clear();print(s.system_error() or 'no error')"` | 无错误；`:MEASure:CLEar` 被接受（DHO 手册命令） |
| ② | 采集第四态 | `s.acquire_type("ULTRa")` → 查错 → `s.acquire_type()` | 写入被接受、回读为 ULTRa（**不是** HRESolution，那是 MHO 的） |
| ③ | **波形 ASCII 是否带 TMC 头** | `s.stop(); wf=s.get_waveform(1, fmt="ASCii", points=1000); print(wf["points"])` | 期望能正常解析出 ~1000 点。**若抛 `非法 TMC 头`** → 说明 DHO 的 ASCII 带 TMC 头，把 `families.py` 里 DHO 的 `ascii_waveform_has_tmc` 改成 `True` |
| ④ | 截屏 | `png=s.screenshot_png(Path("TEST_DATA/dho/shot.png")); print(png.stat().st_size, png.read_bytes()[:8])` | 魔数 `b'\x89PNG\r\n\x1a\n'`，体积数十~数百 KB（可直接 Read 看图） |
| ⑤ | 双信源测量（新能力） | `s.measure_item("RRPHase", 1, 2)`（两通道都接同一信号时） | 有值（两路同源时应接近 0°）；两通道无信号时报"无有效值"属正常 |
| ⑥ | RAW 内存波形 | `s.stop(); wf=s.get_waveform(1, mode="RAW", fmt="BYTE", points=50000)` | 返回 50000 点；`xinc ≈ 1/采样率`（`s.sample_rate()`） |

补充回归（合并前就有、合并后不应退化）：

```bash
# DHO 原有读写/波形路径
python TEST_SCRIPTS/dho/test_dho_read.py
python TEST_SCRIPTS/dho/test_dho_first.py
# 可选：写入类（会改设定，脚本内 try/finally 恢复）——确认插上的是空通道再跑
python TEST_SCRIPTS/dho/test_dho_write.py
```

## 三、期望与实际不符时改哪里

| 症状 | 原因 | 改法 |
|---|---|---|
| ③ 报"非法 TMC 头" | DHO 的 ASCII 带 TMC 头（与 MHO 不同） | `rigol_scope/families.py` → `DHO(... ascii_waveform_has_tmc=True ...)` |
| ② 写第四态被拒（-200/-113） | DHO 的第四态名字与手册不一致 | 改 `families.py` 里 DHO 的 `acq_types`（同时改 `dho_control/commands.py` 注释并跑审计器） |
| ① 清测量报错 | DHO 实际用的是 `:MEASure:DELete` | 改 `families.py` 里 DHO 的 `measure_clear` |
| 波形点数/幅度明显不对 | 采样率或档位与预期不符 | 先 `dho_status` 看实际配置，再核对 `preamble()` 的 `yinc/yref` |
| **读数与设备测量差 10%~30%** | 很可能是 **BYTE 格式的 8bit 量化**（每码 = Vpp/码值数） | 用 `fmt="WORD"` 重读再比；这是已知特性，见 AGENTS.md 铁律#9 |

> 改完任一处，请重跑 `verify_rigol_scope_shared.py`（离线）与
> `verify_audit_extractor.py`，并把留痕 JSON 一并回填。

## 四、回填格式（贴回本文件或 issue）

```
环境：<OS> / python <版本> / NI-VISA <版本>
DHO：*IDN? = <原文>；资源串 = <解析层给出的值>（不要手写 IP 到文档里）
① 清测量      PASS/FAIL  <实际输出>
② 第四态      PASS/FAIL  <回读值>
③ ASCII 头    PASS/FAIL  <点数 / 报错原文；若 FAIL 说明改后的字段值>
④ 截屏        PASS/FAIL  <魔数 + 字节数>
⑤ 双信源      PASS/FAIL  <度数>
⑥ RAW         PASS/FAIL  <点数 + xinc + 采样率>
留痕：TEST_DATA/dho/....json / .png
```

## 五、附：本次合并对 DHO 的具体改动（便于对照）

1. `dho_control/dho.py` 从"自带全部实现"改为薄封装（`class DHO(RigolScope)`，
   `FAMILY = rigol_scope.DHO_FAMILY`）——**公开 API 与签名未变**（`DHO(...)`、`connect()`、
   `idn()`、`snapshot()`、`measure_item()`、`get_waveform()`、`channel_*`、`timebase_*`、
   `edge_*`、`acquire_*`、`run/stop/single/force_trigger/clear/autoset`、`find_dho()`、
   `resolve_model()`）。
2. 新增能力：`measure_clear()`、`screenshot()/screenshot_png()`、`measure_item(..., src2=)`
   双信源、波形分片读取、`points` 上限与 RAW/STOP 前置校验、`channel_impedance()`（MHO 专有，
   DHO 调用会明确报错而非静默失败）。
3. **删除** `DHO.reset()`（`:SYSTem:RESet` 属 AGENTS.md 禁发命令；需要复位请走测试脚本 +
   显式授权）。
4. 修复：`get_waveform(fmt="ASCii")` 此前恒抛异常（`fmt.upper()` 后与混合大小写字面量比较
   的死分支）。
5. **未变**：`dho_control/commands.py` 的常量仍是命令拼写的唯一维护点，仍被审计器按 DHO 手册
   逐条核对（当前 39 HIT / 0 MISS）。
