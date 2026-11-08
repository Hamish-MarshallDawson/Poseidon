# POSEIDON intro video: 20 s shot script

A 20-second opener for the project demo, structured shot by shot so that each shot can be generated in Higgsfield and cut together to music. The music sets the timing.

- **Length:** 20.0 s
- **Format:** 16:9, 1920×1080, 24 fps (also export a 9:16 cut-down if needed)
- **Look:** dark, minimal, no visual clutter. Near-black navy ocean, thin lines, a single accent colour.
- **Tone:** suspense, then capability, then confidence.
- **Audio:** suspense score from frame 0, AIS ping sound effects, an ElevenLabs voiceover from 5.0 s, a hard cut to silence and black on the beat at 16.0 s, then the logo and a fade.

---

## Visual language (match the real software)

Keep the generated footage consistent with how POSEIDON draws things, so that the cut from the stylised opening to the real UI feels like one continuous world.

| Element | How POSEIDON shows it | In the video |
|---|---|---|
| Ship broadcasting AIS | A small slim hull marker pointing along its heading | A white or pale-grey arrowhead hull, top-down |
| AIS ping | A position update, roughly every few seconds | A thin ring radiating out from the hull on each ping, fading as it grows, synced to a soft sonar "tick" |
| Ship goes dark | Pings stop. A "last heard" marker stays at the last fix with its age ("last heard 2 min ago") and a running clock | The rings stop, the hull dims to a hollow outline and freezes, and a small label appears: `LAST HEARD 00:00:03` with the timer counting up |
| Model prediction | Dashed route line plus pink (magenta) 80% and 95% circles: "Estimated position now, 80% chance within X km" | Magenta circles bloom from the last-heard point, with a dashed line running ahead of the hull |
| Watchlist flag | Small tag with rank and 6 h go-dark estimate | A tag next to Sabrina, e.g. `01 · 6 h estimate` |
| Map | Coastlines, a quiet basemap and the live ship field | The coastline draws itself in as thin lines, then the heat map breathes in |
| UI | Live chip (`LIVE · 18,279 ships`), Review, Display, timeline scrubber, ship window with Brief me and Add to review | Panels slide in from the edges, crisp and flat |

Use the dark theme throughout: near-black navy (`#0B1220`-ish) water, slate land, white hulls, magenta (`#E0218A`-ish) predictions.

**Vessel name:** "SABRINA" is fictional. Don't show a real MMSI, IMO, flag or company. If any number is visible, use an obviously illustrative one.

---

## Music and timing grid

Pick or score a suspense track at **120 BPM**, so that a beat is 0.5 s and a bar is 2.0 s. Every cut below lands on the grid.

| Time | Music |
|---|---|
| 0.0 | Low drone and a pulse begin, quiet |
| 4.0 | Downbeat. The drone drops out for one beat as the ships go dark: a sudden absence |
| 5.0 | The pulse returns under the voiceover |
| 8.0 | The build starts: percussion enters and layers stack every bar |
| 11.0 to 16.0 | Accelerating rhythm. A riser, with hits getting closer together (rhythmic acceleration, not tempo change: 1/4 notes, then 1/8, then 1/16) |
| **16.0** | **Hard stop on the downbeat**, then a single low impact as the screen goes black |
| 16.25 to 18.0 | A ring-out or reverb tail under the logo |
| 18.0 to 20.0 | Music and picture fade to black together |

---

## Shot list

### Shot 1: the lone ship (0.0 to 2.0 s, bar 1)

- **Picture:** top-down view of a dark, empty ocean. One small white hull glides slowly left to right through the centre-left third. Each second, a thin ring radiates out from it and fades. A faint grain or scanline texture. No map and no UI.
- **Sound:** music starts with the drone. A soft sonar ping on each ring (at 0.0, 1.0 and 2.0 s).
- **Higgsfield prompt:**
  > Top-down view of a vast dark navy ocean at night, minimalist vector style. A single small white arrowhead-shaped ship icon moves slowly left to right. Every second, a thin white circular ring radiates outward from the ship and fades, like a sonar ping. Very dark, high contrast, clean flat graphics, subtle film grain, no text, no land, cinematic, suspenseful. Slow steady camera, slight drift.

### Shot 2: a second ship joins (2.0 to 4.0 s, bar 2)

- **Picture:** a second hull enters from the bottom-right edge of the frame, also pinging, on an intercepting course. The two converge and settle into travelling side by side, close together, matching speed: a rendezvous. Their rings overlap.
- **Sound:** a second ping, slightly detuned, alternating with the first. The drone rises a little.
- **Higgsfield prompt:**
  > Same dark navy ocean, minimalist top-down vector style. A second small white ship icon enters from the bottom-right edge of the frame and curves to meet the first ship. Both ships emit thin white sonar rings every second. They come alongside each other and travel together, very close, matching speed. Suspenseful, clean, high contrast, subtle grain, no text.

### Shot 3: both go dark (4.0 to 5.0 s)

- **Picture:** on the 4.0 s downbeat, both ships' rings stop. Both hulls dim to hollow outlines and freeze in place. A small monospace label fades in beside them: `LAST HEARD 00:00:01`, and the seconds start counting up. Everything else is still.
- **Sound:** the music drops out for one beat. Silence, then a single low heartbeat thud at 4.5 s.
- **Higgsfield prompt:**
  > Same scene. Suddenly both ship icons stop emitting rings. Both icons fade from solid white to thin hollow outlines and stop moving. A small white monospace text label appears next to them reading "LAST HEARD 00:00:01" with the seconds counting up. Stillness, tension, darkness. Minimalist vector, high contrast.

  The "LAST HEARD" text is better added in the edit (After Effects, CapCut or Premiere) than generated, because AI-generated text tends to warp.

### Shot 4: the voiceover begins (5.0 to 8.0 s)

- **Picture:** a slow push-in on the frozen outlines. The timer keeps counting. A small tag snaps on beside one hull: `SABRINA · 01 · 6 h estimate`.
- **Sound:** the voiceover starts at 5.0 s and the pulse returns underneath.
- **Higgsfield prompt:**
  > Slow cinematic push-in toward two hollow white ship outlines frozen on a dark navy ocean. Minimalist vector style. A small rectangular white tag with a thin border appears next to one ship. Suspenseful, calm, high contrast.

  Add the tag text in the edit.

### Shot 5: the system builds itself (8.0 to 11.0 s)

This is the shot that changes the video from a story into the product. Build it from screen recordings of the real POSEIDON UI in the dark theme, masked and revealed in layers. Higgsfield can provide the transitions between the layers.

| Time | Layer that appears |
|---|---|
| 8.0 | **Predictions first:** magenta 80% and 95% circles bloom out from Sabrina's last-heard point, and a dashed route line extends ahead. The label "Estimated position now, 80% chance within 14 km" ticks in. |
| 8.75 | **The map:** coastlines draw themselves in as thin lines, then the land fills in and the heat map breathes in softly. |
| 9.5 | **Every other ship:** thousands of hulls pop in across the sea in a ripple outward from Sabrina. The live chip counts up: `LIVE · 18,279 ships`. |
| 10.25 | **The UI:** the Review panel, Display button, timeline scrubber and Legend slide in from the edges, crisp and flat. |

- **Sound:** each layer lands on a beat (8.0, 8.75, 9.5 and 10.25 s are close enough to the grid to feel right). Add a soft whoosh or click on each.
- **Higgsfield prompt (transition plate):**
  > Dark navy minimalist map. Magenta glowing concentric circles expand from a single point, then thin white coastline lines draw themselves across the frame, then thousands of tiny white ship icons appear in a ripple outward, then flat interface panels slide in from the screen edges. Clean, high-tech, cinematic, high contrast, fast but smooth.

### Shot 6: using the software, faster and faster (11.0 to 16.0 s)

These are real screen recordings of POSEIDON on the live site, in the dark theme. Record each beat as a separate 1 to 2 s clip with lots of mouse and camera movement, then cut them on the grid with each clip shorter than the last.

| Cut at (s) | Length | Action |
|---|---|---|
| 11.0 | 1.0 | Smooth pan across the Baltic, ships streaming |
| 12.0 | 0.75 | Click a dark ship. The ship window opens with its "last heard" clock and prediction circles. |
| 12.75 | 0.75 | Press **Brief me**. The briefing text types in. |
| 13.5 | 0.5 | Open **Review**, with the go-dark ranking and "Chance of going dark in the next 6 h" |
| 14.0 | 0.5 | Scrub the **timeline** back. Ships rewind along their tracks. |
| 14.5 | 0.375 | **Display** menu: toggle radar detections and GFW gap events on |
| 14.875 | 0.375 | Zoom hard into a strait. The heat map dissolves into individual hulls. |
| 15.25 | 0.25 | **Compare** two ships side by side |
| 15.5 | 0.25 | A collaboration session: a teammate's face and cursor on the map |
| 15.75 | 0.25 | Snap back to Sabrina's prediction circles, the final image before the cut |

- **Sound:** the riser, with hits on every cut.
- **Editing:** add motion blur and a slight speed ramp inside each clip, so that the motion keeps accelerating even within a clip.

### Shot 7: cut to black, then the logo (16.0 to 18.0 s)

- **Picture:** a **hard cut to pure black at exactly 16.0 s**, on the downbeat. At 16.25 s the POSEIDON logo fades or snaps in, centred and white on black. Use `frontend/public/Logo/Poseidon_White.png` (or the wordmark `poseidon-wordmark.png`). Optionally, one single sonar ring radiates out from behind the logo and fades, echoing shot 1.
- **Sound:** the music stops dead on the cut, then a single low impact and a ring-out.

### Shot 8: fade out (18.0 to 20.0 s)

- **Picture:** the logo and black fade to full black by 20.0 s.
- **Sound:** the ring-out and music fade to silence together by 20.0 s.

---

## Voiceover (ElevenLabs)

The voiceover starts at **5.0 s**. The first line has to finish in about 3 s (8.0 s), because that's when the UI starts building. The second line can run over the build and finish by about 11 s, before the fast section, which is music only.

- **Voice:** low, calm, measured, like an analyst's briefing. No hype.
- **Pacing:** about 2.7 words a second, with a short beat after the vessel name.

**Line A (5.0 to 8.0 s), about 9 words. Pick one:**
1. "Vessel Sabrina. Dark for three minutes. Our model saw it coming."
2. "Vessel Sabrina. Flagged six hours ago, likely to go dark."
3. "Vessel Sabrina, flagged by our prediction model. Rendezvous at sea. Then silence."

**Line B (8.0 to 11.0 s, over the build), optional. Pick one:**
1. "POSEIDON watches every ship, predicts where it went, and shows you why."
2. "POSEIDON predicts where dark vessels go, before they reappear."

Keep the claims honest. The go-dark model ranks ships and doesn't promise outcomes, so say "flagged" or "likely", not "will". Avoid "illegal" and avoid naming real ships or companies.

**ElevenLabs settings:** start with stability around 0.5 and similarity around 0.75, with style kept low. Generate 3 or 4 takes, and pick the one that lands "Sabrina" on 5.5 s.

---

## Build checklist

1. **Lock the music first.** Choose a 120 BPM track, or have it scored, and mark beats at 4.0, 8.0, 11.0 and 16.0 s.
2. **Generate shots 1 to 4 in Higgsfield** using the prompts above. Use the same seed or style reference across all of them so that the ocean and hulls match.
3. **Record the real UI for shots 5 and 6** on https://192-248-153-178.sslip.io in the dark theme, at 1920×1080 with 60 fps capture. Hide the browser chrome. Use smooth, deliberate mouse moves.
4. **Record the voiceover** in ElevenLabs and place it at 5.0 s.
5. **Add text in the edit:** `LAST HEARD` timer, the Sabrina tag and the prediction label.
6. **Cut shot 6 on the grid**, with each clip shorter than the last, and land the black frame exactly on 16.0 s.
7. **Add the logo** from `frontend/public/Logo/`, then fade picture and music to black by 20.0 s.
8. **Export:** 1080p H.264, and a 9:16 version if needed for socials.

## Notes

- The Higgsfield shots are stylised. Shots 5 and 6 should be the real product, so the video doesn't promise features we don't have.
- If the live site shows "ILLUSTRATIVE DATA" in the live chip during recording, either crop it out or keep it. Don't present illustrative data as real detections.
