"""Theme presets.

A theme is a flat dict of design tokens rendered into ``:root`` custom
properties.  Pass ``--theme name`` for a preset or ``--theme my.json`` for a
file; a file may set as few tokens as it likes and inherits the rest from
``midnight``.
"""
from __future__ import annotations

import json
from pathlib import Path

MIDNIGHT = {
    "ground": "#151217", "panel": "#1D1922", "panel2": "#241F2B",
    "line": "#3A3242", "line2": "#2B2533",
    "ink": "#F3EEF1", "dim": "#A198AA", "dimmer": "#6E6678",
    "accent": "#C51A4A", "accentSoft": "#7A1531",
    "signal": "#7BB02A", "amber": "#E0A040", "alarm": "#E0563D",
    "frame": "#0B090D", "plate": "#0E0B12",
    "display": '"Archivo", "Helvetica Neue", Arial, sans-serif',
    "body": '"IBM Plex Sans", "Segoe UI", system-ui, sans-serif',
    "mono": '"IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace',
    "scheme": "dark",
    "fonts": ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800"
              "&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap"),
}

SLATE = dict(MIDNIGHT, **{
    "ground": "#0F141A", "panel": "#161D26", "panel2": "#1C242F",
    "line": "#2E3B4A", "line2": "#222C38",
    "ink": "#EAF0F6", "dim": "#93A3B4", "dimmer": "#63717F",
    "accent": "#4C8DFF", "accentSoft": "#1D3E73",
    "signal": "#43C08A", "amber": "#E2B33F", "alarm": "#EE6352",
    "frame": "#080C11", "plate": "#0C1118",
})

PAPER = dict(MIDNIGHT, **{
    "ground": "#F4F1EC", "panel": "#FFFFFF", "panel2": "#EDE8E1",
    "line": "#D5CEC3", "line2": "#E5DFD6",
    "ink": "#1E1B17", "dim": "#5F594F", "dimmer": "#8C8578",
    "accent": "#B4472E", "accentSoft": "#F0D8D0",
    "signal": "#3F7D48", "amber": "#B07B1E", "alarm": "#B33A2B",
    "frame": "#14120F", "plate": "#17150F",      # the frame stays dark: it is video
    "scheme": "light",
})

PRESETS = {"midnight": MIDNIGHT, "slate": SLATE, "paper": PAPER}


def load_theme(spec: str | None, overrides: dict | None = None) -> dict:
    theme = dict(MIDNIGHT)
    if spec:
        if spec in PRESETS:
            theme.update(PRESETS[spec])
        else:
            path = Path(spec)
            if not path.is_file():
                raise SystemExit(f"theme not found: {spec} (presets: {', '.join(PRESETS)})")
            theme.update(json.loads(path.read_text(encoding="utf-8")))
    if overrides:
        theme.update({k: v for k, v in overrides.items() if v})
    return theme


def css_vars(theme: dict) -> str:
    keep = [k for k in theme if k not in ("fonts", "scheme")]
    lines = [f"    --{_kebab(k)}: {theme[k]};" for k in keep]
    lines.append(f"    color-scheme: {theme.get('scheme', 'dark')};")
    return "\n".join(lines)


def _kebab(name: str) -> str:
    out = []
    for ch in name:
        if ch.isupper():
            out.append("-" + ch.lower())
        else:
            out.append(ch)
    return "".join(out)
