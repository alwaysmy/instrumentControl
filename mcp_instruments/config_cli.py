"""仪器地址配置 CLI：查看 / 写入 / 清除**本机**地址配置（不开设备会话）。

用法（在仓库根目录执行）：

    python mcp_instruments/config_cli.py show                  # 当前解析链（配置/缓存/来源）
    python mcp_instruments/config_cli.py init [--force]        # 生成配置模板（不含真实地址）
    python mcp_instruments/config_cli.py set sds TCPIP0::<ip>::inst0::INSTR
    python mcp_instruments/config_cli.py clear sds             # 删除条目 → 回落自动发现

配置文件：`%LOCALAPPDATA%\\instrumentControl\\devices.json`（本机专用、不入库、
可手改）。键 = 设备类 sds/sdg/dmm/dho/psu，值 = 完整 VISA 资源串。
解析优先级：显式入参 > 环境变量 INSTRUMENT_<KIND>_RES > 本文件 > 上次成功缓存 >
自动发现（`common/resolver.py::resolve`）。

注意：本 CLI **只读写本机配置/缓存文件，不连接任何仪器**（`show` 也不会触发发现）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.resolver import (  # noqa: E402
    CACHE_FILE,
    CONFIG_DIR,
    CONFIG_FILE,
    DEVICE_KINDS,
    clear_config,
    config_template,
    explain,
    save_config,
)

USAGE = ("用法: python mcp_instruments/config_cli.py "
         "[show | init [--force] | set <kind> <resource> | clear <kind>]")


def _write_template(force: bool) -> int:
    if CONFIG_FILE.exists() and not force:
        print(f"配置文件已存在，未覆盖（要重置加 --force）: {CONFIG_FILE}")
        return 1
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    import json

    tmp.write_text(json.dumps(config_template(), ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(CONFIG_FILE)
    print(f"已生成模板（不含真实地址；留空/删键即回落到自动发现）:\n  -> {CONFIG_FILE}")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "show"

    if cmd == "show":
        print(f"配置目录: {CONFIG_DIR}")
        print(f"配置文件: {CONFIG_FILE}" + ("" if CONFIG_FILE.exists() else "（不存在）"))
        print(f"缓存文件: {CACHE_FILE}" + ("" if CACHE_FILE.exists() else "（不存在）"))
        for kind in DEVICE_KINDS:
            e = explain(kind)
            if e["resource"]:
                print(f"  {kind:4s} [{e['source']:6s}] {e['resource']}   ({e['label']})")
            else:
                print(f"  {kind:4s} [未配置] 需 instr_discover / env {e['env_var']} / "
                      f"本文件；自动发现待命中   ({e['label']})")
        return 0

    if cmd == "init":
        return _write_template(force="--force" in argv)

    if cmd == "set":
        if len(argv) < 3:
            print(USAGE)
            return 2
        p = save_config(argv[1], argv[2])
        print(f"已写入 {argv[1]} = {argv[2]}\n  -> {p}")
        return 0

    if cmd == "clear":
        if len(argv) < 2:
            print(USAGE)
            return 2
        p = clear_config(argv[1])
        print(f"已删除 {argv[1]} 条目\n  -> {p}")
        return 0

    print(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
