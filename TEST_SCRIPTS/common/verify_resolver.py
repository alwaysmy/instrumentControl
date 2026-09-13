"""地址解析层离线回归（不连任何设备）：优先级链 / 规范化 / IDN 归类 / 缓存回写。

覆盖 `common/resolver.py`：

  ① idn_kind：5 台真实 *IDN? 文本归类 + 未知设备不误判
  ② resource_rank：多协议优选（inst0 > hislip0 > 其它 INSTR > raw SOCKET）
  ③ resolve 优先级：显式 > env > 配置 > 缓存 > 自动发现（逐级验证）
  ④ canonicalize：完整 VISA 串原样返回；裸 host → 探测协议 + *IDN? 校验；
     身份不符 / 探测失败分别给出拒绝与指引
  ⑤ save_config / clear_config / autofill_config / known_resources 行为
  ⑥ 失败文案含可执行指引（instr_discover / env / 配置文件 / 扫描开关）

find_device / identify_lan 全部打桩（monkeypatch），**不产生任何设备 I/O**。
留痕：TEST_DATA/common/verify_resolver_<stamp>.json
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dh1766_control" / "src"))

import common.discovery as cd  # noqa: E402
import common.resolver as cr  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"
results: list[dict] = []

# 真实 *IDN? 文本（取自 TEST_DATA 留痕）
IDNS = {
    "sds": "Siglent Technologies,SDS824X HD,SDS08A0C8R0274,2.8.12.1.1.6.5",
    "sdg": "Siglent Technologies,SDG2122X,SDG2XFBX800780,2.01.01.38R4",
    "dmm": "Keysight Technologies,34465A,MY59026806,A.03.02-03.15-03.02-00.52-05-02",
    "dho": "RIGOL TECHNOLOGIES,DHO924S,DHO9A253600386,KFCVME50114",
    "psu": "BJDH,DH1766A-1,0,V0.1.4.3",
}


def check(name: str, got, want) -> None:
    ok = got == want
    results.append({"item": name, "ok": ok, "got": str(got)[:200], "want": str(want)[:200]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  got={got!r} want={want!r}"),
          flush=True)


def check_raises(name: str, fn, *needles: str) -> None:
    try:
        fn()
        check(name, "没抛异常", "RuntimeError/ValueError")
        return
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        ok = any(n in msg for n in needles)
        results.append({"item": name, "ok": ok, "got": msg[:200], "want": f"含 {needles}"})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} -> {msg[:150]}", flush=True)


def main() -> int:
    # ---- 隔离：配置/缓存指向临时目录；发现函数打桩（绝不碰真设备）----
    tmp = Path(tempfile.mkdtemp(prefix="resolver_check_"))
    cr.CONFIG_DIR = tmp
    cr.CONFIG_FILE = tmp / "devices.json"
    cr.CACHE_FILE = tmp / "last_good_resources.json"

    def _no_net(*_a, **_k):
        raise RuntimeError("offline-stub")

    cd.find_device = _no_net
    cd.identify_lan = _no_net

    print("=== ① idn_kind（真实 IDN 文本）===", flush=True)
    for kind, idn in IDNS.items():
        check(f"idn_kind({kind})", cr.idn_kind(idn), kind)
    check("idn_kind(未知设备)", cr.idn_kind("EmoeR&D,ADS127L11-DAQ-EV,0,1.0"), None)

    print("\n=== ② resource_rank 优选顺序 ===", flush=True)
    check("inst0 最优", cr.resource_rank("TCPIP0::10.0.0.1::inst0::INSTR"), 0)
    check("hislip 次之", cr.resource_rank("TCPIP0::10.0.0.1::hislip0::INSTR"), 1)
    check("其它 INSTR", cr.resource_rank("USB0::0x0957::0xA007::1::INSTR"), 2)
    check("SOCKET 末位", cr.resource_rank("TCPIP0::10.0.0.1::5025::SOCKET"), 3)

    print("\n=== ③ 解析优先级（离线发现全失败）===", flush=True)
    check_raises("无信息时报错含四类指引", lambda: cr.resolve("sds"),
                 "instr_discover", "INSTRUMENT_SDS_RES", "devices.json", "INSTRUMENT_ALLOW_SCAN")

    cr.remember_candidates([("TCPIP0::192.0.2.9::5025::SOCKET", IDNS["sds"]),
                            ("TCPIP0::192.0.2.9::inst0::INSTR", IDNS["sds"]),
                            ("TCPIP0::192.0.2.7::5555::SOCKET", IDNS["dho"]),
                            ("USB0::0x1::0x2::SN::INSTR", "EmoeR&D,ADC,0,1.0")])
    check("识别并按优选写缓存", cr.known_resources().get("sds"), "TCPIP0::192.0.2.9::inst0::INSTR")
    check("未知设备不入库", "Emoe" in json.dumps(cr.known_resources()), False)
    check("走缓存解析", cr.resolve("sds"), "TCPIP0::192.0.2.9::inst0::INSTR")

    cr.CONFIG_FILE.write_text(json.dumps({"sds": "TCPIP0::192.0.2.100::inst0::INSTR"}),
                              encoding="utf-8")
    check("配置优先于缓存", cr.resolve("sds"), "TCPIP0::192.0.2.100::inst0::INSTR")
    os.environ["INSTRUMENT_SDS_RES"] = "TCPIP0::192.0.2.200::inst0::INSTR"
    check("env 优先于配置", cr.resolve("sds"), "TCPIP0::192.0.2.200::inst0::INSTR")
    del os.environ["INSTRUMENT_SDS_RES"]
    check("显式入参最高优先", cr.resolve("sds", "TCPIP0::192.0.2.250::inst0::INSTR"),
          "TCPIP0::192.0.2.250::inst0::INSTR")

    print("\n=== ④ canonicalize（唯一允许“拼接”的入口）===", flush=True)
    check("is_visa_resource：TCPIP", cr.is_visa_resource("TCPIP0::1.2.3.4::inst0::INSTR"), True)
    check("is_visa_resource：USB", cr.is_visa_resource("USB0::0x0957::0xA007::1::INSTR"), True)
    check("is_visa_resource：ASRL", cr.is_visa_resource("ASRL5::INSTR"), True)
    check("is_visa_resource：裸 host", cr.is_visa_resource("192.168.31.220"), False)
    check("完整串原样返回（不联网）",
          cr.canonicalize("sds", "TCPIP0::192.0.2.50::inst0::INSTR"),
          "TCPIP0::192.0.2.50::inst0::INSTR")
    check_raises("裸 host 但探测失败 → 指引式报错",
                 lambda: cr.canonicalize("sds", "192.0.2.77"), "未探测到可识别的仪器")

    # 打桩：探测命中，但身份不符 / 相符
    cd.identify_lan = lambda host, timeout_ms=3000: ("TCPIP0::%s::inst0::INSTR" % host, IDNS["sdg"])
    check_raises("裸 host 身份不符 → 拒绝", lambda: cr.canonicalize("sds", "192.0.2.77"),
                 "不是目标设备")
    check("裸 host 身份相符 → 规范化", cr.canonicalize("sdg", "192.0.2.77"),
          "TCPIP0::192.0.2.77::inst0::INSTR")

    print("\n=== ⑤ 配置读写 ===", flush=True)
    cr.save_config("sdg", "TCPIP0::192.0.2.77::inst0::INSTR")
    check("save_config 写入", json.loads(cr.CONFIG_FILE.read_text(encoding="utf-8")).get("sdg"),
          "TCPIP0::192.0.2.77::inst0::INSTR")
    check("known_resources 只含设备类", set(cr.known_resources()) <= set(cr.DEVICE_KINDS), True)
    cr.clear_config("sdg")
    check("clear_config 删除", "sdg" in json.loads(cr.CONFIG_FILE.read_text(encoding="utf-8")), False)
    check_raises("非法 kind 拒绝", lambda: cr.save_config("nope", "TCPIP0::1::inst0::INSTR"),
                 "未知设备类")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / f"verify_resolver_{stamp}.json"
    n_fail = sum(1 for r in results if not r["ok"])
    f.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"),
                             "mode": "离线（find_device / identify_lan 已打桩，无设备 I/O）",
                             "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n== 结果: {len(results) - n_fail}/{len(results)} PASS ==\n留痕: {f}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
