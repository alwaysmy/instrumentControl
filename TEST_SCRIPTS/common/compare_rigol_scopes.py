"""比对 RIGOL DHO800/900 与 MHO900 两个系列的**编程命令集**，回答"能否功能合并"。

用法：
    python TEST_SCRIPTS/common/compare_rigol_scopes.py            # 打印摘要 + 留痕
    python TEST_SCRIPTS/common/compare_rigol_scopes.py --full     # 追加打印完整清单

方法（全部离线，判据与 audit_all_commands.py 同一套归一化）：
    ① 两份**编程手册提取版**各自建命令索引（段键元组：逐段取 SCPI 短形式、剥通道选择器）；
    ② 算三个集合：共有 / 仅 DHO / 仅 MHO —— 这是"命令集是否一致"的量化答案；
    ③ 再算两套**驱动实际用到的命令**在两个索引里的命中情况：
       DHO 驱动命令有多少能在 MHO 手册里找到（= 移植到 MHO 的可行性），反之亦然；
    ④ 留痕 TEST_DATA/common/rigol_scope_command_compare_<stamp>.json

注意：命令**名字**一致 ≠ **语义**一致（枚举值、返回格式、默认值仍要看手册）。
本脚本判"名字层"的一致性，语义差异由 `docs/rigol_scope_compare_20260915.md` 逐条记录。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "TEST_SCRIPTS" / "common"))

import audit_all_commands as A  # noqa: E402

DHO_MANUAL = ROOT / "dho_control/docs/DHO800编程手册_output/DHO800编程手册.md"
MHO_MANUAL = ROOT / "mho_control/docs/MHO900编程手册_output/MHO900编程手册.md"
OUT_DIR = ROOT / "TEST_DATA" / "common"
FULL = "--full" in sys.argv


def index_of(manual: Path) -> set[tuple[str, ...]]:
    return A.build_index(manual.read_text(encoding="utf-8"))


def driver_keys(code_dir: Path) -> dict[tuple[str, ...], str]:
    """驱动源码里实际用到的命令：段键 → 首条出处。"""
    out: dict[tuple[str, ...], str] = {}
    for f in sorted(code_dir.rglob("*.py")):
        for cmd, ln, _interp in A.extract_cmds(A.strip_comments(f.read_text(encoding="utf-8"))):
            k = A.norm_head(cmd)
            if k:
                out.setdefault(k, f"{f.relative_to(ROOT)}:{ln}  {cmd}")
    return out


def shorten(keys: tuple[str, ...]) -> str:
    return ":".join(keys)


def main() -> int:
    dho_idx, mho_idx = index_of(DHO_MANUAL), index_of(MHO_MANUAL)
    common = {k for k in dho_idx if A.is_hit(k, mho_idx)}
    dho_only = {k for k in dho_idx if not A.is_hit(k, mho_idx)}
    mho_only = {k for k in mho_idx if not A.is_hit(k, dho_idx)}

    print("=== ① 两套编程手册的命令集关系（名字层）===")
    print(f"  DHO800/900 手册命令键: {len(dho_idx):5d}")
    print(f"  MHO900     手册命令键: {len(mho_idx):5d}")
    print(f"  共有（DHO 键能在 MHO 手册命中）: {len(common):5d}"
          f"  = DHO 的 {len(common) / max(len(dho_idx), 1):.0%}")
    print(f"  仅 DHO 有: {len(dho_only):5d}")
    print(f"  仅 MHO 有: {len(mho_only):5d}")

    def dump(title: str, keys, limit=None):
        print(f"\n--- {title}（{len(keys)}）---")
        items = sorted(shorten(k) for k in keys)
        for s in (items if (FULL or limit is None) else items[:limit]):
            print(f"    {s}")
        if not FULL and limit and len(items) > limit:
            print(f"    …（其余 {len(items) - limit} 条见留痕 JSON）")

    dump("仅 DHO 有（MHO 缺）", dho_only)
    if FULL:
        dump("仅 MHO 有", mho_only)

    print("\n=== ② 两套驱动实际用到的命令 vs 对方手册 ===")
    dho_used = driver_keys(ROOT / "dho_control")
    mho_used = driver_keys(ROOT / "mho_control")
    dho_in_mho = {k for k in dho_used if A.is_hit(k, mho_idx)}
    dho_miss_in_mho = {k for k in dho_used if not A.is_hit(k, mho_idx)}
    mho_in_dho = {k for k in mho_used if A.is_hit(k, dho_idx)}
    mho_miss_in_dho = {k for k in mho_used if not A.is_hit(k, dho_idx)}
    print(f"  DHO 驱动用到 {len(dho_used)} 条命令；其中 {len(dho_in_mho)} 条在 MHO 手册里有同名命令"
          f"（{len(dho_miss_in_mho)} 条没有）")
    print(f"  MHO 驱动用到 {len(mho_used)} 条命令；其中 {len(mho_in_dho)} 条在 DHO 手册里有同名命令"
          f"（{len(mho_miss_in_dho)} 条没有）")
    print("\n  DHO 驱动命令里 MHO 手册**没有**的：")
    for k in sorted(dho_miss_in_mho):
        print(f"    {shorten(k):26s} {dho_used[k]}")
    print("\n  MHO 驱动命令里 DHO 手册**没有**的：")
    for k in sorted(mho_miss_in_dho):
        print(f"    {shorten(k):26s} {mho_used[k]}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"rigol_scope_command_compare_{stamp}.json"
    out.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "dho_manual": str(DHO_MANUAL.relative_to(ROOT)),
        "mho_manual": str(MHO_MANUAL.relative_to(ROOT)),
        "counts": {"dho_keys": len(dho_idx), "mho_keys": len(mho_idx),
                   "common": len(common), "dho_only": len(dho_only), "mho_only": len(mho_only),
                   "dho_driver_cmds": len(dho_used), "dho_driver_in_mho": len(dho_in_mho),
                   "mho_driver_cmds": len(mho_used), "mho_driver_in_dho": len(mho_in_dho)},
        "dho_only": sorted(shorten(k) for k in dho_only),
        "mho_only_sample": sorted(shorten(k) for k in mho_only)[:400],
        "dho_driver_missing_in_mho": {shorten(k): dho_used[k] for k in sorted(dho_miss_in_mho)},
        "mho_driver_missing_in_dho": {shorten(k): mho_used[k] for k in sorted(mho_miss_in_dho)},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n留痕: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
