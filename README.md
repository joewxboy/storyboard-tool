# storyboard-tool

Turn a markdown transcript, outline, or beat sheet into an **interactive video
storyboard** — a single self-contained HTML page that plays the sheet against
its real clock, with placeholder plates you swap for footage later.

It answers the question you cannot answer by reading a script: *does this
actually fit?* Scrub the demo beat and you can see that 70 seconds is not
enough for nine commands before anyone rigs a camera.

```
./bin/storyboard build notes/episode-3.md -o out/ep3.html --open
```

No dependencies — Python 3.10+ standard library only. The output has no build
step and no sidecar assets: open it from disk, drop it on a static host, or
publish it as an artifact.

## Where this came from

Generalized from the one-off animatic player written for the *DIY Edge
Computing* video series (`joe-diy/DIY-EdgeComputing/docs/video/`). The engine —
the frame, the beat-segmented scrub bar, the plate builders, the burned-in
caption / lower-third / machine-label furniture — is that code with every
series-specific detail lifted out into data.

## What it reads

Three input shapes, tried in order. Whatever the parser guesses can be
overridden (see **Overrides**).

**1 · Beat sheet** — the richest form. A `## Beat sheet` table that partitions
the clock, plus a `## Shot list` table:

```markdown
## Beat sheet

| # | Beat | Budget | Content |
|---|------|--------|---------|
| 1 | **Relatable problem** | 0:00–0:20 | Cold open inside the pain. |
| 2 | **The fix**           | 0:20–0:40 | Name the thing that kills it. |

## Shot list

| # | Shot | Notes |
|---|------|-------|
| 1 | Terminal on `db-1`: the drop, then the empty table list | Beat 1. Machine label `db-1`. |
| 2 | Talking head | Beat 2. The face enters on the fix, not before. |
```

Also read when present: `## Asset checklist` (becomes a tick-off rail) and
`## Caption / end-card copy` (fenced blocks keyed by beat).

**2 · Outline** — headings that carry their own timecodes, with bullets for
shots:

```markdown
## Cold open (0:00–0:15)

- Terminal: a deploy rolling back at 2am, pager going off
- Talking head: "we shipped it to everyone at once. that was the mistake."
```

**3 · Transcript** — prose with no timings at all. Sections become beats,
paragraphs become narration plates, and the clock is estimated from the word
count at `--wpm` (default 150). Useful for asking "is this script 90 seconds or
four minutes?"

See `examples/` for one of each.

## What it produces

A player with:

- the **frame** at your aspect ratio (`--aspect 9:16` by default, plus `16:9`,
  `1:1`, `4:5`, `2.39:1`), safe-area and thirds guides;
- **plates** — animated placeholders per shot: typing terminals, code files,
  title cards, talking head, app windows, waiting clocks, chat exchanges,
  progress bars, narration text, or a real still once you have one;
- **burned-in furniture** — captions, lower-thirds for commands, machine
  labels, the cold-open problem line, the fixed end card;
- a **scrub bar** segmented by beat and ticked by shot, `1×`/`2×`/`0.5×`;
- **rails** — beats, shot list (click to seek), asset checklist;
- **deep links** — `#e=2&t=95` opens that episode parked on that second.

Keys: `space` play/pause · `←`/`→` nudge a second · `[` / `]` previous/next
episode.

## Commands

```bash
# markdown → player
./bin/storyboard build SHEET.md [MORE.md ...] -o out.html

# a directory of sheets becomes one multi-episode player
./bin/storyboard build docs/video/ --exclude '00-*.md' --exclude 'index.md' -o season.html

# parse only: print the timing table, write nothing
./bin/storyboard check SHEET.md

# markdown → JSON model (hand-edit it) → player
./bin/storyboard extract SHEET.md -o model.json
./bin/storyboard render model.json -o out.html
```

Useful flags: `--title`, `--tagline`, `--chip TEXT` (repeatable),
`--theme midnight|slate|paper|my-theme.json`, `--accent '#4C8DFF'`,
`--url` (default end-card link), `--duration` (fallback length),
`--wpm`, `--start N` (episode to open on), `--open`.

## Overrides

Three levels, cheapest first.

**Front matter** on the markdown file:

```markdown
---
code: V3
title: Restoring a backup
duration: 2:30
url: https://example.com/docs/backups
problem: the backup you never tested is not a backup.
---
```

**A plate marker** in a shot's notes, when inference picks wrong:

```markdown
| 4 | The restore running | [plate: wait to=90] Do not fake the wait. |
| 8 | The row count matches | [plate: image src=stills/shot-8.png] |
```

**The JSON model** — `extract`, edit, `render`. Every plate is plain data; see
`MODEL.md` for the schema and the full plate reference. A file named
`SHEET.storyboard.json` next to `SHEET.md` is merged automatically on build.

## Swapping in real footage

The plates are placeholders. As each shot gets captured, point it at the file:

```json
{"kind": "image", "src": "stills/V07-shot-8.png", "caption": "same container, new secret"}
```

Relative paths resolve against the HTML page, so keep the stills beside it.

## Layout

```
bin/storyboard          run without installing
storyboard/parse.py     markdown → model (the three input shapes)
storyboard/plates.py    which plate a shot gets, and what it says
storyboard/model.py     the data model + JSON round trip
storyboard/render.py    model → one self-contained HTML page
storyboard/theme.py     colour and type tokens
storyboard/assets/      player.html · player.css · player.js
tests/smoke.py          parse the examples, assert the model is playable
```

## Test

```bash
python3 tests/smoke.py
```

## Licence

Apache License 2.0 — see [LICENSE](LICENSE).
