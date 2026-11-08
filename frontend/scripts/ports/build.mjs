// Rebuild public/ports/ports.json. Run: node scripts/ports/build.mjs
// Source: UN/LOCODE code list (UNECE; free to use with attribution, "Source: UN/LOCODE, UNECE"), via the
// datasets/un-locode mirror. Used because the NGA World Port Index (public domain, msi.nga.mil) answered 503 when this
// was built; if NGA is back, swap the parser here and keep the same row shape.
// Kept: entries with function digit 1 (port) plus rail, road, airport or post (2-5) (drops ~5,000 tiny fishing/river
// landings to stay under 300 KB), with coordinates, status not removed, unverified or pending (XX, QQ, RN, UR, AQ). Row shape:
// [name, iso2, locode ("SEGOT" or ""), lat, lon]. Drops exact duplicate locodes.
import { writeFileSync } from 'node:fs'

const SRC = 'https://raw.githubusercontent.com/datasets/un-locode/main/data/code-list.csv'
const text = await (await fetch(SRC)).text()

function* rows(s) {                       // minimal CSV reader (quotes, embedded commas)
  let row = [], f = '', q = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (q) { if (c === '"') { if (s[i + 1] === '"') { f += '"'; i++ } else q = false } else f += c }
    else if (c === '"') q = true
    else if (c === ',') { row.push(f); f = '' }
    else if (c === '\n') { row.push(f.replace(/\r$/, '')); f = ''; yield row; row = [] }
    else f += c
  }
}
const deg = (s, neg) => {                 // "5733N" / "01155E" -> degrees, 2 decimals (~1 km)
  const m = /^(\d+)(\d\d)([NSEW])$/.exec(s)
  if (!m) return null
  const v = +m[1] + +m[2] / 60
  return +((m[3] === neg ? -v : v).toFixed(2))
}
// UN/LOCODE has no coordinates for these major ports; approximate harbour positions added by hand.
const PATCH = { PLGDN: '5424N 01840E' }
const out = [], seen = new Set()
for (const r of rows(text)) {
  const [, cc, loc, name, , , status, fn, , , coord] = r
  if (!loc || fn?.[0] !== '1' || !/[2-5]/.test(fn.slice(1)) || ['XX', 'QQ', 'RN', 'UR', 'AQ'].includes(status)) continue
  const [la, lo] = (coord || PATCH[cc + loc] || '').split(' ')
  const lat = deg(la, 'S'), lon = deg(lo, 'W')
  if (lat === null || lon === null || seen.has(cc + loc)) continue
  seen.add(cc + loc)
  out.push([name, cc, cc + loc, lat, lon])
}
writeFileSync(new URL('../../public/ports/ports.json', import.meta.url), JSON.stringify(out))
console.log(out.length, 'ports')
