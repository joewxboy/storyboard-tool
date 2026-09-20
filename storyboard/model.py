"""The storyboard data model.

A storyboard is a list of episodes; an episode is a clock (``duration``), a
list of beats that partition that clock, and a list of shots that sit inside
the beats.  Everything else — captions, lower-thirds, machine labels, the end
card — is a timed overlay on top.

The model is plain dicts under the hood so it round-trips through JSON
losslessly: ``extract`` writes it, you hand-edit it, ``render`` reads it back.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


def timecode(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass
class Beat:
    n: int
    name: str
    frm: float
    to: float
    content: str = ""

    def json(self) -> dict:
        return {"n": self.n, "name": self.name, "from": round(self.frm, 3),
                "to": round(self.to, 3), "content": self.content}


@dataclass
class Shot:
    num: Any                 # shot number from the sheet; may be "" or a string
    frm: float
    to: float
    title: str
    meta: str = ""           # "screen capture · beat 4"
    note: str = ""
    plate: dict = field(default_factory=lambda: {"kind": "scene"})
    asset: dict | None = None    # the captured take placed on this shot, if any

    def json(self) -> dict:
        out = {"num": self.num, "from": round(self.frm, 3), "to": round(self.to, 3),
               "title": self.title, "meta": self.meta, "note": self.note,
               "plate": self.plate}
        if self.asset:
            out["asset"] = self.asset
        return out


@dataclass
class Span:
    """A timed piece of burned-in furniture: caption, lower-third, label."""
    frm: float
    to: float
    text: str

    def json(self) -> dict:
        return {"from": round(self.frm, 3), "to": round(self.to, 3), "text": self.text}


@dataclass
class Episode:
    code: str = ""
    title: str = ""
    chapter: str = ""
    duration: float = 150.0
    moment: str = ""
    problem: str = ""
    problem_until: float = 0.0
    beats: list[Beat] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    captions: list[Span] = field(default_factory=list)
    lower: list[Span] = field(default_factory=list)
    labels: list[Span] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    endcard: dict = field(default_factory=dict)   # {eyebrow, line, url}
    end_from: float | None = None
    bonus: bool = False
    source: str = ""                              # path it was parsed from

    def json(self) -> dict:
        return {
            "code": self.code, "title": self.title, "chapter": self.chapter,
            "dur": round(self.duration, 3), "moment": self.moment,
            "problem": self.problem, "problemUntil": round(self.problem_until, 3),
            "beats": [b.json() for b in self.beats],
            "shots": [s.json() for s in self.shots],
            "captions": [c.json() for c in self.captions],
            "lower": [l.json() for l in self.lower],
            "labels": [l.json() for l in self.labels],
            "assets": list(self.assets),
            "endcard": dict(self.endcard),
            "endFrom": None if self.end_from is None else round(self.end_from, 3),
            "bonus": self.bonus, "source": self.source,
        }


@dataclass
class Storyboard:
    title: str = "Storyboard"
    tagline: str = ""
    aspect: str = "9:16"
    chips: list[str] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)   # [{heading, body}]
    theme: dict = field(default_factory=dict)
    episodes: list[Episode] = field(default_factory=list)

    def json(self) -> dict:
        return {
            "title": self.title, "tagline": self.tagline, "aspect": self.aspect,
            "chips": list(self.chips), "notes": list(self.notes),
            "theme": dict(self.theme),
            "episodes": [e.json() for e in self.episodes],
        }

    def dumps(self, indent: int = 2) -> str:
        return json.dumps(self.json(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------- loading ---

def _span(d: dict) -> Span:
    return Span(float(d["from"]), float(d["to"]), d.get("text", ""))


def episode_from_json(d: dict) -> Episode:
    return Episode(
        code=d.get("code", ""), title=d.get("title", ""), chapter=d.get("chapter", ""),
        duration=float(d.get("dur", d.get("duration", 150))),
        moment=d.get("moment", ""), problem=d.get("problem", ""),
        problem_until=float(d.get("problemUntil", 0) or 0),
        beats=[Beat(b.get("n", i + 1), b.get("name", ""), float(b["from"]), float(b["to"]),
                    b.get("content", ""))
               for i, b in enumerate(d.get("beats", []))],
        shots=[Shot(s.get("num", ""), float(s["from"]), float(s["to"]), s.get("title", ""),
                    s.get("meta", ""), s.get("note", ""),
                    s.get("plate") or {"kind": "scene"}, s.get("asset"))
               for s in d.get("shots", [])],
        captions=[_span(x) for x in d.get("captions", [])],
        lower=[_span(x) for x in d.get("lower", [])],
        labels=[_span(x) for x in d.get("labels", [])],
        assets=list(d.get("assets", [])),
        endcard=dict(d.get("endcard", {})),
        end_from=d.get("endFrom"),
        bonus=bool(d.get("bonus", False)),
        source=d.get("source", ""),
    )


def storyboard_from_json(d: dict) -> Storyboard:
    return Storyboard(
        title=d.get("title", "Storyboard"), tagline=d.get("tagline", ""),
        aspect=d.get("aspect", "9:16"), chips=list(d.get("chips", [])),
        notes=list(d.get("notes", [])), theme=dict(d.get("theme", {})),
        episodes=[episode_from_json(e) for e in d.get("episodes", [])],
    )
