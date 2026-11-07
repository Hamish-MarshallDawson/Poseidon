# Integration: one engine, three lenses

How the three use cases (Baltic shadow fleet, Southeast Asia illegal fishing, oil-market flows) fit into one piece of software. Written with Claude on 7 Nov 2026; sources at the bottom, unverified until an agent checks them.

## The link

All three are **valuable cargo moving at sea while the ship hides from tracking**. The cargo differs (Russian oil, stolen fish, Iranian oil), but the behaviour, the tricks and some of the waters are the same.

1. **Same key behaviour: meeting another ship at sea.** Shadow tankers move oil ship-to-ship to launder its origin. Illegal fishing relies on carriers that take catch off fishing boats and bunker tankers that refuel them. Global Fishing Watch defines an encounter as two vessels within 500 m for at least 2 hours at under 2 knots, at least 10 km from an anchorage: almost exactly our rendezvous rule. GFW also flags "loitering" support ships with no visible partner, which may be meeting a dark vessel. GFW publishes encounters as free data, so we get **labels to validate our rendezvous detector**.
2. **Same identity tricks.** Shadow tankers use flags of convenience such as Gabon, Comoros and Cameroon, and illegal fishing fleets use the same weak registries. Example: 36 of the 38 sanctioned shadow tankers flying Equatorial Guinea's flag joined in 2026; the rest of that registry is mostly small domestic and fishing vessels. One identity-risk layer (flag hopping, MMSI changes, registry quality) scores tankers and trawlers alike.
3. **Same waters in Southeast Asia.** The Malaysian Eastern Outer Port Limits, a hub for ship-to-ship transfers of Iranian oil, is close to the Natuna Sea, where dark fishing is heavy. Indonesia caught a Cameroon-flagged shadow tanker in an illegal STS transfer in July 2023. One SE Asia map can show dark trawlers and dark tankers together.

## Product shape

**Shared core (built once):**

1. Ingest live AIS, plus satellite radar and night-light detections.
2. Reconcile: which ships are seen but not broadcasting.
3. Events: dark gap, spoofing, identity change, **meeting at sea**.
4. Per-ship risk score and forecast.

**Lenses (a cargo filter plus a different decision):**

| Lens | Cargo | Decision it outputs | Who uses it | Sponsor fit |
| --- | --- | --- | --- | --- |
| Sanctions (Baltic) | Russian oil | Which ships to inspect next | Coastguards, insurers | G-Research |
| Fisheries (Natuna) | Fish | Where to send the patrol tonight | Fisheries ministries | G-Research, moral weight |
| Markets (Hormuz, Malaysia) | Oil | Barrels that really moved: false transits removed, dark transits added | Traders | HRT |

**Pitch line:** "One question, three answers: what moved at sea that wasn't meant to be seen? For a coastguard it's who to board, for a fisheries ministry it's where to patrol, for a trader it's how many barrels really moved."

## Scoping for 24 hours

- Build the engine once, **live, on the Baltic**, with the forecast score.
- Run the other two lenses on **historical data**: GFW encounters and SAR detections for Natuna; Hormuz and Malaysia transfers for markets.
- In the interface it is a lens switcher across the three mockup boards.
- **Put the meeting-at-sea detector on the critical path**, because all three lenses depend on it. Validate it against GFW encounter events.

## Risk

Three lenses can read as three half-projects. Keep one lens fully working and give the other two about 40 seconds of the demo as "same engine, different data".

## Claims for agents to check

| # | Claim | Source |
| --- | --- | --- |
| I.1 | GFW encounter definition: within 500 m for 2+ h, under 2 knots, 10+ km from anchorage | [GFW](https://globalfishingwatch.org/?p=15947) |
| I.2 | GFW loitering events with no visible partner may indicate a dark vessel | [GFW report to WCPFC](https://meetings.wcpfc.int/file/10010/download) |
| I.3 | Transshipment relies on carriers and bunker tankers; GFW database of 1,350 carriers and 963 bunker vessels | [GFW](https://globalfishingwatch.org/?p=13025) |
| I.4 | Shadow tankers use flags of convenience such as Gabon, Comoros or Cameroon | [WSJ via To Vima](https://www.tovima.com/wsj/a-shadow-fleet-smuggles-illicit-oil-across-the-high-seas-this-is-how-it-works) |
| I.5 | 36 of 38 sanctioned shadow tankers flying Equatorial Guinea's flag joined in 2026; the rest are mostly small domestic or fishing vessels | [Hellenic Shipping News](https://www.hellenicshippingnews.com/russia-is-the-leading-flag-for-shadow-fleet-tankers/) |
| I.6 | Lansing Institute: the same weaknesses that enable Russian oil exports enable illegal fishing | [ADF Magazine](https://adf-magazine.com/?p=139277) |
| I.7 | Indonesia caught a Cameroon-flagged shadow tanker in an illegal STS operation in July 2023 | [Maritime Executive](https://maritime-executive.com/editorials/russia-s-shadow-tanker-fleet-runs-into-trouble) |
| I.8 | Does GFW's encounters dataset cover tanker-to-tanker meetings, or only fishing/carrier/bunker? If only fishing, Baltic STS labels must come from elsewhere | open question |
