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

## Requirements

- **Python 3.10+** — standard library only, nothing to install.
- **ffprobe** *(optional)* — checks a placed take against the slot it has to
  fit. Without it, takes still play; their length is simply not checked.
  Part of ffmpeg: `sudo pacman -S ffmpeg` / `apt install ffmpeg`.
- **inotifywait** *(optional)* — makes `--watch` react instantly instead of
  polling once a second. From inotify-tools.

The built page itself has no build step and no dependencies: open it from
disk, drop it on a static host, or publish it as an artifact. Placed takes are
the exception — they are referenced, not embedded, so they travel with the
page.

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

Useful flags: `--assets DIR`, `--watch`, `--title`, `--tagline`, `--chip TEXT` (repeatable),
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

## Placing real footage

The plates are placeholders. As shots get captured, name the files after the
shot they are and point the build at the directory:

```bash
./bin/storyboard build docs/video/V01-*.md --assets takes/ -o out/v01.html --watch
```

Recognised names — case-insensitive, `-`/`_`/space interchangeable:

| File | Lands on |
|------|----------|
| `V01-shot-6.mp4` | V1, shot 6 — as video |
| `V01-shot-6-take3.mp4` | V1, shot 6, take 3 — the **highest take wins** |
| `V01-shot-6.png` | V1, shot 6 — as a still |
| `shot-6.mp4` | shot 6, when only one episode is being built, or when the file sits in a `V01/` directory |

The episode prefix follows the sheet: `V1` and `V01` both work, and the
trailer's `Ep 0` also answers to `V00`. When a shot has both a still and a
take, the take wins; ties break on modification time.

With `--watch`, leave the page open in a browser while you capture — every new
file rebuilds it. Takes are referenced by a path relative to the output file;
`--assets-url https://…/takes` points them somewhere else instead.

**The length check.** Each placed take is measured with `ffprobe` and compared
to the slot the sheet gives it:

```
takes: 3 placed from 4 files
  ! V1 shot 6: take is 0:23, slot is 0:14 — 9s over
```

The shot rail carries the same thing as a badge (`take · #2 · 0:23 clip · 9s
over slot`), amber when a take is short and red when it overruns. `--tolerance
SECONDS` sets how far a take may miss before it is reported, and `--no-probe`
turns the check off.

Browsers play `.mp4`, `.webm`, `.m4v` and `.ogv`. A `.mov` or `.mkv` is placed
anyway and the build tells you how to transcode it:

```bash
ffmpeg -i V01-shot-6.mov -c:v libx264 -an V01-shot-6.mp4
```

For one-off placement without the naming convention, a plate marker still
works: `[plate: image src=stills/anything.png]`.

## Capturing

Nothing here is needed to use the tool — but for the record, the workflow it
was built around:

```bash
# a still, on Wayland
grim -g "$(slurp)" takes/V01-shot-6.png

# trim a take to its slot, no re-encode
ffmpeg -ss 4.5 -t 14 -i raw.mp4 -c copy takes/V01-shot-6-take2.mp4
```

Screen and camera takes come out of OBS, recording straight into `takes/`
under the shot's name. Anything that needs real assembly goes to an editor;
this page is for judging timing, not for cutting.

## Layout

```
bin/storyboard          run without installing
storyboard/parse.py     markdown → model (the three input shapes)
storyboard/plates.py    which plate a shot gets, and what it says
storyboard/takes.py     finds captured footage and places it on its shot
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
