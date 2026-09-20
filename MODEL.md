# The storyboard model

`extract` writes this; `render` reads it; the player consumes it verbatim as
`window.STORYBOARD`. Times are seconds (floats). Everything is plain JSON, so
hand-editing an extracted model is the supported way to take control.

```jsonc
{
  "title": "Season animatics",       // page title and heading
  "tagline": "One line under it.",
  "aspect": "9:16",                  // 9:16 · 16:9 · 1:1 · 4:5 · 2.39:1
  "chips": ["1080 × 1920", "2:30"],  // small header chips; auto if omitted
  "notes": [{"heading": "...", "body": "HTML allowed"}],  // footer columns
  "episodes": [ /* see below */ ]
}
```

## Episode

```jsonc
{
  "code": "V7",                      // short label on the tab
  "title": "Secrets management",
  "chapter": "CH06 Secrets",         // second line on the tab
  "dur": 150,                        // the clock, in seconds
  "moment": "Rotate a credential; the fleet re-pulls.",   // shown under the title
  "problem": "the token is in a public repo.",            // burned over the cold open
  "problemUntil": 20,                // ...until this second
  "beats":   [ /* partition the clock */ ],
  "shots":   [ /* tile the clock */ ],
  "captions": [{"from": 40, "to": 50, "text": "..."}],    // centred, burned in
  "lower":    [{"from": 98, "to": 106, "text": "$ ssh pi@..."}],  // lower-third
  "labels":   [{"from": 98, "to": 120, "text": "laptop"}],        // top-left machine label
  "assets":  ["laptop screen capture — shots 5, 6"],      // tick-off rail
  "endcard": {"eyebrow": "full walkthrough →",
              "line": "Line one<br>line two", "url": "https://..."},
  "endFrom": 142,                    // end card covers the frame from here
  "bonus": false                     // marks the tab as off the critical path
}
```

Invariants the player relies on, and `tests/smoke.py` checks:

- beats are ordered and the last one ends at `dur`;
- shots tile the clock: the first starts at 0, the last ends at `dur`, and
  consecutive shots touch (no gaps, no overlaps);
- every overlay span sits inside `[0, dur]`.

## Beat

```jsonc
{"n": 4, "name": "Demo", "from": 50, "to": 120, "content": "raw markdown cell"}
```

`content` is shown as the beat row's tooltip.

## Shot

```jsonc
{
  "num": 7,                          // as numbered in the sheet; "" is fine
  "from": 50, "to": 62,
  "title": "laptop: hzn secret add",
  "meta": "screen capture · beat 4", // first segment becomes the plate badge
  "note": "Command as typed before output.",
  "plate": { "kind": "term", "...": "..." }
}
```

## Plates

One per shot. `kind` picks the builder; unknown kinds fall back to `scene`.
Each plate animates across the shot's own progress, 0 → 1.

| kind | what it draws | fields |
|------|----------------|--------|
| `term` | a terminal typing its commands | `script`, `label`, `split`, `script2`, `headL`, `headR` |
| `file` | a code/config pane revealing lines | `name`, `lines`, `note` |
| `card` | a title card: glyph + one line | `line`, `glyph` |
| `head` | talking-head placeholder rising into frame | — |
| `scene` | abstract b-roll: hatch, glyph, the shot's words | `label`, `glyph`, `kind` |
| `text` | narration landing word by word on the clock | `text`, `eyebrow` |
| `wait` | an elapsed clock, for waits you must not fake | `to` (seconds), `label`, `label2`, `eyebrow` |
| `app` | a window whose rows resolve as it plays | `title`, `rows`, `flip`, `note` |
| `chat` | a question, a think, an answer | `title`, `q`, `a`, `think`, `badge` |
| `progress` | a progress bar with named stages | `title`, `stages` |
| `image` | a real still or frame grab | `src`, `caption`, `fit` |

### `term.script`

A list of `[text, kind]` lines, revealed by typing speed:

```jsonc
"script": [["$ pg_restore --clean --dbname orders latest.dump", "c"],
           ["done in 88s", "o"],
           ["", "k"]]
```

`c` types the line · `o` appears at once (output) · `k` parks the caret there.
`split: true` runs `script` and `script2` side by side under `headL` / `headR`.

### `file.lines`

`[["line text", 1], ["another", 0]]` — the `1` marks the line highlighted from
45% of the shot onward. `name` is the filename in the title bar.

### `app.rows`

`[["pi-1", "online"], ["pi-2", "offline", "—"]]` — label, end state, optional
start state. Rows resolve in order around `flip` (0 → 1, default 0.45). The
pill colours itself from the state's wording: `online`/`ready` green,
`offline`/`idle` grey, `failed`/`down` red, `pending`/`waiting` amber.

### `glyph`

Generic marks shared by `card` and `scene`: `spark`, `key`, `cloud`, `chip`,
`box`, `arrow`, `check`, `alert`, `doc`. Unknown names fall back to `spark`.

## Theme

`--theme` takes a preset (`midnight`, `slate`, `paper`) or a JSON file setting
any of these tokens; anything left out is inherited from `midnight`:

```jsonc
{
  "ground": "#151217", "panel": "#1D1922", "panel2": "#241F2B",
  "line": "#3A3242", "line2": "#2B2533",
  "ink": "#F3EEF1", "dim": "#A198AA", "dimmer": "#6E6678",
  "accent": "#C51A4A", "accentSoft": "#7A1531",
  "signal": "#7BB02A", "amber": "#E0A040", "alarm": "#E0563D",
  "frame": "#0B090D", "plate": "#0E0B12",
  "display": "\"Archivo\", sans-serif",
  "body": "\"IBM Plex Sans\", system-ui, sans-serif",
  "mono": "\"IBM Plex Mono\", ui-monospace, monospace",
  "scheme": "dark",
  "fonts": "https://fonts.googleapis.com/css2?family=..."   // null to drop the request
}
```

The frame itself stays dark in every preset — it is video, not page.
