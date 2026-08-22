"""快速截屏查看当前 SDS 屏幕。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from datetime import datetime

from sds_control import SDS

OUT_DIR = ROOT / "TEST_DATA" / "common"
OUT_DIR.mkdir(parents=True, exist_ok=True)

with SDS("TCPIP0::192.168.31.220::inst0::INSTR") as s:
    data = s.screenshot_bmp()
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
bmp = OUT_DIR / f"sds_screen_{stamp}.bmp"
bmp.write_bytes(data)

from PIL import Image
import struct

w = struct.unpack("<i", data[18:22])[0]
h_raw = struct.unpack("<i", data[22:26])[0]
offset = struct.unpack("<I", data[10:14])[0]
row_size = ((w * 4 + 3) // 4) * 4
img = Image.frombytes("RGBA", (abs(w), abs(h_raw)), bytes(data[offset:offset + row_size * abs(h_raw)]), "raw", "BGRA")
if h_raw > 0:
    img = img.transpose(0)
png = OUT_DIR / f"sds_screen_{stamp}.png"
img.save(png)
print(f"PNG: {png}")
