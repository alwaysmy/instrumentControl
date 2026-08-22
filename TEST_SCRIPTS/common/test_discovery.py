"""common 统一发现层冒烟测试（离线/在线场景自适应，无需设备也可跑）。

用法：
    python TEST_SCRIPTS/common/test_discovery.py [--full-cidr]

用例：
    T1 显式 resource 不存在（TEST-NET 保留地址）→ 期望 RuntimeError 快速失败且链路完整
    T2 显式 resource 在线但 IDN 不匹配（取本机任一在线仪器）→ 期望 ValueError 不 fallback
    T3 无参查找 DH1766 → 在线则 listed 命中，离线则期望 RuntimeError（均为合法结局）
    T4 detect_cidr + scan_cidr 机制冒烟（默认本机附近 /29 小段；--full-cidr 扫整个 /24）

输出：TEST_DATA/common/discovery_smoke_<时间戳>.json 留痕（逐用例 PASS/FAIL 与耗时）。
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.discovery import (  # noqa: E402
    detect_cidr,
    find_device,
    identify,
    list_resources,
    scan_cidr,
)

OUT_DIR = ROOT / "TEST_DATA" / "common"


def run_case(
    results: list[dict],
    name: str,
    expect_desc: str,
    fn,
    expect_exc: type[Exception] | None = None,
) -> None:
    """执行用例并按 expect_exc 判定：无异常且 expect_exc 为 None，或异常类型匹配才算 PASS。"""
    t0 = time.monotonic()
    try:
        detail = fn()
        ok = expect_exc is None
        if not ok:
            detail = f"未按预期抛 {expect_exc.__name__}，实际正常返回: {detail}"
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        ok = isinstance(e, expect_exc) if expect_exc else False
    elapsed = round(time.monotonic() - t0, 2)
    results.append(
        {
            "case": name,
            "expect": expect_desc,
            "ok": ok,
            "elapsed_s": elapsed,
            "detail": str(detail)[:500],
        }
    )
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} ({elapsed}s)")
    print(f"         {str(detail)[:200]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-cidr", action="store_true", help="T4 扫描整个 /24（约 15~20s）")
    args = parser.parse_args()

    results: list[dict] = []
    print("== common.discovery 冒烟 ==")

    # 本机在线仪器清单（identify 内建超时兜底）
    online = []
    for r in list_resources():
        idn = identify(r)
        print(f"  [资源] {r} -> {idn or '(no response)'}")
        if idn:
            online.append((r, idn))

    # T1: 显式指定不存在地址（RFC5737 TEST-NET-1，保证不命中真实设备）
    def t1():
        find_device(
            "NO_SUCH_DEVICE_XYZ",
            resource="TCPIP0::192.0.2.123::inst0::INSTR",
            timeout_ms=1500,
        )

    run_case(results, "T1 显式不存在地址", "RuntimeError(含尝试链路)", t1, expect_exc=RuntimeError)

    # T2: 在线设备但 IDN 不匹配 → 必须拒绝而非静默换设备
    if online:
        res2, idn2 = online[0]

        def t2():
            find_device("NO_SUCH_DEVICE_XYZ", resource=res2, timeout_ms=3000)

        run_case(
            results,
            f"T2 在线但 IDN 不匹配({res2})",
            "ValueError(拒绝自动换设备)",
            t2,
            expect_exc=ValueError,
        )
    else:
        results.append(
            {"case": "T2 在线但 IDN 不匹配", "expect": "-", "ok": True,
             "note": "SKIP: 本机无可识别在线设备"}
        )
        print("  [SKIP] T2（本机无可识别在线设备）")

    # T3: 无参查 DH1766 —— 在线则应命中 listed，离线则应明确失败
    dh1766_online = any(i and "DH1766" in i.upper() for _, i in online)

    def t3():
        hit = find_device("DH1766", timeout_ms=3000)
        return f"source={hit.source} {hit.resource} -> {hit.idn}"

    run_case(
        results,
        "T3 无参查 DH1766",
        "FindResult(listed)" if dh1766_online else "RuntimeError(设备离线)",
        t3,
        expect_exc=None if dh1766_online else RuntimeError,
    )

    # T4: 网段扫描机制冒烟（验证并发扫描/留痕打印/空结果处理）
    def t4():
        seg = detect_cidr()
        assert seg, "detect_cidr 返回空"
        print(f"\n         [T4] 探测网段: {seg}")
        if args.full_cidr:
            net = seg
        else:
            base_ip = ipaddress.ip_interface(f"{seg.split('/')[0]}/24").ip
            net_int = int(base_ip) - int(base_ip) % 8
            net = str(ipaddress.ip_network((net_int, 29), strict=False))
        hits = scan_cidr(net, "DH1766")
        return f"net={net} 在线: {[(h.resource, h.idn) for h in hits] or '无'}"

    run_case(results, "T4 CIDR 扫描机制", "正常返回(在线列表可为空)", t4)

    out_dir = OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "full_cidr": args.full_cidr,
        "online_devices": [{"resource": r, "idn": i} for r, i in online],
        "results": results,
    }
    out_file = out_dir / f"discovery_smoke_{stamp}.json"
    out_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    n_fail = sum(1 for r in results if not r["ok"])
    print(f"\n== 结果: {len(results) - n_fail}/{len(results)} PASS, {n_fail} FAIL ==")
    print(f"留痕已保存: {out_file}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
