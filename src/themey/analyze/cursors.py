"""AST ``__CURSOR`` blocks → tuple[CursorSpec, ...].

E16 ``cursors.c:267-340`` defines the __CURSOR block grammar:

    __CURSOR __BGN
      __NAME <ident>
      __XBM_FILE "path/relative/to/asset_root.xbm"
      __FG_COLOR <r> <g> <b>
      __BG_COLOR <r> <g> <b>
      __HOT_X <int>                  (optional, defaults to 0)
      __HOT_Y <int>                  (optional, defaults to 0)
    __END

This module ONLY parses the blocks into a frozen ``CursorSpec`` tuple —
XCursor emission is deferred to Phase 3 per the plan.

Path policy mirrors ``iclasses.py``: paths that resolve outside
``asset_root`` (T-05-01) are set to ``None``; missing files keep their
resolved Path so ``build_theme`` can log the missing-asset note.
"""
from __future__ import annotations

from pathlib import Path

from themey.etheme.ast import AstNode, Block, KeyVal
from themey.ir import CursorSpec


def _to_int(v: object) -> int:
    return int(v)  # type: ignore[arg-type]


def _block_name(block: Block) -> str | None:
    """Mirror of ``iclasses._block_name`` — accept head_values or legacy __NAME."""
    if block.head_values:
        return str(block.head_values[0])
    for child in block.children:
        if isinstance(child, KeyVal) and child.keyword == "__NAME" and child.values:
            return str(child.values[0])
    return None


def _rgb_from_kv(kv: KeyVal, default: tuple[int, int, int]) -> tuple[int, int, int]:
    """Parse the three-integer color form ``__FG_COLOR r g b``."""
    if len(kv.values) < 3:
        return default
    return (_to_int(kv.values[0]), _to_int(kv.values[1]), _to_int(kv.values[2]))


def extract_cursors(
    ast_nodes: list[AstNode],
    asset_root: Path,
) -> tuple[CursorSpec, ...]:
    """Collect every top-level ``__CURSOR`` block into a CursorSpec tuple.

    Unnamed blocks (no head_values and no __NAME child) are skipped — there
    is no key to dedupe against and emission cannot map them to an XCursor
    file name.
    """
    asset_root_resolved = str(asset_root.resolve())
    cursors: list[CursorSpec] = []
    for node in ast_nodes:
        if not (isinstance(node, Block) and node.keyword == "__CURSOR"):
            continue
        name = _block_name(node)
        if name is None:
            continue
        xbm_path: Path | None = None
        hot_x = 0
        hot_y = 0
        fg_rgb: tuple[int, int, int] = (255, 255, 255)
        bg_rgb: tuple[int, int, int] = (0, 0, 0)
        for child in node.children:
            if not isinstance(child, KeyVal) or not child.values:
                continue
            k = child.keyword
            if k == "__XBM_FILE":
                rel = str(child.values[0])
                full = (asset_root / rel).resolve()
                if (
                    str(full) == asset_root_resolved
                    or str(full).startswith(asset_root_resolved + "/")
                ):
                    xbm_path = full
                else:
                    xbm_path = None
            elif k == "__HOT_X":
                hot_x = _to_int(child.values[0])
            elif k == "__HOT_Y":
                hot_y = _to_int(child.values[0])
            elif k == "__FG_COLOR":
                fg_rgb = _rgb_from_kv(child, fg_rgb)
            elif k == "__BG_COLOR":
                bg_rgb = _rgb_from_kv(child, bg_rgb)
        cursors.append(
            CursorSpec(
                name=name,
                xbm_path=xbm_path,
                hot_x=hot_x,
                hot_y=hot_y,
                fg_rgb=fg_rgb,
                bg_rgb=bg_rgb,
            )
        )
    return tuple(cursors)
