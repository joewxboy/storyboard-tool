"""Command line interface.

    storyboard build  INPUT.md [INPUT2.md ...] -o out.html
    storyboard extract INPUT.md [...] -o model.json
    storyboard render model.json -o out.html
    storyboard check  INPUT.md
"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from .model import Storyboard, storyboard_from_json, timecode
from .parse import parse_file
from .render import render
from .theme import PRESETS, load_theme


def _episodes(paths: list[str], args) -> list:
    eps = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files = sorted(f for f in path.glob("*.md") if not f.name.startswith("."))
            if args.exclude:
                import fnmatch
                files = [f for f in files
                         if not any(fnmatch.fnmatch(f.name, pat) for pat in args.exclude)]
        else:
            files = [path]
        for f in files:
            if not f.is_file():
                raise SystemExit(f"no such file: {f}")
            ep = parse_file(f, wpm=args.wpm, default_duration=args.duration)
            side = f.with_suffix(".storyboard.json")
            if side.is_file():
                from .parse import apply_sidecar
                ep = apply_sidecar(ep, json.loads(side.read_text(encoding="utf-8")))
            if args.url and not ep.endcard.get("url"):
                ep.endcard["url"] = args.url
            eps.append(ep)
    return eps


def _storyboard(args) -> Storyboard:
    eps = _episodes(args.input, args)
    if not eps:
        raise SystemExit("nothing to build")
    title = args.title or (eps[0].title if len(eps) == 1 else "Storyboard")
    sb = Storyboard(title=title, tagline=args.tagline or "", aspect=args.aspect, episodes=eps)
    if args.chip:
        sb.chips = list(args.chip)
    return sb


def _write(path: str | None, text: str, label: str) -> None:
    if not path or path == "-":
        sys.stdout.write(text)
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print(f"{label} → {p}  ({len(text) / 1024:.0f} KB)", file=sys.stderr)


def cmd_build(args) -> int:
    sb = _storyboard(args)
    theme = load_theme(args.theme, {"accent": args.accent} if args.accent else None)
    out = args.output or "storyboard.html"
    _write(out, render(sb, theme, start=args.start), "storyboard")
    if args.model:
        _write(args.model, sb.dumps(), "model")
    if args.open and out != "-":
        webbrowser.open(Path(out).resolve().as_uri())
    _report(sb)
    return 0


def cmd_extract(args) -> int:
    sb = _storyboard(args)
    _write(args.output, sb.dumps(), "model")
    _report(sb)
    return 0


def cmd_render(args) -> int:
    data = json.loads(Path(args.model_file).read_text(encoding="utf-8"))
    sb = storyboard_from_json(data)
    if args.title:
        sb.title = args.title
    if args.aspect and args.aspect != "9:16":
        sb.aspect = args.aspect
    theme = load_theme(args.theme or (sb.theme.get("preset") if sb.theme else None),
                       {"accent": args.accent} if args.accent else None)
    out = args.output or "storyboard.html"
    _write(out, render(sb, theme, start=args.start), "storyboard")
    if args.open and out != "-":
        webbrowser.open(Path(out).resolve().as_uri())
    return 0


def cmd_check(args) -> int:
    sb = _storyboard(args)
    _report(sb, verbose=True)
    return 0


def _report(sb: Storyboard, verbose: bool = False) -> None:
    for ep in sb.episodes:
        mode = getattr(ep, "mode", "")
        head = f"{ep.code or ep.title}".strip()
        print(f"\n{head}  {timecode(ep.duration)}  "
              f"{len(ep.beats)} beats · {len(ep.shots)} shots · "
              f"{len(ep.captions)} captions"
              + (f"  [{mode}]" if mode else ""), file=sys.stderr)
        if verbose:
            for b in ep.beats:
                own = [s for s in ep.shots if s.frm >= b.frm - 0.01 and s.to <= b.to + 0.01]
                print(f"  {b.n:>2} {b.name[:28]:<28} {timecode(b.frm)}–{timecode(b.to)}"
                      f"  {len(own)} shots", file=sys.stderr)
            for s in ep.shots:
                print(f"     {str(s.num):>3}  {timecode(s.frm)}–{timecode(s.to)}  "
                      f"{s.plate.get('kind','?'):<8} {s.title[:52]}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="storyboard",
        description="Turn a markdown transcript, outline or beat sheet into an "
                    "interactive, playable video storyboard.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, inputs=True):
        if inputs:
            sp.add_argument("input", nargs="+",
                            help="markdown file(s), or a directory of them (one episode each)")
        sp.add_argument("-o", "--output", help="output path ('-' for stdout)")
        sp.add_argument("--title", help="page title (default: first episode's title)")
        sp.add_argument("--tagline", default="", help="one line under the title")
        sp.add_argument("--aspect", default="9:16",
                        choices=["9:16", "16:9", "1:1", "4:5", "2.39:1"],
                        help="frame aspect ratio (default 9:16)")
        sp.add_argument("--theme", help=f"preset ({', '.join(PRESETS)}) or path to a theme JSON")
        sp.add_argument("--accent", help="override the accent colour, e.g. '#4C8DFF'")
        sp.add_argument("--chip", action="append", help="extra chip in the header (repeatable)")
        sp.add_argument("--url", help="default end-card URL for episodes that have none")
        sp.add_argument("--duration", type=float, default=150.0,
                        help="fallback episode length in seconds (default 150)")
        sp.add_argument("--wpm", type=int, default=150,
                        help="narration speed used to time untimed transcripts (default 150)")
        sp.add_argument("--start", type=int, default=0, help="episode index to open on")
        sp.add_argument("--exclude", action="append", metavar="GLOB",
                        help="skip files matching this glob when INPUT is a directory "
                             "(repeatable, e.g. --exclude '00-*.md')")

    b = sub.add_parser("build", help="markdown → self-contained HTML player")
    common(b)
    b.add_argument("--model", help="also write the intermediate JSON model here")
    b.add_argument("--open", action="store_true", help="open the result in a browser")
    b.set_defaults(func=cmd_build)

    e = sub.add_parser("extract", help="markdown → JSON model (edit it, then render)")
    common(e)
    e.set_defaults(func=cmd_extract)

    r = sub.add_parser("render", help="JSON model → HTML player")
    r.add_argument("model_file", help="a model written by 'extract'")
    common(r, inputs=False)
    r.add_argument("--open", action="store_true", help="open the result in a browser")
    r.set_defaults(func=cmd_render)

    c = sub.add_parser("check", help="parse and print the timing table, write nothing")
    common(c)
    c.set_defaults(func=cmd_check)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
