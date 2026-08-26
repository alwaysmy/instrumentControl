---
name: instrument-mcp
description: instrument MCP 服务器使用指引 — 五台仪器（SDS 示波器/SDG 信号源/Keysight 34465A 万用表/DHO 示波器/DH1766 电源）的 MCP 工具选择、参数语义、安全门、典型工作流。触发条件：使用 instrument MCP 工具、sds_/sdg_/dmm_/dho_/psu_ 前缀工具、仪器测量/定标/截图/关机决策。
---

# instrument MCP 使用指引

MCP server：`mcp_instruments/server.py`（17 工具，五台设备）。
本文是 AI 选择工具/参数时的决策依据。

## 一、工具选择决策树

```
需要知道有哪些设备在线？
  → instr_discover（LAN 网段 + USB/GPIB/串口全探测；串口被占用给提示，
    驱动挂起 6s 硬超时；代理 fake-IP 干扰 LAN 时降级 warning 不影响 VISA 结果）

示波器（SDS）：
  看波形显示是否正常 → sds_diagnose（触发链路）→ 异常则 sds_auto_scale
  读测量值 → sds_measure（item 见下）
  判断削顶/居中/有无波形 → sds_screenshot（设备测量值超屏被钳制不可信）
  全量状态 → sds_status

信号源（SDG）：
  设波形 → sdg_set_wave（不动输出开关）
  开/关输出 → sdg_output（on=True 必须 confirm=True）
  看当前配置 → sdg_status

万用表（DMM）：
  测量 → dmm_measure（先 dmm_configure 设功能/量程更稳）
  看配置 → dmm_status

DHO 示波器 → dho_status / dho_measure_item
电源（DH1766）→ psu_status / psu_measure
```

## 二、参数语义速查

| 工具 | 参数 | 语义 |
|---|---|---|
| sds_auto_scale | ch=1-4；use_autoset | **use_autoset=True 破坏性**（重置所有通道），仅简单周期信号+无其他已调通道时用 |
| sds_measure | item | SDS 缩写：PKPK/MAX/MIN/AMPL/RMS/PER/FREQ/PWID/DUTY/RISE...；ch=1-4 |
| sds_measure | 无信号测 FREQ | 超时报 device_error（正常现象，非故障） |
| sdg_set_wave | wvtp | SINE/SQUARE/RAMP/PULSE/NOISE/DC；amp_v 高阻下即 Vpp |
| sdg_output | on=True | **必须 confirm=True**（真实信号） |
| dmm_measure | function | volt_dc/volt_ac/curr_dc/curr_ac/res/fres/cont/cap/diod/freq |
| dmm_configure | range_v | 设定量程后 :CONF? 回读滞后一拍，以实测为准 |
| dho_measure_item | item | RIGOL 长名：VPP/VMAX/VAVG/PERiod/FREQuency...；无值返回 9.9E37 |
| psu_* | 三路 | CH1-3；带载读数即实际输出；上电后 ≥2s 再读（过渡态） |

## 三、安全门

| 工具 | 门 | 说明 |
|---|---|---|
| sds_shutdown | confirm=True | 设备离线需面板手动开机 |
| sdg_output(on=True) | confirm=True | 真实信号输出 |
| （未暴露）| — | 复位类命令一律不可用 |

## 四、典型工作流

**信号链验证**（SDG 输出 → SDS 测量）：
1. `sdg_set_wave(ch=2, wvtp="SINE", freq_hz=1000, amp_v=2)` 
2. `sdg_output(ch=2, on=True, confirm=True)`
3. `sds_auto_scale(ch=4)`（信号接在 C4）
4. `sds_measure(item="PKPK")` + `sds_measure(item="FREQ")` 断言
5. 结束 `sdg_output(ch=2, on=False)`

**示波器无波形**：
1. `sds_diagnose` 看触发源/电平/模式
2. `sds_auto_scale` 修正
3. `sds_screenshot` 像素确认（测量值超屏被钳制不可信）

## 五、错误处理

统一返回 `{ok, error_type, error}`：
- `confirm_required`：补 confirm=True 重试
- `param_validation`：改参数（枚举/范围错）
- `connection`：设备离线（instr_discover 确认）
- `device_error`：设备拒绝/测量超时（读 error 文本，多为信号/触发问题）
- `communication`：IO 异常（重试一次，仍失败检查连接）
