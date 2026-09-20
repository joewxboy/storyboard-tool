"""Model → one self-contained HTML page.

CSS and JS are inlined so the output works from ``file://``, from a static
host, or as a published Claude artifact with no build step and no assets
beside it.  The only external request is the Google Fonts stylesheet, and the
page degrades to system fonts without it.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from .model import Storyboard, timecode
from .theme import css_vars

ASSETS = Path(__file__).parent / "assets"

DEFAULT_NOTES = [
    {"heading": "What this is",
     "body": "Placeholder plates cut to the real clock, straight from the source markdown. "
             "The value is the timing: scrub the long beat and you can see which sections are "
             "over-packed before a camera is rigged."},
    {"heading": "Keys",
     "body": "<code>space</code> play/pause · <code>←</code>/<code>→</code> nudge a second · "
             "<code>[</code>/<code>]</code> previous/next episode · click any beat or shot to seek · "
             "<code>guides</code> overlays the safe areas and thirds."},
    {"heading": "Turning it into footage",
     "body": "Shoot to these durations — the shot list is the capture order. Then swap a plate for "
             "the real thing by setting that shot's plate to "
             "<code>{\"kind\": \"image\", \"src\": \"stills/shot-3.png\"}</code> and re-rendering."},
]

ASPECTS = {
    "9:16": ("9 / 16", "min(372px, calc((100vh - 300px) * 0.5625))"),
    "16:9": ("16 / 9", "min(760px, calc((100vh - 320px) * 1.778))"),
    "1:1":  ("1 / 1",  "min(520px, calc(100vh - 320px))"),
    "4:5":  ("4 / 5",  "min(440px, calc((100vh - 300px) * 0.8))"),
    "2.39:1": ("2.39 / 1", "min(880px, calc((100vh - 320px) * 2.39))"),
}


def render(sb: Storyboard, theme: dict, *, start: int = 0) -> str:
    template = (ASSETS / "player.html").read_text(encoding="utf-8")
    css = (ASSETS / "player.css").read_text(encoding="utf-8")
    js = (ASSETS / "player.js").read_text(encoding="utf-8")

    aspect, frame_max = ASPECTS.get(sb.aspect, ASPECTS["9:16"])
    data = sb.json()
    data["start"] = start

    chips = sb.chips or _auto_chips(sb)
    chip_html = "\n        ".join(
        f'<span class="chip">{html.escape(c)}</span>' for c in chips)

    notes = sb.notes or DEFAULT_NOTES
    notes_html = "\n".join(
        f"    <div>\n      <h4>{html.escape(n.get('heading',''))}</h4>\n"
        f"      <p>{n.get('body','')}</p>\n    </div>" for n in notes)

    fonts = theme.get("fonts")
    fonts_html = ""
    if fonts:
        fonts_html = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                      '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                      f'<link rel="stylesheet" href="{html.escape(fonts, quote=True)}">')

    out = template
    for token, value in (
        ("__TITLE__", html.escape(sb.title)),
        ("__HEADING__", html.escape(sb.title)),
        ("__TAGLINE__", html.escape(sb.tagline)),
        ("__FONTS__", fonts_html),
        ("__THEME__", css_vars(theme)),
        ("__ASPECT__", aspect),
        ("__CHIPS__", chip_html),
        ("__NOTES__", notes_html),
        ("__CSS__", css + f"\n.frame {{ --frame-max: {frame_max}; }}\n"),
        ("__JS__", js),
        ("__DATA__", json.dumps(data, ensure_ascii=False)),
    ):
        out = out.replace(token, value)
    return out


def _auto_chips(sb: Storyboard) -> list[str]:
    chips = [sb.aspect.replace(":", " : ")]
    durs = sorted({round(e.duration) for e in sb.episodes})
    if len(durs) == 1:
        chips.append(timecode(durs[0]))
    elif durs:
        chips.append(f"{timecode(durs[0])}–{timecode(durs[-1])}")
    chips.append(f"{len(sb.episodes)} episode{'s' if len(sb.episodes) != 1 else ''}")
    return chips
