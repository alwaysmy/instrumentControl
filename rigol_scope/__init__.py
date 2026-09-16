"""rigol_scope — RIGOL 示波器共享内核（DHO800/900 与 MHO900）。

合并依据（命令集 97% 重合、DHO 驱动 40 条命令 100% 存在于 MHO 手册）与家族差异表见
`docs/rigol_scope_compare_20260915.md` 和 `rigol_scope/families.py`。

用法（正常不需要直接用它，用各库的 DHO/MHO 即可）：
    from rigol_scope import RigolScope, FAMILIES, family_of
"""
from .families import DHO as DHO_FAMILY, FAMILIES, MHO as MHO_FAMILY, Family, family_of
from .scope import (EDGE_DEPENDENT_ITEMS, INVALID_MEASURE, RigolScope, find_scope,
                    snap_1_2_5, snap_up)

# 兼容旧引用（mho_control 曾从本模块名导出）
__all__ = [
    "FAMILIES",
    "INVALID_MEASURE",
    "EDGE_DEPENDENT_ITEMS",
    "DHO_FAMILY",
    "MHO_FAMILY",
    "Family",
    "RigolScope",
    "family_of",
    "find_scope",
    "snap_1_2_5",
    "snap_up",
]
