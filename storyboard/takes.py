"""Find captured footage and put it in the shot it belongs to.

The sheets already name their assets — `00-template.md` says takes are
``V<NN>-<slug>-<take>.<ext>`` and stills ``V<NN>-shot-<n>.png``.  So placing a
shot needs no editing at all: drop the file in the assets directory under a
name that says which shot it is, and it lands there on the next build.

Recognised names (case-insensitive, separators interchangeable)::

    V01-shot-6.png          still for shot 6 of V1
    V01-shot-6.mp4          footage for shot 6
    V01-shot-6-take3.mp4    take 3 — the highest take number wins
    shot-6.mp4              episode taken from the directory, or the only one

Ordering when several files match one shot: highest take number first, then
video over still, then most recently modified.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".ogv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg"}
# What a browser will actually play back from a file:// page.
BROWSER_VIDEO = {".mp4", ".webm", ".m4v", ".ogv"}

STEM_RE = re.compile(
    r"^(?:(?P<ep>[a-z]{1,3}[ _-]?\d{1,3})[-_ ]+)?"
    r"shot[-_ ]*(?P<n>\d{1,3})"
    r"(?:[-_ ]*(?:take[-_ ]*)?(?P<take>\d{1,3}))?$", re.I)


@dataclass
class Take:
    path: Path
    shot: int
    episode: str | None      # normalised episode key, e.g. "V01"
    take: int
    kind: str                # "video" | "image"
    duration: float | None = None   # seconds, from ffprobe (video only)

    @property
    def sort_key(self):
        return (self.take, self.kind == "video", self.path.stat().st_mtime)


def episode_keys(ep) -> set[str]:
    """Every spelling of an episode's asset prefix: V1, V01 — and V00 for Ep 0."""
    keys: set[str] = set()
    code = re.sub(r"[^A-Za-z0-9]", "", ep.code or "").upper()
    m = re.match(r"^([A-Z]{1,3})(\d{1,3})$", code)
    if m:
        letters, num = m.group(1), int(m.group(2))
        keys |= {f"{letters}{num}", f"{letters}{num:02d}"}
        if letters == "EP":                      # the template shoots Ep 0 as V00
            keys |= {f"V{num}", f"V{num:02d}"}
    elif code:
        keys.add(code)
    return keys


def _norm(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", token).upper()


def scan(dirs: list[str | Path]) -> list[Take]:
    """Every recognisable take under these directories (one level of nesting)."""
    found: list[Take] = []
    for d in dirs:
        root = Path(d)
        if not root.is_dir():
            raise SystemExit(f"assets directory not found: {root}")
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            kind = "video" if ext in VIDEO_EXT else "image" if ext in IMAGE_EXT else None
            if not kind:
                continue
            m = STEM_RE.match(path.stem)
            if not m:
                continue
            ep = _norm(m.group("ep")) if m.group("ep") else None
            if ep is None:
                parent = _norm(path.parent.name)
                ep = parent if re.fullmatch(r"[A-Z]{1,3}\d{1,3}", parent) else None
            found.append(Take(path=path, shot=int(m.group("n")), episode=ep,
                              take=int(m.group("take") or 0), kind=kind))
    return found


def probe_duration(path: Path) -> float | None:
    """Clip length in seconds, or None when ffprobe is unavailable or unsure."""
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def attach(episodes: list, takes: list[Take], *, out_dir: Path,
           url_prefix: str | None = None, probe: bool = True,
           tolerance: float = 1.0) -> list[str]:
    """Put each take on its shot. Returns a list of human-readable notes."""
    notes: list[str] = []
    single = len(episodes) == 1

    for ep in episodes:
        keys = episode_keys(ep)
        mine: dict[int, list[Take]] = {}
        for t in takes:
            if t.episode is not None and t.episode not in keys:
                continue
            if t.episode is None and not single:
                continue        # ambiguous: several episodes, unprefixed file
            mine.setdefault(t.shot, []).append(t)

        by_num = {}
        for s in ep.shots:
            try:
                by_num[int(s.num)] = s
            except (TypeError, ValueError):
                continue

        for num, candidates in sorted(mine.items()):
            shot = by_num.get(num)
            if not shot:
                notes.append(f"{ep.code or ep.title}: no shot {num} for "
                             f"{candidates[0].path.name}")
                continue
            take = max(candidates, key=lambda t: t.sort_key)
            if probe and take.kind == "video":
                take.duration = probe_duration(take.path)

            src = url_prefix.rstrip("/") + "/" + take.path.name if url_prefix else \
                _relative(take.path, out_dir)
            slot = shot.to - shot.frm

            if take.kind == "video":
                shot.plate = {"kind": "video", "src": src, "fit": "cover",
                              "slot": round(slot, 2)}
                if take.duration:
                    shot.plate["clip"] = round(take.duration, 2)
            else:
                shot.plate = {"kind": "image", "src": src, "caption": shot.title}

            shot.asset = {"src": src, "kind": take.kind, "take": take.take,
                          "clip": round(take.duration, 2) if take.duration else None,
                          "slot": round(slot, 2)}

            if take.kind == "video" and take.path.suffix.lower() not in BROWSER_VIDEO:
                notes.append(f"{ep.code}: {take.path.name} may not play in a browser — "
                             f"try: ffmpeg -i {take.path.name} -c:v libx264 -an "
                             f"{take.path.stem}.mp4")
            if take.duration:
                delta = take.duration - slot
                if abs(delta) > tolerance:
                    over = "over" if delta > 0 else "under"
                    shot.asset["over"] = round(delta, 2)
                    notes.append(
                        f"{ep.code} shot {num}: take is {_tc(take.duration)}, "
                        f"slot is {_tc(slot)} — {abs(delta):.0f}s {over}")
    return notes


def _relative(path: Path, out_dir: Path) -> str:
    """A src the built page can resolve, relative to where the page is written."""
    import os
    try:
        return os.path.relpath(path.resolve(), out_dir.resolve()).replace("\\", "/")
    except ValueError:            # different drive on Windows
        return path.resolve().as_uri()


def _tc(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"
