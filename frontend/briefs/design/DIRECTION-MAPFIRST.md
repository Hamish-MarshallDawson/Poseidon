# Round 2b: map-first (Hamish's new direction; overrides the dashboard-sidebar layout)

**The whole screen is the map. You interact through the map, not a dashboard sidebar.**

- The **scrub bar** stays visible most of the time.
- Everything else **drops in and out depending on what you click**. There is **no fixed right-hand dashboard**.
- Clicking a ship opens a **floating ship window** that you can drag anywhere. Several can be open at once, for comparing ships.
- The **forecast lives on the map** (probability tags on ships, ghost circles). The **watchlist** is a drop-in panel you summon; it is not always on.
- The **legend** is a small toggleable overlay that drops in.
- **Coastlines must be real**: detailed land-to-ocean coastlines from real geometry, with no low-poly or hexagonal shapes. Land borders between countries stay as the dotted line. The coastline agent publishes real basemap components; every map frame moves to them.

Unchanged: only the shared DVM variables (no new variables), Light and Dark versions, your own page only, the neutral wording ("No AIS received; reception normal nearby"), and no frontend code.

The round-2 agents' reports, for context on what exists: `R2-AGENT1-STACKING.md`, `R2-AGENT2-TIMELINE.md`, `R2-AGENT3-FORECAST.md`, `R2-AGENT4-LEGEND.md`. The dashboard's report is in its own folder.
