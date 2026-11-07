# Agent 1: design system and theming

Read `CONTEXT.md` first. Worktree `G:/GitHub/dvm-fe/tokens`, branch `40-tokens`, dev port **5174**. You own `frontend/src/tokens/`, `frontend/src/theme/`, `frontend/src/ui/`, plus `frontend/index.html` (fonts) and `frontend/src/index.css`.

## Design source

- Figma page `39:448` "Agent 1 · Colour & themes". Specimens: Light `39:449`, Dark `39:567`, Dark CVD `39:684`, Dark HC CVD Large `39:801`, Light HC `39:918`. Rationale `40:5`, structure `40:8`, final encodings `40:11`, contrast checks `40:14`.
- The variable values are all in `design/R1-AGENT1-COLOUR.md` (DVM Theme × 4 modes, DVM Signals × 2 sets per theme, DVM Text size × 3). Use `get_variable_defs` on `39:449` to cross-check, but the report is the faster source.
- Type: Barlow Semi Condensed, IBM Plex Mono, Libre Caslon Text (`design/CONTEXT-R2.md`, page `14:2` frame `14:131`).

## Build

1. **`src/tokens/tokens.css`**: every DVM variable as a CSS custom property on `:root`/`html`, per mode via attributes `data-theme`, `data-signals`, `data-text` (names in CONTEXT.md). Signals alias into the theme exactly as Figma does (`--dvm-ship-dark` resolves differently per theme and per signal set). Include `--dvm-ship-ghost-fill` / `-edge` (dark colour at 14 % / 75 %), `--dvm-focus-dim-opacity`, `--dvm-accent-subtle`, `--dvm-focus-veil`, coverage colours with their alphas (use `color-mix` or rgb with alpha; no preprocessor). Add the roles the design agents flagged missing, as aliases: `--dvm-ship-keyline` (= bg/app), `--dvm-opacity-routine: 0.8`, `--dvm-opacity-trace: 0.2`, `--dvm-shadow-lift` (a subtle shadow colour per theme), `--dvm-replay-edge` (= text/primary).
2. **`src/tokens/tokens.json`** (or `.ts`): the same values as data, generated from one script `scripts/tokens/build.mjs` that writes both the CSS and the JSON from a single source file. One source of truth; `npm run tokens` regenerates.
3. **`src/theme/theme.ts`**: a store (use `createStore` from `src/store/store.ts`) with `theme`, `signals`, `text`, `reducedMotion`; persists to `localStorage`; applies the attributes to `<html>`; follows `prefers-color-scheme` and `prefers-reduced-motion` until the user chooses. **`src/theme/tokens.ts`**: `readToken(name): string` (resolved colour via `getComputedStyle`) and `onTokensChange(cb)` so the map can repaint. Export `useTheme()`.
4. **Theme crossfade**: switching theme must not flash. Implement a crossfade (e.g. snapshot the old `<html>` as an overlay that fades out over 300 ms with `opacity` only, or View Transitions where available with a reduced-motion fallback). Must stay 60 fps with the map underneath.
5. **Fonts** in `index.html`: Google Fonts link with `preconnect` and `display=swap` for the three families (weights the design uses: Barlow Semi Condensed 400/500/600, IBM Plex Mono 400/500, Libre Caslon Text 400 italic+regular). Set the global typography scale from `--dvm-size-*`/`--dvm-line-*`.
6. **Base components in `src/ui/`** (small, dependency-free, styled with tokens only, keyboard accessible, `forwardRef`): `Button` (filled / outline / ghost), `IconButton`, `Chip` (the inverted-ink REPLAY chip style, the neutral tag style, the signal-bordered tag), `Panel` (bg/panel, 1 px border/default, 4 px radius), `Lamp` (the square indicator lamp with text state used in the layers panel: on/off/n-a), `Switch` row, `Tooltip` (CSS-positioned, `aria-describedby`), `Kbd`. Look at the specimens for the exact look (status line, popup, legend, login screen).
7. **`ThemeMenu`** (`src/theme/ThemeMenu.tsx`): a small drop-in (top-right, next to where the layers button will be) with the three switches: theme (4), signals (2), text size (3). Design it in the same idiom as the layers panel (lamps, not phone toggles).
8. **Login screen** restyled from the specimen (the gate in `App.tsx`): you may edit the `.gate` markup in `App.tsx` for this (title in Barlow, button), that is your one App.tsx edit besides mounting `ThemeMenu`.
9. **Demo page** for review: `src/tokens/TokensDemo.tsx` rendered at `?demo=tokens` (one line in App.tsx) that shows swatches of every token in the current modes and the base components. The lead will screenshot it against the Figma specimens.

## Acceptance

- All 24 mode combinations render; contrast matches the report's claims (spot check 5 pairs with a script and put the numbers in the report).
- Switching any mode is a smooth crossfade, no flash, no layout shift; `prefers-reduced-motion` disables it.
- `npm run build` and `npm run lint` pass; tokens CSS gzipped size in the report.
- Report: `briefs/reports/tokens.md`.
