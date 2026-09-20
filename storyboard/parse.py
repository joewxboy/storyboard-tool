"""Markdown → storyboard model.

Three input shapes are understood, in order of preference:

1. **Beat-sheet** — a ``## Beat sheet`` table (``# | Beat | Budget | Content``)
   and a ``## Shot list`` table (``# | Shot | Notes``).  This is the richest
   form and the one the tool was generalized from.
2. **Outline** — headings or bullets carrying their own timecodes, e.g.
   ``## Cold open (0:00–0:20)`` with ``- shot`` bullets beneath.
3. **Transcript** — prose with no timings at all.  Sections become beats,
   paragraphs become shots, and the clock is estimated from the word count at
   ``--wpm`` words per minute.

Anything the parser guesses can be overridden by front matter, by a sidecar
JSON model, or by editing the extracted JSON and re-rendering it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .model import Beat, Episode, Shot, Span, Storyboard
from .plates import infer_plate

DASHES = "-\u2013\u2014\u2012"                      # - – — ‒  (hyphen first: safe in [...])
TIME_RE = re.compile(r"(?:(\d{1,2}):)?(\d{1,3})(?::(\d{2}))?")
SPAN_RE = re.compile(
    r"(\d{1,2}:\d{2}(?::\d{2})?)\s*[" + DASHES + r"]\s*(\d{1,2}:\d{2}(?::\d{2})?)")
AT_RE = re.compile(r"@\s*(\d{1,2}:\d{2})")
DUR_RE = re.compile(r"(?:~\s*)?(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)\b", re.I)
BEAT_REF_RE = re.compile(r"beats?\s+([0-9]+(?:\s*(?:,|and|&|[" + DASHES + r"])\s*[0-9]+)*)", re.I)


# ------------------------------------------------------------------ times ---

def parse_time(text: str) -> float | None:
    """'1:30' → 90.0, '0:07' → 7.0, '90s' → 90.0, '2:03:04' → 7384.0."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    m = DUR_RE.fullmatch(s)
    if m:
        return float(m.group(1))
    parts = s.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None
    return None


def parse_span(text: str) -> tuple[float, float] | None:
    """Pull a '0:20–0:40' style span out of arbitrary text."""
    if not text:
        return None
    m = SPAN_RE.search(text)
    if not m:
        return None
    a, b = parse_time(m.group(1)), parse_time(m.group(2))
    if a is None or b is None or b < a:
        return None
    return a, b


# --------------------------------------------------------- front matter ----

def split_front_matter(text: str) -> tuple[dict, str]:
    """Minimal YAML subset: ``key: value``, ``key:`` + ``- item`` lists."""
    if not text.startswith("---"):
        return {}, text
    end = re.search(r"^---\s*$", text[3:], re.M)
    if not end:
        return {}, text
    raw = text[3:3 + end.start()]
    body = text[3 + end.end():]
    meta: dict = {}
    key = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- ") and key:
            meta.setdefault(key, [])
            if isinstance(meta[key], list):
                meta[key].append(_scalar(line.lstrip()[2:]))
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            meta[key] = _scalar(val) if val else []
    return meta, body.lstrip("\n")


def _scalar(v: str):
    v = v.strip().strip('"').strip("'")
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d*\.\d+", v):
        return float(v)
    return v


# ----------------------------------------------------------- md helpers ----

def strip_md(text: str) -> str:
    """Inline markdown → plain text, keeping the words and the punctuation."""
    if not text:
        return ""
    t = text.replace("<br>", " ").replace("\\|", "|")
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\*\*([^*]*)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]*)\*", r"\1", t)
    t = re.sub(r"_{1,2}([^_]*)_{1,2}", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def sections(md: str) -> list[tuple[int, str, str]]:
    """[(level, heading, body)] for every ATX heading, plus a preamble."""
    out: list[tuple[int, str, str]] = []
    cur_level, cur_head, buf = 0, "", []
    in_fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            out.append((cur_level, cur_head, "\n".join(buf)))
            cur_level, cur_head, buf = len(m.group(1)), m.group(2).strip(), []
        else:
            buf.append(line)
    out.append((cur_level, cur_head, "\n".join(buf)))
    return out


def tables(md: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every GitHub-flavoured table in a block of markdown."""
    found = []
    rows: list[list[str]] = []
    for line in md.splitlines() + [""]:
        if line.strip().startswith("|"):
            inner = line.strip().strip("|")
            cells = [c.strip().replace("\\|", "|")
                     for c in re.split(r"(?<!\\)\|", inner)]
            rows.append(cells)
            continue
        if rows:
            if len(rows) >= 2 and re.fullmatch(r"[:\- ]+", "".join(rows[1])):
                found.append((rows[0], rows[2:]))
            rows = []
    return found


def _col(headers: list[str], *names: str) -> int | None:
    low = [h.lower().strip() for h in headers]
    for n in names:
        for i, h in enumerate(low):
            if n in h:
                return i
    return None


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


# ------------------------------------------------------------- the parse ---

def parse_file(path: str | Path, *, wpm: int = 150, default_duration: float = 150.0) -> Episode:
    p = Path(path)
    return parse_markdown(p.read_text(encoding="utf-8"), source=str(p),
                          wpm=wpm, default_duration=default_duration)


def parse_markdown(text: str, *, source: str = "", wpm: int = 150,
                   default_duration: float = 150.0) -> Episode:
    meta, body = split_front_matter(text)
    secs = sections(body)
    ep = Episode(source=source)

    _title_and_meta(ep, secs, meta)
    beats = _parse_beats(secs)
    mode = "beat-sheet" if beats else ""

    if not beats:
        beats = _parse_outline_beats(secs)
        mode = "outline" if beats else ""
    if not beats:
        beats, est = _parse_transcript_beats(secs, wpm)
        mode = "transcript"
        if est and not meta.get("duration"):
            ep.duration = est

    ep.beats = beats
    if meta.get("duration"):
        ep.duration = float(parse_time(str(meta["duration"])) or default_duration)
    elif beats:
        ep.duration = max(b.to for b in beats)
    else:
        ep.duration = default_duration
    if beats:
        _rescale(beats, ep.duration)

    ep.shots = _parse_shots(secs, ep)
    if not ep.shots:
        ep.shots = _shots_from_beats(ep)
    _fill_gaps(ep)

    ep.assets = _parse_assets(secs)
    _parse_copy_block(ep, secs)
    _derive_overlays(ep)
    _apply_meta_overrides(ep, meta)

    for s in ep.shots:
        if not s.plate or s.plate.get("kind") in (None, "", "auto"):
            s.plate = infer_plate(s, ep)
    ep.mode = mode                                    # type: ignore[attr-defined]
    return ep


# ----------------------------------------------------------- title / meta ---

TITLE_SPLIT = re.compile(r"^\s*([A-Za-z]{1,3}\s?\d{1,3}|Ep\.?\s?\d{1,3})\s*[" + DASHES + r":]\s*(.+)$")


def _title_and_meta(ep: Episode, secs, meta: dict) -> None:
    h1 = next((h for lvl, h, _ in secs if lvl == 1), "")
    h1_plain = strip_md(h1)
    bonus = bool(re.search(r"\(\s*bonus\s*\)|\(\s*optional\s*\)", h1, re.I))
    h1_plain = re.sub(r"\((?:bonus|optional|capstone[^)]*)\)", "", h1_plain, flags=re.I)
    h1_plain = SPAN_RE.sub("", h1_plain).strip(" ()" + DASHES)   # '… (0:00–1:40)' → '…' 
    m = TITLE_SPLIT.match(h1_plain)
    if m:
        ep.code, ep.title = m.group(1).strip(), m.group(2).strip()
    else:
        ep.code, ep.title = "", h1_plain
    ep.bonus = bonus

    preamble = next((b for lvl, _, b in secs if lvl <= 1), "")
    fields = dict(re.findall(r"^\*\*([^:*]+):\*\*\s*(.+)$", preamble, re.M))
    for key, dest in (("Pairs with", "chapter"), ("Chapter", "chapter"),
                      ("Section", "chapter"), ("Dramatized moment", "moment"),
                      ("Moment", "moment"), ("Premise", "moment")):
        for k, v in fields.items():
            if k.strip().lower() == key.lower() and not getattr(ep, dest):
                setattr(ep, dest, strip_md(v))
    if not ep.moment:
        for lvl, head, bodytext in secs:
            if re.search(r"\b(premise|logline|moment|summary)\b", head, re.I):
                first = next((strip_md(l) for l in bodytext.splitlines() if strip_md(l)), "")
                ep.moment = first
                break
    if not ep.chapter:
        ep.chapter = strip_md(meta.get("chapter", "")) if meta.get("chapter") else ""


def _apply_meta_overrides(ep: Episode, meta: dict) -> None:
    for key, attr in (("code", "code"), ("title", "title"), ("chapter", "chapter"),
                      ("moment", "moment"), ("problem", "problem")):
        if meta.get(key):
            setattr(ep, attr, str(meta[key]))
    if meta.get("problem_until"):
        ep.problem_until = float(parse_time(str(meta["problem_until"])) or 0)
    elif ep.problem and not ep.problem_until and ep.beats:
        ep.problem_until = ep.beats[0].to
    if meta.get("endcard"):
        ep.endcard.setdefault("line", str(meta["endcard"]))
    if meta.get("url"):
        ep.endcard["url"] = str(meta["url"])
    if meta.get("eyebrow"):
        ep.endcard["eyebrow"] = str(meta["eyebrow"])
    if meta.get("bonus"):
        ep.bonus = bool(meta["bonus"])
    if meta.get("end_from"):
        ep.end_from = parse_time(str(meta["end_from"]))


# ----------------------------------------------------------------- beats ---

def _parse_beats(secs) -> list[Beat]:
    for lvl, head, body in secs:
        if not re.search(r"beat\s*(sheet|budget|breakdown)|structure|beats", head, re.I):
            continue
        for headers, rows in tables(body):
            ti = _col(headers, "budget", "time", "timecode", "clock", "span", "when")
            ni = _col(headers, "beat", "section", "segment")
            if ti is None or ni is None:
                continue
            ci = _col(headers, "content", "notes", "what", "description", "purpose", "action")
            numi = _col(headers, "#", "no.", "num")
            beats: list[Beat] = []
            for i, row in enumerate(rows):
                span = parse_span(_cell(row, ti))
                if not span:
                    continue
                num = _cell(row, numi) if numi is not None else ""
                try:
                    n = int(re.sub(r"\D", "", num) or (i + 1))
                except ValueError:
                    n = i + 1
                beats.append(Beat(n, strip_md(_cell(row, ni)), span[0], span[1],
                                  _cell(row, ci)))
            if beats:
                return beats
    # A beat table can also live without a matching heading.
    for lvl, head, body in secs:
        for headers, rows in tables(body):
            if _col(headers, "beat") is not None and _col(headers, "budget", "time") is not None:
                return _parse_beats([(lvl, "beat sheet", body)])
    return []


def _parse_outline_beats(secs) -> list[Beat]:
    """Headings (or top-level bullets) that carry their own timecodes."""
    cands = []
    for lvl, head, body in secs:
        if lvl < 2 or not head:
            continue
        span = parse_span(head)
        if span:
            name = strip_md(SPAN_RE.sub("", head)).strip(" ()" + DASHES)
            cands.append(Beat(len(cands) + 1, name, span[0], span[1], body.strip()))
    if cands:
        return cands

    for lvl, head, body in secs:
        bullets = [l for l in body.splitlines() if re.match(r"^\s*[-*+]\s+", l)]
        timed = [b for b in bullets if parse_span(b)]
        if len(timed) >= 2:
            out = []
            for b in timed:
                span = parse_span(b)
                name = strip_md(SPAN_RE.sub("", re.sub(r"^\s*[-*+]\s+", "", b)))
                out.append(Beat(len(out) + 1, name.strip(" ()" + DASHES) or f"Beat {len(out)+1}",
                                span[0], span[1], ""))
            return out
    return []


def _parse_transcript_beats(secs, wpm: int) -> tuple[list[Beat], float]:
    """No timings anywhere: section headings become beats, length from words."""
    blocks = []
    for lvl, head, body in secs:
        text = "\n".join(l for l in body.splitlines()
                         if not l.strip().startswith("|") and not l.strip().startswith("---"))
        words = len(strip_md(text).split())
        if head and (words or lvl >= 2):
            blocks.append((strip_md(head), text.strip(), max(words, 8)))
    if not blocks:
        paras = [p for p in re.split(r"\n\s*\n", "\n".join(b for _, _, b in sections("")) or "") if p]
        return [], 0.0
    total_words = sum(w for _, _, w in blocks)
    total = max(20.0, total_words / max(1, wpm) * 60.0)
    beats, t = [], 0.0
    for i, (name, body, words) in enumerate(blocks):
        span = total * words / total_words
        beats.append(Beat(i + 1, name or f"Beat {i+1}", t, t + span, body))
        t += span
    if beats:
        beats[-1].to = total
    return beats, total


def _rescale(beats: list[Beat], duration: float) -> None:
    span = max(b.to for b in beats)
    if span <= 0 or abs(span - duration) < 0.01:
        return
    k = duration / span
    for b in beats:
        b.frm, b.to = b.frm * k, b.to * k


# ----------------------------------------------------------------- shots ---

def _parse_shots(secs, ep: Episode) -> list[Shot]:
    rows_found: list[list[str]] = []
    headers_found: list[str] = []
    for lvl, head, body in secs:
        if not re.search(r"shot\s*list|shots|storyboard|visuals", head, re.I):
            continue
        for headers, rows in tables(body):
            si = _col(headers, "shot", "visual", "frame", "description")
            if si is None:
                continue
            headers_found, rows_found = headers, rows
            break
        if rows_found:
            break
    if not rows_found:
        return []

    si = _col(headers_found, "shot", "visual", "frame", "description")
    numi = _col(headers_found, "#", "no.", "num")
    ni = _col(headers_found, "note", "detail", "action", "content")
    ti = _col(headers_found, "time", "timecode", "budget", "span", "clock")

    shots: list[Shot] = []
    for i, row in enumerate(rows_found):
        title_raw = _cell(row, si)
        if not title_raw:
            continue
        note = _cell(row, ni)
        num = _cell(row, numi) if numi is not None else str(i + 1)
        num = re.sub(r"\D", "", num) or (i + 1)
        span = parse_span(_cell(row, ti)) if ti is not None else None
        if not span:
            span = parse_span(title_raw) or parse_span(note)
        title, meta = _split_title_meta(title_raw, note)
        shots.append(Shot(num=int(num) if str(num).isdigit() else num,
                          frm=span[0] if span else -1.0,
                          to=span[1] if span else -1.0,
                          title=title, meta=meta, note=strip_md(note),
                          plate={"kind": "auto", "raw": title_raw + " " + note}))
    _assign_times(shots, ep)
    return shots


def _split_title_meta(title_raw: str, note: str) -> tuple[str, str]:
    """`laptop`: run the thing → title 'laptop: run the thing', meta from kind+beat."""
    title = strip_md(title_raw)
    kind = ""
    for pat, label in (
        (r"talking head|to camera|piece to camera", "camera"),
        (r"screen ?(capture|recording)|terminal|shell|cli", "screen capture"),
        (r"motion graphic|title card|card\b|graphic", "motion graphic"),
        (r"b-?roll|cutaway|establishing", "b-roll"),
        (r"timelapse|jump-?cut|wait", "timelapse"),
        (r"montage", "montage"),
        (r"still|screenshot|photo", "still"),
    ):
        if re.search(pat, title_raw + " " + note, re.I):
            kind = label
            break
    beats = BEAT_REF_RE.search(title_raw + " " + note)
    parts = [p for p in (kind, beats.group(0).lower() if beats else "") if p]
    return title, " · ".join(parts)


def _assign_times(shots: list[Shot], ep: Episode) -> None:
    """Fill in shot times the sheet did not state.

    A shot that names a beat ('beat 4', 'beats 2, 3') is placed inside that
    beat, sharing it equally with the other shots that name it.  Anything
    still unplaced is spread over whatever clock is left, in order.
    """
    beats = {b.n: b for b in ep.beats}
    groups: dict[tuple, list[Shot]] = {}
    for s in shots:
        if s.frm >= 0:
            continue
        m = BEAT_REF_RE.search(s.meta + " " + s.note + " " + s.title)
        key: tuple = ()
        if m:
            nums = [int(x) for x in re.findall(r"\d+", m.group(1)) if int(x) in beats]
            key = tuple(sorted(nums))
        groups.setdefault(key, []).append(s)

    for key, members in groups.items():
        if not key:
            continue
        frm = min(beats[n].frm for n in key)
        to = max(beats[n].to for n in key)
        step = (to - frm) / len(members)
        for i, s in enumerate(members):
            s.frm, s.to = frm + i * step, frm + (i + 1) * step

    loose = groups.get((), [])
    if loose:
        placed = sorted([s for s in shots if s.frm >= 0], key=lambda s: s.frm)
        gaps = _free_gaps(placed, ep.duration)
        total_gap = sum(g[1] - g[0] for g in gaps) or ep.duration
        weights = [max(12, len(s.note) + len(s.title)) for s in loose]
        wsum = sum(weights)
        cursor = 0
        gi, within = 0, 0.0
        for s, w in zip(loose, weights):
            length = total_gap * w / wsum
            while gi < len(gaps) and (gaps[gi][1] - gaps[gi][0] - within) <= 0.01:
                gi, within = gi + 1, 0.0
            if gi >= len(gaps):
                s.frm, s.to = max(0.0, ep.duration - length), ep.duration
                continue
            start = gaps[gi][0] + within
            end = min(gaps[gi][1], start + length)
            s.frm, s.to = start, end
            within += end - start
            cursor += 1
    shots.sort(key=lambda s: (s.frm, s.to))


def _free_gaps(placed: list[Shot], duration: float) -> list[tuple[float, float]]:
    gaps, t = [], 0.0
    for s in placed:
        if s.frm - t > 0.5:
            gaps.append((t, s.frm))
        t = max(t, s.to)
    if duration - t > 0.5:
        gaps.append((t, duration))
    return gaps or [(0.0, duration)]


def _shots_from_beats(ep: Episode) -> list[Shot]:
    """No shot list: every beat becomes one shot, split on its own content.

    A bullet is a shot *description*, so its plate is inferred as usual.  A
    paragraph is *narration*, so it gets a text plate that plays the words
    against the clock — the useful thing to see in a bare transcript.
    """
    shots: list[Shot] = []
    for b in ep.beats:
        bullets = [strip_md(re.sub(r"^\s*[-*+]\s+", "", l))
                   for l in b.content.splitlines() if re.match(r"^\s*[-*+]\s+", l)]
        bullets = [x for x in bullets if x]
        prose = not bullets
        if prose:
            paras = [strip_md(x) for x in re.split(r"\n\s*\n", b.content) if strip_md(x)]
            pieces = paras or [b.name]
        else:
            pieces = bullets
        step = (b.to - b.frm) / len(pieces)
        for i, piece in enumerate(pieces):
            title = piece if len(piece) <= 60 else piece[:57].rsplit(" ", 1)[0] + "\u2026"
            plate = ({"kind": "text", "text": piece, "eyebrow": b.name}
                     if prose else {"kind": "auto", "raw": piece})
            shots.append(Shot(num=len(shots) + 1, frm=b.frm + i * step,
                              to=b.frm + (i + 1) * step, title=title,
                              meta=f"beat {b.n}", note=piece, plate=plate))
    return shots


def _fill_gaps(ep: Episode) -> None:
    """Shots must tile the clock — the player always has something on screen."""
    if not ep.shots:
        ep.shots = [Shot(num=1, frm=0, to=ep.duration, title=ep.title or "Frame",
                         meta="", note="", plate={"kind": "card", "line": ep.title})]
        return
    ep.shots.sort(key=lambda s: (s.frm, s.to))
    for i, s in enumerate(ep.shots):
        s.frm = max(0.0, min(s.frm, ep.duration))
        s.to = max(s.frm + 0.5, min(s.to, ep.duration))
        if i + 1 < len(ep.shots):
            nxt = ep.shots[i + 1]
            if nxt.frm > s.to + 0.25:
                s.to = nxt.frm
    ep.shots[0].frm = 0.0
    ep.shots[-1].to = ep.duration


# ------------------------------------------------------------- overlays ----

QUOTED = re.compile(r"[“\"]([^”\"]{3,140})[”\"]")
CAPTION_RE = re.compile(
    r"(?:caption(?:\s+overlay)?|on-?screen(?:\s+(?:line|text|card))?|burn(?:ed)?-?in)\s*[:—-]\s*"
    r"[“\"*]*([^”\"*\n\.][^”\"*\n]{2,140})", re.I)
CMD_RE = re.compile(r"`([^`\n]{2,90})`")
LABEL_RE = re.compile(r"(?:machine label|label|host|node|\bon\b|\bat\b)[^`\n]{0,16}`([A-Za-z0-9][\w.\-]{1,24})`", re.I)


def _derive_overlays(ep: Episode) -> None:
    for s in ep.shots:
        # The raw cell keeps its backticks; the display text has them stripped,
        # and backticks are what mark commands, hosts and file names.
        blob = (s.plate or {}).get("raw") or (s.title + " · " + s.note)
        for m in CAPTION_RE.finditer(blob):
            text = strip_md(m.group(1)).strip(" —-’'\".")
            if text and not any(c.text == text for c in ep.captions):
                ep.captions.append(Span(s.frm, s.to, text))
        from .plates import _commands
        cmds = _commands(blob)
        if cmds:
            step = (s.to - s.frm) / len(cmds)
            for i, c in enumerate(cmds):
                ep.lower.append(Span(s.frm + i * step, s.frm + (i + 1) * step, c.strip()))
        lm = LABEL_RE.search(blob) or re.match(r"^`?([a-z][\w.\-]{1,20})`?\s*:", s.title)
        if lm:
            name = lm.group(1)
            if ep.labels and abs(ep.labels[-1].to - s.frm) < 0.6 and ep.labels[-1].text == name:
                ep.labels[-1].to = s.to
            else:
                ep.labels.append(Span(s.frm, s.to, name))

    if not ep.problem and ep.beats:
        first = ep.beats[0]
        pool = first.content or " ".join(s.note for s in ep.shots if s.to <= first.to)
        m = CAPTION_RE.search(pool) or QUOTED.search(pool)
        if m:
            ep.problem = strip_md(m.group(1)).strip(" —-’'\".")
            ep.problem_until = first.to

    ep.captions = _dedupe(ep.captions)
    ep.captions.sort(key=lambda c: c.frm)
    ep.lower.sort(key=lambda c: c.frm)
    ep.labels.sort(key=lambda c: c.frm)

    if ep.end_from is None and ep.beats:
        ep.end_from = ep.beats[-1].frm
    ep.endcard.setdefault("eyebrow", "full walkthrough →")
    ep.endcard.setdefault("line", ep.title or ep.code)


def _dedupe(spans: list[Span]) -> list[Span]:
    """Drop repeats — the same line often appears in a shot and in the copy block."""
    seen: dict[str, Span] = {}
    for sp in spans:
        key = re.sub(r"[^a-z0-9]+", "", sp.text.lower())
        if key in seen:
            keep = seen[key]
            keep.frm, keep.to = min(keep.frm, sp.frm), max(keep.to, sp.to)
            continue
        seen[key] = sp
    return list(seen.values())


def _parse_assets(secs) -> list[str]:
    for lvl, head, body in secs:
        if re.search(r"asset|checklist|capture list|b-?roll list", head, re.I):
            items = [strip_md(re.sub(r"^\s*[-*+]\s*\[.\]\s*", "", l))
                     for l in body.splitlines() if re.match(r"^\s*[-*+]\s*\[.\]", l)]
            items += [strip_md(re.sub(r"^\s*[-*+]\s*", "", l))
                      for l in body.splitlines()
                      if re.match(r"^\s*[-*+]\s+", l) and not re.match(r"^\s*[-*+]\s*\[.\]", l)]
            if items:
                return items
    return []


def _parse_copy_block(ep: Episode, secs) -> None:
    """A '## Caption / end-card copy' section: fenced blocks keyed by label."""
    for lvl, head, body in secs:
        if not re.search(r"caption|end\s*-?card|copy|on-?screen text", head, re.I):
            continue
        for m in re.finditer(r"\*\*([^*]+)\*\*\s*\n+```[^\n]*\n(.*?)```", body, re.S):
            label, block = m.group(1), m.group(2).strip("\n")
            lines = [l for l in block.splitlines() if l.strip()]
            if not lines:
                continue
            if re.search(r"end\s*-?card", label, re.I):
                url = next((l.strip() for l in lines if re.match(r"https?://", l.strip())), "")
                body_lines = [l.strip() for l in lines if l.strip() != url]
                ep.endcard["line"] = "<br>".join(body_lines) or ep.endcard.get("line", "")
                if url:
                    ep.endcard["url"] = url
                span = parse_span(label)
                if span:
                    ep.end_from = span[0]
                continue
            span = parse_span(label)
            if not span:
                bm = BEAT_REF_RE.search(label)
                if bm:
                    nums = [int(x) for x in re.findall(r"\d+", bm.group(1))]
                    hits = [b for b in ep.beats if b.n in nums]
                    if hits:
                        span = (min(b.frm for b in hits), max(b.to for b in hits))
            if span:
                text = " ".join(l.strip() for l in lines)
                ep.captions = [c for c in ep.captions
                               if not (c.frm >= span[0] - 0.01 and c.to <= span[1] + 0.01)]
                ep.captions.append(Span(span[0], span[1], text))


# --------------------------------------------------------------- sidecar ---

def apply_sidecar(ep: Episode, data: dict) -> Episode:
    """Merge a hand-written JSON override onto a parsed episode."""
    from .model import episode_from_json
    merged = ep.json()
    for k, v in data.items():
        merged[k] = v
    return episode_from_json(merged)


def load_model(path: str | Path) -> Storyboard:
    from .model import storyboard_from_json
    return storyboard_from_json(json.loads(Path(path).read_text(encoding="utf-8")))
