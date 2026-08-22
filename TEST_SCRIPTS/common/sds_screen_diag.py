"""SDS 截屏诊断 v2：32bit BMP 解析 + 转 PNG 供 AI 查看。

用法：
    $env:PYTHONIOENCODING="utf-8"; python TEST_SCRIPTS/common/sds_screen_diag.py [--open]
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sds_control import SDS  # noqa: E402

OUT_DIR = ROOT / "TEST_DATA" / "common"


def parse_and_convert(bmp_path: Path) -> None:
    data = bmp_path.read_bytes()
    w = struct.unpack("<i", data[18:22])[0]
    h_raw = struct.unpack("<i", data[22:26])[0]
    bpp = struct.unpack("<H", data[28:30])[0]
    top_down = h_raw < 0
    h = abs(h_raw)
    print(f"尺寸 {w}x{h} @ {bpp}bit, 自上而下={top_down}")

    offset = struct.unpack("<I", data[10:14])[0]
    row_size = ((w * bpp // 8 + 3) // 4) * 4
    px = bpp // 8

    colors: Counter = Counter()
    rows: dict[int, Counter] = {}
    for r in range(h):
        src_row = r if top_down else h - 1 - r
        base = offset + r * row_size
        for c in range(w):
            i = base + c * px
            b, g, rr = data[i], data[i + 1], data[i + 2]
            key = (rr >> 4 << 4, g >> 4 << 4, b >> 4 << 4)
            colors[key] += 1
            if rr > 150 and g > 100 and b < 120 and g > b + 40:
                rows.setdefault(src_row, Counter())[c] += 1

    total = w * h
    print("主要颜色 TOP10:")
    for cc, n in colors.most_common(10):
        print(f"  RGB{cc}: {n / total:.1%}")

    print(f"\n疑似绿色轨迹像素行分布（前 20 行）:")
    for row in sorted(rows)[:20]:
        cs = rows[row]
        lo, hi = min(cs), max(cs)
        print(f"  y={row}: {sum(cs.values())}px, x∈[{lo},{hi}]")

    try:
        from PIL import Image

        img = Image.frombytes(
            "RGBA", (w, h), bytes(data[offset : offset + row_size * h]), "raw", "BGRA"
        )
        if not top_down:
            img = img.transpose(0)
        png = bmp_path.with_suffix(".png")
        img.save(png)
        print(f"\nPNG 已生成: {png}")
    except ImportError:
        print("\n无 PIL，跳过 PNG 转换")


def main() -> int:
    with SDS("TCPIP0::192.168.31.220::inst0::INSTR") as s:
        data = s.screenshot_bmp()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bmp_path = OUT_DIR / f"sds_screen_{stamp}.bmp"
    bmp_path.write_bytes(data)
    print(f"BMP 已保存: {bmp_path}")
    parse_and_convert(bmp_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
