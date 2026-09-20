# Shipping a feature flag (0:00–1:40)

A short explainer cut from an outline rather than a full beat sheet: each
heading carries its own timecode and its bullets become shots.

## Cold open (0:00–0:15)

- Terminal: a deploy rolling back at 2am, pager going off
- Talking head: "we shipped it to everyone at once. that was the mistake."

## The idea (0:15–0:40)

- Motion-graphic card: one dial, 0% to 100%
- Editor: `flags.json` with `checkout_v2` set to `0.05`

## The demo (0:40–1:20)

- Terminal on `web-1`: `curl -s localhost:8080/flags | jq .checkout_v2`
- Dashboard: error rate by cohort, flagged cohort flat
- Terminal on `web-1`: dial to 50%, then `kubectl rollout status deploy/web`

## Land it (1:20–1:40)

- Talking head: "ship to five percent. watch. then ship to everyone."
- End card
