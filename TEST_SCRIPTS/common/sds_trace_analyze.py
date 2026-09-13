"""复检历史截图中 C4 绿色轨迹的真实分布（修正 AI 肉眼看漏的问题）。"""
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from common.resolver import resolve
from sds_control import SDS

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def analyze(bmp_path: Path) -> None:
    data = bmp_path.read_bytes()
    w = struct.unpack("<i", data[18:22])[0]
    h_raw = struct.unpack("<i", data[22:26])[0]
    top_down = h_raw < 0
    h = abs(h_raw)
    offset = struct.unpack("<I", data[10:14])[0]
    row_size = ((w * 4 + 3) // 4) * 4

    # 绿色系（C4）：G 高、R 低、B 低
    ys: Counter = Counter()
    xs: Counter = Counter()
    for r in range(h):
        base = offset + r * row_size
        for c in range(w):
            i = base + c * 4
            b, g, rr = data[i], data[i + 1], data[i + 2]
            if g > 150 and g > rr + 50 and g > b + 50:
                disp_r = r if top_down else h - 1 - r
                ys[disp_r] += 1
                xs[c] += 1
    if not ys:
        print("未找到绿色像素")
        return
    y_all = sorted(ys)
    x_all = sorted(xs)
    print(f"绿色像素总数: {sum(ys.values())}")
    print(f"Y 分布: min={y_all[0]} max={y_all[-1]} 行数={len(y_all)}")
    print(f"X 分布: min={x_all[0]} max={x_all[-1]} 列数={len(x_all)}")
    print("\nY 直方图(每 25px 一桶):")
    buckets: Counter = Counter()
    for y, n in ys.items():
        buckets[y // 25 * 25] += n
    for k in sorted(buckets):
        bar = "#" * min(60, buckets[k] // 20)
        print(f"  y∈[{k:3d},{k+25:3d}): {buckets[k]:5d} {bar}")


if __name__ == "__main__":
    if TARGET and TARGET.exists():
        analyze(TARGET)
    else:
        # 地址由 common.resolver 解析（不写死 IP，换网段/换口自适应）
        with SDS(resolve("sds")) as s:
            from datetime import datetime

            OUT_DIR = ROOT / "TEST_DATA" / "common"
            p = OUT_DIR / f"sds_screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bmp"
            p.write_bytes(s.screenshot())
            print(f"新截屏: {p}")
            analyze(p)
