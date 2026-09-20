#!/usr/bin/env python3
"""Self-test: parse the examples, assert the model is playable, render once.

    python3 tests/smoke.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storyboard.model import Storyboard                     # noqa: E402
from storyboard.parse import parse_file, parse_span, parse_time  # noqa: E402
from storyboard.render import render                        # noqa: E402
from storyboard.theme import load_theme                     # noqa: E402

KINDS = {"term", "file", "card", "head", "scene", "wait", "app",
         "chat", "progress", "image", "video", "text"}
fails: list[str] = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


check(parse_time("1:30") == 90, "parse_time m:ss")
check(parse_time("90s") == 90, "parse_time 90s")
check(parse_span("0:20–0:40") == (20, 40), "parse_span en dash")
check(parse_span("2:00 - 2:12") == (120, 132), "parse_span hyphen")
check(parse_span("no times here") is None, "parse_span miss")

episodes = []
for md in sorted((ROOT / "examples").glob("*.md")):
    ep = parse_file(md)
    episodes.append(ep)
    where = md.name

    check(ep.duration > 0, f"{where}: duration")
    check(ep.beats, f"{where}: has beats")
    check(ep.shots, f"{where}: has shots")

    for a, b in zip(ep.beats, ep.beats[1:]):
        check(b.frm >= a.frm, f"{where}: beats out of order")
    check(abs(ep.beats[-1].to - ep.duration) < 0.5, f"{where}: beats reach the end")

    # shots must tile the clock with no gap and no overlap
    check(abs(ep.shots[0].frm) < 0.01, f"{where}: first shot starts at 0")
    check(abs(ep.shots[-1].to - ep.duration) < 0.01, f"{where}: last shot ends at the end")
    for a, b in zip(ep.shots, ep.shots[1:]):
        check(abs(b.frm - a.to) < 0.51, f"{where}: gap/overlap at {a.to:.1f}s")
        check(a.to > a.frm, f"{where}: zero-length shot {a.num}")

    for s in ep.shots:
        check(s.plate.get("kind") in KINDS, f"{where}: unknown plate {s.plate.get('kind')}")
    for span in list(ep.captions) + list(ep.lower) + list(ep.labels):
        check(0 <= span.frm < span.to <= ep.duration + 0.01,
              f"{where}: overlay out of range ({span.text[:20]})")

    # the model must survive a JSON round trip unchanged
    from storyboard.model import episode_from_json
    check(episode_from_json(json.loads(json.dumps(ep.json()))).json() == ep.json(),
          f"{where}: json round trip")

# --- take discovery ---------------------------------------------------------
import tempfile                                                    # noqa: E402
from storyboard.takes import attach, episode_keys, scan            # noqa: E402

beat_sheet_ep = next(e for e in episodes if e.source.endswith("beat-sheet.md"))
check(episode_keys(beat_sheet_ep) >= {"V3", "V03"}, "episode keys: V3 and V03")

with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    for name in ("V03-shot-4.mp4", "V03-shot-4-take2.mp4", "V03-shot-6.png",
                 "V04-shot-1.mp4", "notes.txt", "random.mp4"):
        (d / name).write_bytes(b"x")
    found = scan([d])
    check(len(found) == 4, f"scan found {len(found)} takes, expected 4")

    notes = attach([beat_sheet_ep], found, out_dir=d, probe=False)
    by_num = {int(s.num): s for s in beat_sheet_ep.shots}
    check(by_num[4].plate["kind"] == "video", "shot 4 takes the video")
    check(by_num[4].asset["take"] == 2, "highest take wins")
    check(by_num[6].plate["kind"] == "image", "shot 6 takes the still")
    check(by_num[4].plate["src"] == "V03-shot-4-take2.mp4",
          f"src is relative to the output: {by_num[4].plate['src']}")
    check(any("no shot 1" not in n for n in notes) or not notes,
          "other episodes' files are left alone")
    check(all(s.asset is None for n, s in by_num.items() if n not in (4, 6)),
          "only matching shots are touched")

    # final beats a numbered take, and coverage totals both ways
    (d / "V03-shot-6-final.png").write_bytes(b"x")
    attach([beat_sheet_ep], scan([d]), out_dir=d, probe=False)
    check(by_num[6].asset["state"] == "final", "-final marks the shot final")
    check(by_num[4].asset["state"] == "draft", "a numbered take is a draft")
    cov = beat_sheet_ep.coverage()
    check(cov["captured"] == 2 and cov["final"] == 1 and cov["draft"] == 1,
          f"coverage counts: {cov}")
    covered = sum(s.to - s.frm for s in (by_num[4], by_num[6]))
    check(abs(cov["seconds"] - covered) < 0.01, "coverage seconds")
    check(cov["pct"] == round(100 * covered / beat_sheet_ep.duration), "coverage pct")

    # the length check
    slot = by_num[4].to - by_num[4].frm
    found2 = scan([d])
    for t in found2:
        t.duration = slot + 9 if t.shot == 4 else None
    notes = attach([beat_sheet_ep], found2, out_dir=d, probe=False)
    check(any("9s over" in n for n in notes), f"overrun reported: {notes}")
    check(by_num[4].asset.get("over") == 9, "overrun recorded on the shot")

sb = Storyboard(title="smoke", episodes=episodes)
html = render(sb, load_theme("midnight"))
check("window.STORYBOARD" in html, "render: data injected")
check("__DATA__" not in html and "__CSS__" not in html, "render: all tokens replaced")
check(len(html) > 40_000, "render: page looks complete")

beat_sheet = next(e for e in episodes if e.source.endswith("beat-sheet.md"))
check(beat_sheet.code == "V3", f"beat sheet code: {beat_sheet.code!r}")
check(len(beat_sheet.beats) == 7, "beat sheet: 7 beats")
check(beat_sheet.endcard.get("url", "").startswith("https://"), "beat sheet: end-card url")
check(any("deleted production" in c.text for c in beat_sheet.captions),
      "beat sheet: punchline caption")
check(beat_sheet.assets, "beat sheet: asset checklist")
check(any(l.text == "db-1" for l in beat_sheet.labels), "beat sheet: machine label")

transcript = next(e for e in episodes if e.source.endswith("transcript.md"))
check(all(s.plate["kind"] == "text" for s in transcript.shots),
      "transcript: prose becomes text plates")

if fails:
    print(f"FAIL ({len(fails)})")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"ok — {len(episodes)} episodes, "
      f"{sum(len(e.shots) for e in episodes)} shots, {len(html)//1024} KB page")
