---
url: https://example.com/docs/backups
eyebrow: full walkthrough →
---

# V3 — Restoring a backup

**Pairs with:** `CH03 - Backups`
**Dramatized moment:** A database is dropped on purpose and is back in ninety seconds.

## Beat sheet

| # | Beat | Budget | Content |
|---|------|--------|---------|
| 1 | **Relatable problem** | 0:00–0:20 | Cold open on a terminal, `$ DROP DATABASE orders;` already typed. On-screen line within 2 s: *"the backup you never tested is not a backup."* |
| 2 | **The fix** | 0:20–0:40 | Face enters. Point-in-time restore, and the one command that proves it works. |
| 3 | **Punchline** | 0:40–0:50 | "I deleted production. On purpose. Twice." |
| 4 | **Demo** | 0:50–2:00 | The real restore, on real data, timed on screen. |
| 5 | **Hook** | 2:00–2:12 | "Restores are easy. Knowing the backup is good is the hard part — next video." |
| 6 | **Call to action** | 2:12–2:22 | Subscribe, framed as following the build. |
| 7 | **Book pointer** | 2:22–2:30 | End card. |

## Shot list

| # | Shot | Notes |
|---|------|-------|
| 1 | Terminal on `db-1`: the drop, then the empty table list | Beat 1. Machine label `db-1`. Problem line burned in. |
| 2 | Talking head | Beat 2. The face enters on the fix, not before. |
| 3 | Motion-graphic card: a snapshot rolling backwards on a timeline | Beat 3. Caption overlay: "I deleted production. On purpose." |
| 4 | Terminal on `db-1`: `pg_restore --clean --dbname orders latest.dump` | Beat 4. Command as typed before output. |
| 5 | Timelapse: the restore running, wall clock on screen | Beat 4. Do not fake the wait — it takes about 90 s. |
| 6 | Terminal on `db-1`: `psql -c "select count(*) from orders"` — the row count matches | Beat 4. Box the number. |
| 7 | End card | Beat 7, fixed wording. |

## Asset checklist

- [ ] `db-1` screen capture — shots 1, 4, 6
- [ ] Wall-clock plate for the restore wait (shot 5)
- [ ] Punchline motion-graphic card

## Caption / end-card copy

**Punchline caption (beat 3):**

```
I deleted production. On purpose. Twice.
```

**End card (beat 7):**

```
Full walkthrough → Backups, Chapter 3
https://example.com/docs/backups
```
