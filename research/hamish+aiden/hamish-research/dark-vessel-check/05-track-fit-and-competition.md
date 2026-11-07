# 05. Track fit, judge-facing claims, competitors

Checked Sat 7 Nov 2026. Sources: web pages fetched or searched; a few sites returned 403/404 and are marked.

## 1. Verdict: AMBER

The idea is a strong G-Research fit and a good-but-riskier HRT fit. The facts we would say to judges mostly hold, with two small corrections (the "half of exports" figure is a Jan 2025 number; VIIRS latency is ~6 h, not ~4 h). The competition is the real issue: "isn't this just Windward?" is a fair question, and the answer must be "no, because we show a scored, backtested forecast and we built it in 17 hours on free data". The idea works if the forecast is backtested honestly and the demo has one visual moment. It does not win on novelty of the problem, which is crowded commercially but, from what I could find, not at hackathons.

## 2. Claims table

| # | Claim | Status | Evidence | Note |
|---|---|---|---|---|
| 3.1 | ~half of shadow-fleet oil exports pass the Baltic | partly | https://cepa.org/article/choking-russias-shadow-fleet-in-the-baltic/ | CEPA says "around 50% of shadow fleet oil exports pass through it", but the article is dated 15 Jan 2025, not 2026. Say "CEPA estimated in 2025". |
| 3.2 | Apr 2026: 30 to 40 tankers idling near Russian waters and the strip between Finland and Estonia | confirmed | https://www.themoscowtimes.com/2026/04/14/idling-shadow-fleet-tankers-threaten-baltic-security-and-environment-experts-warn-a92498 | "Between 30 and 40 shadow fleet tankers" at unofficial anchorages in Russian waters and the 6 nm international strip. Moscow Times is the source, so attribute it. |
| 3.3 | EU list passed 670 in 21st package, 23 Jul 2026 | confirmed (673) | https://www.consilium.europa.eu/en/press/press-releases/2026/07/23/21st-package-of-sanctions-eu-hits-russian-energy-financial-services-and-crypto-hard/ | Direct fetch got 403; a search snippet of the Council release says 41 added "on top of the 632 already", so 673. gCaptain, Lloyd's List Intelligence and Steptoe also say 673. Reed Smith says 692 (unsupported). EEAS page says "more than 636", inconsistent. Say "about 670" or "673". I did not see the Official Journal itself. |
| 3.4 | Finland Coast Guard: constant GNSS interference, tankers spoofing positions | partly | https://marinelink.com/news/finland-coast-guard-detects-satnav-518723 (via search; page fetch failed) | Article is 31 Oct 2024: disruption since April 2024, spoofing seen "around ten times" by tankers visiting St Petersburg-area ports. "Constant" is not in what I saw. Later coverage (May 2025 phantom ships; Jan 2026 14-state letter) supports the trend. Say "since 2024". |
| 3.5 | LPG tanker to Ust-Luga drew circular AIS patterns ~10 days | confirmed | https://www.hellenicshippingnews.com/?p=1110298 | 8 to 17 Oct 2025, "irregular AIS circular patterns", Gulf of Finland. Photo caption says 11 days. Say "about 10 days". |
| 3.6 | Jan 2026 Venezuelan-oil tankers tried to leave with AIS off | confirmed | https://www.opensanctions.org/entities/NK-bcokCDJNYi7ztnQjV7Az3W | Page (vessel MEROPE) says "attempted to leave Venezuelan waters in dark mode (with AIS transponders turned off)", PDVSA oil, early Jan 2026. Three returned after a US detention on 9 Jan. |
| 4.1 | 2024 Nature/GFW: ~75% of industrial fishing vessels untracked; 7 in 10 in Asia | confirmed | https://globalfishingwatch.org/?p=39532 | "about 75 percent ... not publicly tracked"; "for every 10 vessels ... seven were in Asia". |
| 4.4 | VIIRS boat detection nightly CSV, ~4 h latency | partly | https://eogdata.mines.edu/products/vbd/ | Nightly CSV/KMZ yes. Latency stated as ~6 hours after overpass, not 4. |
| 5.1 | Hormuz ~20 mb/d, ~1/5 of consumption, >1/4 seaborne oil trade | confirmed | https://eia.gov/todayinenergy/detail.php?embed=true&id=65504 | 2024 and Q1 2025, exact. |
| 5.2 | Conflict from 28 Feb 2026; transits down 97% in March | partly | https://windward.ai/knowledge-base/q1-2026-maritime-risk-report/ | 97% drop is stated. The 28 Feb date is not on that page. Source the date elsewhere or drop it. |
| 5.4 | Aug 2026: 61.2% of logged Hormuz transits false | confirmed | https://windward.ai/knowledge-base/gps-jamming-and-false-transits-in-the-strait-of-hormuz/ | "Of 642 vessel transits logged ... 393, 61.2%, never actually happened", caused by GPS jamming corrupting AIS. Windward's own number; attribute it. |
| 6.1 | Palantir Gotham/Foundry one data model, Apollo, AIP | partly | https://www.sec.gov/Archives/edgar/data/1321655/000132165525000022/pltr-20241231.htm | 10-K names Gotham, Foundry, Apollo, AIP as the four platforms; AIP adds LLMs inside Gotham and Foundry. "One data model" not confirmed in filings; the B.D. Emerson page was not opened. |
| 6.2 | Palantir Gotham demo flags a warship going dark | unverifiable | none | Searches found no such demo. Do not say it on stage. |
| 6.3 | Saildrone and Palantir partnership, Mar 2025 | confirmed | https://www.navalnews.com/naval-news/2025/03/saildrone-and-palantir-announce-strategic-partnership-to-advance-ai-powered-maritime-intelligence/ | Dated 13 Mar 2025; fuses Saildrone sea-surface data with other sources for maritime intelligence. |
| 6.4 | Windward customers include BP, Shell, HSBC | confirmed | https://www.cityam.com/?p=1811280 | Used for charter compliance. |
| 6.5 | Skylight free, 300+ orgs, ~70 countries, SAR + night-light dark vessel detection | partly | https://www.geekwire.com/2026/ai2s-skylight-project-launches-shippy-an-ai-agent-that-dives-into-ocean-data/ (direct fetch 403; via search) | Free for governments, regional bodies, qualifying NGOs (not everyone). 300 and 70 repeated in recent coverage; Skylight's own news page still says 200+. Dark detection uses Sentinel-1 SAR and Sentinel-2 optical; night lights not confirmed. New AI agent "Shippy". |
| 6.6 | Kayrros sells off-the-radar detection to traders; Kpler/Vortexa sell flows | partly | https://www.kayrros.com/products/off-the-radar-detection-for-traders/ (page fetch 404; via search) | Kayrros: satellite plus AIS count of vessels with AIS off, dashboard/CSV, fortnightly report. Kpler/Vortexa tanker-flow data: not checked this round, widely known. |
| 6.7 | Missed competitors | see section 4 | | |

## 3. Track fit

### G-Research, "Make the Invisible Visible" (hidden patterns, looks cool or is cool, creative and well-structured)

Score: **8/10.**
- Rewarded: the headline is literally the brief. Ships that turn invisible are the demo. Thin-line black map with red rings is "looks cool". Probability that a ship will vanish is a hidden signal found in data. The firm's roots in finding signals matches a ranked forecast with baselines.
- Marked down: if the map is just dots and a table. If "invisible" is only an AIS gap that is really receiver coverage (false positives). If code is a mess, since they said "well-structured".
- G-Research have a quant-signal culture: they will ask about false positives and what the model learns. Show the baseline comparison.

### HRT, "Best Use of Data for Predictions and Decision Making" (decisions fast from data)

Score: **6.5/10.**
- Rewarded: streaming data, a real forecast, backtest versus baselines, an automated inspect-next ranking, latency of decision.
- Marked down: HRT are trading people. They will test the statistics: sample size, leakage, base rates. A handful of sanctioned ships makes a weak label set. "Forecast who goes dark in 6 h" with few real events can look like a toy. Decision value is not quantified (what is a wrong inspection worth?).
- The "decision" part must be concrete: show precision at top 10, time to alert, and compare to "last-seen-gap" or "sanctions-list-only" baselines.

### Both tracks

Entering both with one project is credible and allowed (organisers: a project may enter several sponsor tracks). The pitch is naturally two-part: "see it" (G-Research) then "act on it" (HRT). **G-Research is the stronger primary**, because the visual payoff is guaranteed while HRT scoring depends on stats that a 17-hour build can undersell. Pitch HRT as the second beat, with one slide of backtest numbers.

## 4. Competitors and "isn't this just X?"

| Competitor | What they do | Verified / source | Judge would say |
|---|---|---|---|
| Windward | Maritime AI. Dark activity, AIS manipulation, GNSS manipulation, risk scoring, shadow fleet, customers BP/Shell/HSBC; claims predictive flags on "99% of sanctioned vessels before designation" (own marketing, unverified); MAI Expert Gen-AI agent | https://windward.ai/solutions/risk-and-compliance/ , City AM | "Just Windward's risk score." |
| Skylight (Ai2) | Free to governments/NGOs; AIS plus SAR/optical dark-vessel detection; Shippy agent | GeekWire | "Just Skylight, and it's free." |
| Kpler, Vortexa | Tanker flow data and (Kpler) deceptive-practice analytics | Kpler blog Nov 2025 | "Just their feed." |
| Kayrros | Satellite plus AIS count of AIS-off tankers for oil traders | Kayrros site (via search) | "Just Kayrros, a bit prettier." |
| Spire, MarineTraffic, exactEarth (now Spire), Pole Star, Lloyd's List Intelligence, HawkEye 360, Unseenlabs | AIS data (Spire, MarineTraffic), screening/risk (Pole Star, LLI), RF detection (HawkEye 360, Unseenlabs), SAR/RF dark detection. Pole Star and SynMax (Theia) market dark-vessel detection | Pole Star https://www.polestarglobal.com/use-cases/dark-vessel-detection ; SynMax https://synmax.com/maritime/dark-vessel-detection/ | These are data vendors; judges rarely name them. Only some were checked via search snippets, not product pages. |
| Palantir | Gotham/Foundry/AIP platforms; Saildrone tie-up | SEC 10-K, Naval News | "Palantir already does this." Their going-dark demo is unverified, so do not claim it. |
| Open source | FormerLab/shadow-fleet-tracker-light (MIT, 44 stars, last push 29 Apr 2026): Baltic AIS, 1200+ vessels from the Ukrainian GUR list, blackout reports, cable proximity alerts. gma2th/aisdk (MIT, 6 stars, last push 2020): DMA AIS analysis. SeaSpoofFinder paper (arXiv 2602.16257): GNSS spoofing from AIS, includes Baltic. Global Fishing Watch research (SAR dark fleets) | gh repo view; search results | Closest "just X": the FormerLab tracker. It detects gaps on a known list; it has no forecast and no ranking by predicted risk. |

### Sharpened answer to "isn't this just Windward?"

Suggested 20 seconds:
"Windward is a paid platform that scores ships on past behaviour for compliance teams. We did something different in a weekend on free data: a 6-hour forecast of which ships will go dark next, ranked into an inspect-next list, with the backtest shown against simple baselines and every claim reproducible. We are not claiming better data than Windward. We are showing the method and its measured accuracy, and we are open about what a free feed cannot see."

Honesty points: do not claim novelty of dark-vessel detection (commercial and free tools exist). Claim: forecast-first, open, backtested, receiver-coverage-aware. Do not repeat Windward's 99% figure as fact.

## 5. Is it overdone at hackathons?

Evidence is thin; web search does not index Devpost well.
- Devpost "Shadow Stalker" (https://devpost.com/software/temp-p5ogjk) and "Fishy" (https://devpost.com/software/fishy) exist. Page fetches were blocked (403), so detail comes from search snippets only: Fishy is described as AIS gap scan plus probability clouds with Global Fishing Watch APIs; Shadow Stalker looks drone/vision-based. Year, hackathon and prizes unverified.
- "DarkFleet": GitHub project, 6th of 64 at the Claude Hackathon, Imperial College London (illegal fishing risk score, Claude briefs). A placing, not a win. Not Devpost.
- "Hormuz Watch" came from a Philly maritime defense hackathon, 27 to 29 Mar 2026.
- Defence-tech hackathons and DNV hackathon also produced maritime work.
- Conclusion: not saturated, but not unique. Expect 0 to 2 other maritime/AIS entries at a general UK student hackathon; I could not check the HackTheBurgh entry list. Guess: the bigger competition is polished generic AI-agent apps, which tend to win "Best Overall".

## 6. Ethics and privacy answer

AIS is a public safety broadcast, so tracking is lawful and not personal data in the usual sense (ships, not people), though masters and crews can be identifiable. The risk is naming a ship as a suspect on a thin signal: a gap can be receiver range, an outage or jamming.

Say:
1. "We rank for human review. We never accuse." Output wording: "unexplained AIS gap, risk score 0.7", not "sanctions-buster".
2. Dark is not illegal. Show the reason codes and the confidence next to every alert; suppress an alert when neighbouring ships also vanished (coverage or jamming).
3. Only name vessels already on public sanctions lists (EU, OpenSanctions); for all others show IMO/MMSI only, no owner or crew names, and use placeholder names in public material (already in pitch-plan).
4. Show false-positive rate and sample sizes in the backtest.
5. Data minimisation: public feeds only, no personal data, no crew tracking, no scraping behind logins.
6. Dual use: the same tool could help evaders learn what flags them; we publish method, not evasion advice.

## 7. Metaview "Best Overall"

Judged on creativity; any project eligible. Moment candidates:
- **Rewind and race:** replay the last hour and watch a real tanker's marker go out at the instant the system turned its ring red, then say "we predicted it 3 hours earlier" (needs a real hit).
- **Live "switch off" moment:** a judge picks a ship on the map and we show its predicted-dark probability climbing. Needs real data.
- Risk: Baltic events are rare in 24 hours; without a recorded case the map looks static. Mitigate with a prepared replay of a documented case (e.g. the Gulf of Finland circle spoof, which is visibly weird on a map: a ship drawing circles while "anchored").
Odds for "Best Overall": moderate. Judges there reward creativity and wow, and a good-looking map helps, but the topic is niche versus agent apps. A guess: 15 to 20% chance.

## 8. Key judgement

- G-Research: realistic chance, maybe 30 to 40% (guess), higher with a polished map and a visible "found something hidden" moment.
- HRT: maybe 15 to 25% (guess); stats-literate judges, and the label set is small.
- **Single change that most raises the odds:** produce one honest, recorded, pre-made proof: a held-out backtest card ("of our top 10 forecast ships, X went dark within 6 h versus Y for the baseline") plus one replayable real event where the forecast fired before the ship vanished. That one slide serves both tracks (invisible made visible; prediction scored against baselines) and answers "is this just Windward?" with evidence rather than claims.

## 9. Risks (ranked) for the remaining ~17 h

1. No convincing real dark event in the data to demo. Fix: pick one from DMA history by Saturday night and freeze it as the replay.
2. Backtest has too few positives; judges from HRT will notice. Fix: define "dark" broadly (gap over N hours with neighbours heard), report counts and confidence intervals, compare to baselines.
3. False positives from coverage. Fix: neighbour check, per-area message-rate check (already planned).
4. Naming ships. Fix: section 6.
5. Competitor question handled badly. Fix: section 4 answer; do not claim novelty of the problem.

## 10. Anything missed

- Open source: FormerLab/shadow-fleet-tracker-light (MIT) is the closest thing; licence permits reuse with attribution, but only code written in the hackathon counts for the rules, so reading it for ideas is fine and copying it into the repo needs attribution and a note in the write-up.
- SeaSpoofFinder (arXiv 2602.16257) is a useful method reference for spoofing detection.
- The 5 Aug 2026 AISStream outage is a team-claimed fact (1.5); not in my area.
- Unchecked: Kpler/Vortexa specifics, Spire/MarineTraffic/Pole Star/LLI/HawkEye/Unseenlabs product pages, 3.4 main page, 5.3, 5.5, 5.6, and the Devpost pages (403).
