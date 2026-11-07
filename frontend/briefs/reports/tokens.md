# Tokens agent report (#40, design system and theming)

PR: https://github.com/Hamish-MarshallDawson/Hedged-Bets-hacktheburgh/pull/47 (branch `40-tokens`, 3 commits on main `aa1a22b`). Not merged.

## What I built

| File | What |
|---|---|
| `frontend/scripts/tokens/source.json` | The one source: DVM Theme (25 roles + dim-opacity, 4 modes), DVM Signals (9 base + 2 derived ghost colours, std/cvd per theme), DVM Text size (7 roles × 3), extra roles, constants. Copied from `design/R1-AGENT1-COLOUR.md`, cross-checked with `get_variable_defs` on `39:567` (all Dark values match). |
| `frontend/scripts/tokens/build.mjs` | `npm run tokens` writes `src/tokens/tokens.css` and `src/tokens/tokens.json`. `--check` fails if they're stale. Validates every mode column. |
| `frontend/scripts/tokens/check.mjs` | Renders `?demo=tokens` in all 24 combinations, reads resolved tokens, checks contrast, times a theme switch. |
| `frontend/src/tokens/tokens.css` | Generated. `:root` = light/standard/default. Theme blocks per `[data-theme]`; hidden `--dvm-signal-std-*` / `--dvm-signal-cvd-*` per theme; `--dvm-ship-*` / `--dvm-risk-*` alias them per `[data-signals]` (as Figma does). Alpha colours are `#rrggbbaa`. |
| `frontend/src/tokens/tokens.json` | Same values as data (per mode), for code. |
| `frontend/src/theme/theme.ts` | `themeStore` (createStore), `useTheme()`, `setTheme(patch)`, `resetTheme()`, `THEMES` / `SIGNAL_SETS` / `TEXT_SIZES`. Follows `prefers-color-scheme`, `prefers-contrast: more` (→ HC) and `prefers-reduced-motion` until the user picks; persists picks (validated) in localStorage `dvm-theme`. Sets `data-theme`, `data-signals`, `data-text`, `data-motion` on `<html>`. Crossfade via View Transitions. |
| `frontend/src/theme/tokens.ts` | `readToken('ship-dark' \| 'ship/dark' \| '--dvm-ship-dark')` → resolved hex; `onTokensChange(cb)` (MutationObserver on the three attributes) → unsubscribe. |
| `frontend/src/theme/ThemeMenu.tsx`, `theme.css` | "Display" drop-in, fixed top-right (16 px). Lamp toggle like the legend toggle; inside: lamp radio rows for Theme (4), Signal colours (2), Text size (3) (native radios, so arrow keys work), a Reduce motion switch, "Follow system settings". Esc closes and returns focus; click outside closes; `role="dialog"`, `aria-expanded`/`aria-controls`. |
| `frontend/src/ui/index.tsx`, `ui.css` | `Button` (filled/outline/ghost, `aria-pressed` look), `IconButton` (required `label`), `Chip` (`tag`, inverted-ink `replay`, `signal` with `signal="risk-3"`), `Panel`, `Lamp` (on/off/na with text), `Switch` (layers-panel row, `role="switch"`, `unavailable` = n/a), `Tooltip` (CSS, `aria-describedby`), `Kbd`, plus `.dvm-section-label`. All forwardRef, tokens only. |
| `frontend/index.html` | Google Fonts (Barlow Semi Condensed 400/500/600, IBM Plex Mono 400/500, Libre Caslon Text 400 + italic) with preconnect, `display=swap`; a 6-line pre-paint script that sets the modes from localStorage/media so dark users don't see a light flash. |
| `frontend/src/index.css` | Imports tokens; body font/size/colour from tokens; `:focus-visible` ring; type classes `.t-caption … .t-display`, `.t-data` (mono), `.t-place`, `.t-water` (Caslon italic), `.t-muted`, `.t-secondary`, `.dvm-sr`; view-transition timing; `[data-motion=reduce]` kills all animation/transition. Existing `.status`, `.gate`, `.dot`, `.ship-popup` retokenised; MapLibre popup on panel colours (otherwise dark-theme text would sit on the white default popup). |
| `frontend/src/tokens/TokensDemo.tsx`, `demo.css` | `?demo=tokens` (no login needed): modes line, a map specimen (water, land, coast, border, grid, coverage, labels, every ship state, risk ramp), every token as a swatch with its resolved value, the type scale, all components. Lazy chunk (4.0 KB gz). |

## How to run and verify

```
cd frontend
npm run tokens                         # regenerate CSS + JSON after editing scripts/tokens/source.json
npm run dev -- --port 5174 --strictPort
open http://localhost:5174/?demo=tokens   # Display menu top right
node scripts/tokens/check.mjs          # 24 combinations + contrast + switch timing (headless Edge)
```

## Measurements

- **tokens.css: 10,053 B raw, 2,271 B gzipped.** ui.css 1,519 B gz, theme.css 526 B gz. Production CSS bundle 14.6 KB gz in total (13 KB of that is maplibre-gl.css). No new dependencies.
- **24 combinations:** `check.mjs` sets each combination and reads the tokens: all resolve, no page errors, `ALL 24 COMBINATIONS OK`.
- **Contrast spot checks (WCAG, from the browser-resolved values):**

| pair | light/std | light/cvd | dark/std | dark/cvd | light-hc/std | light-hc/cvd | dark-hc/std | dark-hc/cvd |
|---|---|---|---|---|---|---|---|---|
| text-muted on bg-raised (≥4.5) | 6.03 | 6.03 | 4.94 | 4.94 | 11.72 | 11.72 | 9.88 | 9.88 |
| text-primary on bg-panel (≥4.5) | 14.68 | 14.68 | 11.69 | 11.69 | 21.00 | 21.00 | 17.33 | 17.33 |
| text-on-accent on accent-default (≥4.5) | 6.93 | 6.93 | 9.14 | 9.14 | 10.29 | 10.29 | 14.05 | 14.05 |
| map-label-water on map-water (≥4.5) | 6.33 | 6.33 | 6.56 | 6.56 | 11.35 | 11.35 | 11.26 | 11.26 |
| ship-dark on map-water-alt (≥3) | 4.29 | 8.63 | 3.45 | 3.23 | 6.81 | 9.56 | 5.37 | 5.57 |
| ship-sanctioned on map-water-alt (≥3) | 3.86 | 3.06 | 3.73 | 3.42 | 6.17 | 3.41 | 5.46 | 3.96 |

  These match the design report's claims: lowest text 4.94 (Dark text/muted on bg/raised), lowest non-text 3.06, and the fixed Dark CVD sanctioned on water-alt is 3.42.
- **Theme switch over the live map** (headed Edge, logged in on :5174, 26,542 ships, current App.tsx GeoJSON layer), rAF over 800 ms around each switch: light 57.6 fps, dark 58.8, light-hc 58.8, dark-hc 58.8, dark 60.0. At most 2 frames over 20 ms per switch, worst 33 ms (the snapshot frame at the start of the transition).
- Keyboard: arrow keys move through each radio group (checked: ArrowDown on Light → Dark applied); Esc closes the menu and returns focus to "Display".
- `npm run build` and `npm run lint` pass (0 warnings).

## Design deviations and why

- **Login copy:** the specimen says "Ships that hide from tracking…". The brief bans "hiding", so it says "Ships that go quiet on AIS while reception nearby is normal, ranked for review. Never an accusation."
- **Login button label** stays "Log in to view the map" (the specimen says "Sign in with Auth0") because `scripts/smoke.mjs` clicks it by that name. The lead can rename both together.
- **Crossfade** uses View Transitions (Chrome/Edge, Safari 18+, Firefox 144+); browsers without it switch instantly (marked `shortcut:` in theme.ts). No overlay fallback was built.
- **Extra roles not in Figma** (values are mine): `--dvm-shadow-lift` = light `#1d2529` @ 18 %, dark black @ 45 %, light-hc black @ 25 %, dark-hc black @ 60 %; `--dvm-radius-panel` 4px; `--dvm-duration-theme` 300ms; `--dvm-font-ui|data|place`. `Panel` uses a small `0 2px 6px` shadow-lift.
- **`prefers-contrast: more`** picks the HC variant until the user chooses (small addition beyond the brief).
- Signals and aliases resolve on any element with `data-theme` or `data-signals`, so a nested scope must set both attributes; a nested `data-theme` alone falls back to standard signals.

## For other agents

- MapLibre paint: `readToken('ship-dark')` returns `#rrggbb` or `#rrggbbaa`; repaint in `onTokensChange(() => …)`. The callback runs inside the crossfade, so the repaint fades in with the rest.
- Respect motion with `themeStore.get().reducedMotion` in JS, or nothing in CSS (`[data-motion=reduce]` already zeroes CSS animation and transition durations).
- The map currently uses the OpenFreeMap dark style and `#22d3ee` dots, so it doesn't follow the theme yet (map and coastline agents).

## Not done

- No overlay crossfade fallback for browsers without View Transitions.
- Tooltip can't be dismissed with Esc while hovered (WCAG 1.4.13); fine for short labels.
- No pixel comparison against every Figma specimen: I compared the Dark specimen (`39:567`) and the layers panel (`41:432`) by eye.
- Board: I kept `board wait` running and read the posts. None affect tokens; I didn't post.
