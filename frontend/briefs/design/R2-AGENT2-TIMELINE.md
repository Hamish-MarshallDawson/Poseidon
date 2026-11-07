# Round 2 · Agent 2 report: scrub-back timeline

File `tR0vsJQJlm1lvLKOgUJhOg`, new page **R2 · 2 Timeline**: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-1043
I worked only on this page. I created no variables or collections. Every fill, stroke and text colour is bound to DVM Theme or DVM Signals, and every text size and line height is bound to DVM Text size.

## What I made

| Frame | Link | What |
|---|---|---|
| Read me | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=58-3402 | Purpose, page index, bar anatomy, principles |
| Timeline bar · Light | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-7582 | Live, replay (idle), hover, dragging and playing at 6 h, plus replay at 1 h and 24 h, each with a caption. Also the track legend and the keyboard, pointer and touch reference |
| Timeline bar · Dark | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-8331 | The same frame with DVM Theme = Dark |
| Map in replay · Light | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-6177 | A 1440 px map at 13:05:12Z: replay edge and tab, status line, "as of" ship popup, ghost circle, a bar instance, numbered notes |
| Map in replay · Dark | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-6362 | The same frame in Dark |
| For the dashboard | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-2503 | The wrapper (Light) around the component set |
| **R2/Timeline/Bar** (component set) | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-2502 | 15 variants |
| Developer notes | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=58-3411 | Each control mapped to its message, behaviour while dragging, accessibility |

The example clock is **Sun 8 Nov 14:07:12Z**, so the 24 h range includes the forecast freeze (Sat 23:00Z) and the outcomes that resolved on Sunday morning.

## Component for agent 5

- **Name:** `R2/Timeline/Bar`, 1440 × 88 px. The hover tooltip and the drag readout overflow up to about 60 px above the bar (`clipsContent` is off).
- **Variant properties:**
  - `State` = `live` | `replay` | `hover` | `dragging` | `playing`. `replay` is the idle state: paused in the past.
  - `Range` = `1 h` | `6 h` | `24 h`. 6 h is the default.
- **No explicit modes on the component.** An instance follows the dashboard frame's DVM Theme, Signals and Text size modes. The wrapper frame alone is set to Light.
- The brief listed four states (live, replay, dragging, playing). I added `hover` so the time tooltip is a real variant too.

## Key decisions and why

- **Live is quiet; replay is unmistakable but calm.**
  - Live: a small `accent/default` dot, "LIVE · following now · 1×", and a blue playhead pinned to the right end. A short blue growing edge stands in for the track filling up.
  - Replay:
    - The bar's top edge goes from 1 px `border/default` to 2 px `text/primary`.
    - An inverted ink REPLAY chip appears, and the readout shows `13:05:12Z −1 h 02 min`.
    - A filled "Back to live [L]" button appears, the only filled button on the bar.
    - The map gets the same 2 px ink edge and a REPLAY tab.
  - No new colours, no flashing, nothing red.
- **Every surface states its moment.** The status line, the popup ("AS OF 13:05:12Z" chip) and lists show values as of the shown time. Nothing after it is drawn. The popup footer, marked with the blue "now" dot, says what is true live when that differs ("Live now: no AIS received since 13:20Z (47 min); reception normal nearby").
- **The playhead colour carries the mode:** blue for live, ink for replay. The blue NOW mark stays at the right end of the track in replay, so you can see how far back you are.
- **Coverage strip under the track:**
  - Solid (`border/default`): the raw log has data.
  - `coverage/degraded` with a dotted edge: reception degraded nearby.
  - Hatched over `coverage/dead`: our own ingest stalled (`own_stall`).
  - Dashed empty outline: not in our log.
  - So a blank stretch never reads as "no ships".
- **Markers are shape first** and use the round 1 grammar:
  - Gaps are spans in `ship/dark`, matching the hollow and ghost language.
  - Meetings are rings, as in v2.
  - Outcomes are ink squares, kept deliberately un-celebratory.
- **Times:** UTC with Z everywhere. Behind-live is rounded down to whole minutes.

## Event markers

| Marker | Glyph | Variable |
|---|---|---|
| No AIS received, gap closed | Span with a solid edge and ghost fill, start to end | `ship/dark`, `ship/ghost-fill` |
| No AIS received, still silent | Span with a dashed edge, running to now | `ship/dark`, `ship/ghost-fill` |
| Possible spoofing | Small solid triangle | `ship/spoof` |
| Meeting (two ships alongside) | 9 px ring | `ship/normal` |
| Forecast frozen and committed (Sat 23:00Z) | Full-height line with a small flag | `text/primary` |
| Outcome hit / miss / censored | Filled / hollow / dashed 7 px square | `text/primary`, `text/muted` |
| Coverage: data / degraded / own_stall / not in log | 5 px strip under the track | `border/default`, `coverage/degraded`, `coverage/dead` + hatch in `text/secondary`, dashed `border/default` |

- Gaps that overlap in time sit in two lanes.
- Only events for watchlisted ships and the selected ship are drawn. Markers closer than 6 px merge into a count.
- Clicking a marker seeks to its start and selects the ship.

## Speeds, steps, keys

- **Speeds:** 1×, 10×, 60×, 300×. Speed is disabled in live, and the default replay speed is 60×.
- **Steps (arrow / Shift + arrow):**
  - 1 h range: 1 min / 10 min
  - 6 h range: 5 min / 30 min
  - 24 h range: 15 min / 2 h
- **Keys:** Space plays or pauses. In live, pausing freezes the view at that second and enters replay. L goes back to live.
- **Ticks:**
  - 1 h: every 10 min (minor ticks every 5)
  - 6 h: every hour (minor every 15 min)
  - 24 h: every 3 h (minor every hour); midnight is labelled "Sun 00:00Z"
- **Custom range and zoom:**
  - "Custom" opens UTC from and to fields, clamped to `status.replay.from_ts` / `to_ts`.
  - The wheel over the track zooms around the cursor, from 15 min to 7 days. Shift + wheel pans.
  - Double-clicking the track goes back to the last preset.
- **Pointer and touch:**
  - The track uses `cursor: ew-resize`; markers use `pointer`.
  - On touch: tap to seek, drag to scrub (the readout sits 56 px above the finger), pinch to zoom, long-press for the tooltip. There is no hover state.

## Message mapping (DATA.md §4.3)

| Control | Message | Client does |
|---|---|---|
| Click track, release a drag | `{"type":"replay","action":"seek","t":<ms>}` | Enter replay (paused). Show "Loading …" until `status` (mode `replay`) and a snapshot with `now_ts ≈ t` arrive |
| While dragging | No message per pointer move | Move the playhead and readout locally. Send a trailing seek after the pointer rests 150 ms (one request in flight), plus a final seek on pointer-up. As a preview, keep the last frame under `focus/veil` and draw cached trails only |
| Play | **Proposed** `{"type":"replay","action":"play"}` | Until it exists, resend `speed` and have the server treat that as resume |
| Pause | `{"type":"replay","action":"pause"}` | In live: seek to the latest `now_ts`, then pause |
| Speed | `{"type":"replay","action":"speed","speed":60}` | Disabled in live |
| Step | `seek` with `t` = shown ± step | Debounce key repeat |
| Back to live | **Proposed** `{"type":"replay","action":"live"}` | The server replies with `status` (mode `live`) and a snapshot |
| Range, zoom, Custom | Scale is client-only; **proposed** `{"type":"timeline","from_ts","to_ts"}` | Fetches the markers and coverage for the window |
| `status` (server) | `mode`, `speed`, `now_ts`, `replay.from_ts/to_ts` | Drive the bar state, speed, playhead and log extent |
| `delta.now_ts` | Every 1000 ms | Advance the playhead while playing (interpolate between deltas). A gap in `seq` means freeze, show "Reconnecting…", and take a snapshot |

## Decisions for Hamish (and Jake, who owns the data model)

1. **There's no `play` or "back to live" action** in the frozen client messages. I've proposed `action: "play"` and `action: "live"`.
2. **`status` has no paused flag.** I've proposed `"paused": true`, or treating speed 0 as paused.
3. **The socket sends no event history for a time window.** The track's markers and coverage strip for 6 h or 24 h need one. I've proposed a `timeline` request and reply, built from `gaps`, `spoofs`, `outcomes`, FeedStatus `stall` windows and CoverageCell buckets. Without it, the track can only show events seen since page load.
4. **Seeking doesn't promise a snapshot.** It should be specified that after a `seek` the server sends `status` and then a `snapshot` at the new time.
5. **Replay writes `RiskScore.mode = "replay"` rows.** The UI can show them labelled "as of", but the prospective evaluation must keep using `mode = live` only.
6. **Hover as a variant:** I added it as a fifth `State` value beyond the brief's four. Drop it if agent 5 wants only four.

## Gaps in the variables

- **No strong "coverage ok" role.** `coverage/ok` (10–12 % alpha) is invisible as a 5 px strip, so "raw log has data" uses `border/default`.
- **`coverage/degraded` is faint in Dark** at strip size. It's readable together with its dotted edge, but a solid `coverage/degraded-strong` would help.
- **No "replay" or "past" role.** Replay reuses `text/primary` (ink edge, inverted chip) and `bg/app` for the chip text. That works in all four themes, but a named role would make the intent explicit.
- **No "live" role.** Live uses `accent/default`, which is also the selected-ship colour (`ship/selected` aliases it). They sit in different places (bar versus map), so I left it.
- **Page backgrounds can't take variables**, so the page background is the hex value of dusk `bg/app`.

## Not checked

- I checked Light and Dark only (Signals = Standard, Text size = Default). The bar is fixed at 88 px, so Large and Largest text will crowd it.
- Marker positions in the frames are hand-placed example data, not real events.
