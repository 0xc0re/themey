"""Aurorae theme file generators.

This package converts a frozen ``Theme`` IR into the files that KDE Plasma's
Aurorae window decoration plugin expects:

  - ``decoration.svg``   — 9-patch FrameSvg with 18 required element IDs
  - ``<name>rc``         — INI [General] + [Layout]
  - ``metadata.desktop`` — Aurorae plugin metadata (hand-rolled .desktop)
  - ``metadata.json``    — KF6-compatible plugin metadata
  - per-button SVGs      — close.svg, maximize.svg, restore.svg, minimize.svg, …

Entry point for Plan 09 (CLI pipeline)::

    from themey.generate.aurorae import write as write_aurorae
"""
