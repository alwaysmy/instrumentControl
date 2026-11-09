"""本机默认地址：**走解析层**（配置/缓存），常量只做最后兜底。

为什么单独一个模块：`GPIB0::9::INSTR` 原先散落在 `remote.py` / `worker.py` /
`preflight.py` 三处（都是"默认实参/兜底"），换 GPIB 接口号就得改三处，
而且改错了没有任何提示——它只是"连不上"。

这里只查**已确定的**地址（`common/resolver.known_resources()`：
`devices.json` > 上次成功缓存），**不做网络发现**：默认值会在导入期/构造期求值，
不能触发 10s 级的扫描。
"""
from __future__ import annotations


def resource(kind: str = "ks3458a", fallback: str = "GPIB0::9::INSTR") -> str:
    """取本机配置里的地址；配置/缓存都没有才返回 `fallback`。"""
    try:
        from common.resolver import known_resources

        hit = known_resources().get(kind)
        if hit:
            return hit
    except Exception:                                          # noqa: BLE001
        pass
    return fallback
