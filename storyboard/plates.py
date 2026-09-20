"""Plate inference — deciding what a shot should *look* like on the frame.

A plate is a small animated placeholder the player draws for a shot: a typing
terminal, a code file, a title card, a talking head, an app window, a waiting
clock, an abstract b-roll scene, or a real image once you have one.

Inference is keyword-driven and deliberately shallow; it is meant to get a
whole sheet on screen in one pass.  Override any shot by putting an explicit
marker in its notes::

    [plate: term label=pi-1]
    [plate: image src=stills/V07-shot-8.png]

or by editing the extracted JSON, where ``plate`` is just data.
"""
from __future__ import annotations

import re

MARKER = re.compile(r"\[plate:\s*([a-z]+)([^\]]*)\]", re.I)
CMD = re.compile(r"`([^`\n]{2,120})`")
QUOTED = re.compile(r"[“\"]([^”\"]{3,160})[”\"]")
PATH = re.compile(r"`?([\w./\-]+\.(?:json|ya?ml|sh|py|js|ts|go|conf|toml|env|md|Dockerfile))`?")
IMG = re.compile(r"(?:!\[[^\]]*\]\(([^)]+)\)|\b([\w./\-]+\.(?:png|jpe?g|webp|gif|svg))\b)")

GLYPH_WORDS = [
    (r"secret|token|credential|password|key|vault|auth", "key"),
    (r"cloud|hub|server|internet|network|remote", "cloud"),
    (r"pi\b|board|device|node|chip|hardware|sensor|camera", "chip"),
    (r"container|image|docker|podman|package|box", "box"),
    (r"deploy|ship|push|rollout|pipeline|flow", "arrow"),
    (r"pass|success|healthy|works|green|done|fix", "check"),
    (r"fail|error|broken|red|alarm|down|crash", "alert"),
    (r"ai|model|llm|infer|brain|智", "spark"),
    (r"doc|book|chapter|write|note|page", "doc"),
]


def _glyph(text: str) -> str:
    low = text.lower()
    for pat, name in GLYPH_WORDS:
        if re.search(pat, low):
            return name
    return "spark"


SHELLY = re.compile(
    r"^(?:sudo\s+)?[a-z][\w.\-]*\s+[\w./\-\$\'\"{|\u2026]", re.I)


def _commands(text: str) -> list[str]:
    """Backticked spans that read as something typed at a prompt."""
    out = []
    for c in CMD.findall(text):
        c = c.strip()
        if c.startswith(("$", "#", ">", "PS>")):
            out.append(c)
        elif SHELLY.match(c) and not re.match(r"^\w+\.\w{1,4}$", c):
            out.append("$ " + c)
    return out


def _script(cmds: list[str], outputs: list[str] | None = None) -> list[list[str]]:
    """Terminal script lines: ``[text, kind]`` where kind is

    ``c`` typed command · ``o`` instant output · ``k`` keep the caret here.
    """
    script: list[list[str]] = []
    outs = list(outputs or [])
    for i, c in enumerate(cmds):
        script.append([c, "c"])
        if i < len(outs):
            script.append([outs[i], "o"])
    script.append(["", "k"])
    return script


def _marker(note: str) -> dict | None:
    m = MARKER.search(note)
    if not m:
        return None
    spec: dict = {"kind": m.group(1).lower()}
    for k, v in re.findall(r"(\w+)\s*=\s*([^\s\]]+)", m.group(2) or ""):
        spec[k] = v
    return spec


def infer_plate(shot, episode) -> dict:
    plate = shot.plate or {}
    raw = plate.get("raw") or f"{shot.title} {shot.note}"
    title_raw = plate.get("rawTitle") or shot.title

    explicit = _marker(shot.note) or _marker(raw)
    if explicit:
        return _finish(explicit, raw)

    # The title is what is in frame; the note is direction about it. Read the
    # title on its own first so a note that merely mentions "the browser" or
    # "a shell" does not decide the plate.
    return _infer(shot, title_raw) or _infer(shot, raw, strict=True) or {
        "kind": "scene", "label": _short(shot.title, 52), "glyph": _glyph(raw)}


def _infer(shot, raw: str, strict: bool = False) -> dict | None:
    """One pass over one piece of text. ``strict`` is the notes pass: only
    signals strong enough to survive being mentioned in passing count, so a
    note that says "the browser still reaches it" does not make a browser."""
    blob = raw
    low = blob.lower()

    img = IMG.search(raw)
    if img:
        src = img.group(1) or img.group(2)
        # A bare filename in a sheet is usually an asset still to be captured;
        # a path (stills/shot-8.png) is one that exists. Only show the latter.
        if "/" in src:
            return {"kind": "image", "src": src, "caption": shot.title}

    card = re.search(r"motion graphic|title card|end card|punchline|graphic|montage still", low)
    if card:
        q = QUOTED.search(raw)
        return {"kind": "card", "line": _short(q.group(1) if q else shot.title, 64),
                "glyph": _glyph(blob)}

    cmds = _commands(raw)
    prompted = [c for c in cmds if not c.startswith("$ ") or c.startswith("$ $")]
    fileish = re.search(r"editor\b|service definition|config file|manifest|\bfile\b|"
                        r"\.(json|ya?ml|toml|conf|env)\b", low)
    termish = re.search(r"terminal|shell\b|\bcommand\b|\bcli\b|prompt|\bexec\b", low)
    if fileish and not prompted and not termish:
        return _file_plate(shot, raw)

    if cmds:
        return _term_plate(shot, blob, low, cmds)
    if re.search(r"talking head|to camera|piece to camera|creator|face enters|presenter", low):
        return {"kind": "head"}

    if re.search(r"progress bar|flashing|writing to|install(?:ing)?|upload|download", low):
        return {"kind": "progress", "title": _short(shot.title, 44)}

    if re.search(r"wait|timelapse|time-?lapse|poll|elapsed|countdown|jump-?cut", low):
        return {"kind": "wait", "label": _short(shot.title),
                "to": max(5, int(shot.to - shot.frm))}

    if not strict and re.search(r"chat|ask|prompt the model|question|answer|conversation|llm", low):
        q = QUOTED.search(raw)
        return {"kind": "chat",
                "title": _short(shot.title, 40),
                "q": (q.group(1) if q else "ask it something"),
                "a": "…answering locally.",
                "badge": "offline" if re.search(r"offline|unplug|no internet", low) else ""}

    if not strict and re.search(r"dashboard|browser|web ?ui|console|app window|portal|status page|"
                 r"list of nodes|settings pane|dialog|wizard|installer|preferences|"
                 r"fields filled|\bform\b", low):
        return {"kind": "app", "title": _short(shot.title, 44),
                "rows": _rows(raw), "flip": 0.45}

    if not strict and (PATH.search(raw) or re.search(
            r"editor|file|config|json|ya?ml|manifest|definition|\bdef\b|block|snippet|code", low)):
        return _file_plate(shot, raw)

    if termish and not strict:
        return _term_plate(shot, blob, low, cmds)

    return None


def _term_plate(shot, blob: str, low: str, cmds: list[str]) -> dict:
    spec: dict = {"kind": "term"}
    label = re.match(r"^`?([a-z][\w.\-]{1,20})`?\s*:", shot.title)
    if label:
        spec["label"] = label.group(1)
    if re.search(r"split[- ]screen|side by side|both", low) and len(cmds) >= 2:
        half = max(1, len(cmds) // 2)
        spec["split"] = True
        spec["headL"], spec["headR"] = _split_heads(blob)
        spec["script"] = _script(cmds[:half])
        spec["script2"] = _script(cmds[half:])
    else:
        spec["script"] = _script(cmds or ["$ " + re.sub(r"\s+", " ", shot.title)[:48]])
    return spec


def _file_plate(shot, raw: str) -> dict:
    path = PATH.search(raw)
    lines = [[c, 0] for c in CMD.findall(raw)
             if not c.strip().startswith(("$", "#", ">"))][:9]
    if not lines:
        lines = [[w, 0] for w in _wrap(shot.note or shot.title, 34)][:9]
    if lines:
        lines[min(len(lines) - 1, 2)][1] = 1      # one highlighted line to read to
    return {"kind": "file", "name": path.group(1) if path else "file",
            "lines": lines, "note": ""}


def _finish(spec: dict, blob: str) -> dict:
    kind = spec.get("kind")
    if kind == "card" and "line" not in spec:
        spec["line"] = _short(blob, 64)
    if kind == "card" and "glyph" not in spec:
        spec["glyph"] = _glyph(blob)
    if kind == "term" and "script" not in spec:
        cmds = _commands(blob) or ["$ " + _short(blob, 40)]
        spec["script"] = _script(cmds)
    if kind == "scene" and "label" not in spec:
        spec["label"] = _short(blob, 52)
    if kind == "wait":
        spec.setdefault("to", 30)
        spec["to"] = int(float(spec["to"]))
    return spec


def _split_heads(blob: str) -> tuple[str, str]:
    names = re.findall(r"`([a-z][\w.\-]{1,20})`", blob)
    uniq: list[str] = []
    for n in names:
        if n not in uniq:
            uniq.append(n)
    return (uniq[0] if uniq else "left", uniq[1] if len(uniq) > 1 else "right")


def _rows(raw: str) -> list[list[str]]:
    """Rows for an app plate: backticked names first, then a 'a / b / c' list."""
    seen: list[str] = []
    for n in re.findall(r"`([a-z][\w.\-]{1,24})`", raw):
        if n not in seen and not n.startswith(("$", "#")):
            seen.append(n)
    if not seen:
        m = re.search(r"((?:[\w*][\w *\-]{1,22}\s*/\s*){1,3}[\w*][\w *\-]{1,22})", raw)
        if m:
            seen = [_short(x, 22) for x in m.group(1).split("/") if x.strip()]
    rows = [[n, "set"] for n in seen[:4]]
    return rows or [["item-1", "ready"], ["item-2", "idle"]]


def _short(text: str, n: int = 56) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"`", "", text)).strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def _wrap(text: str, width: int) -> list[str]:
    words, line, out = re.sub(r"\s+", " ", text).split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out
