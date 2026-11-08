// Run: node src/layout.check.mjs. The --lay-* custom properties in panels.css must equal the numbers in layout.ts.
import { readFileSync } from 'node:fs'
import { BOTTOM, CONTROLS_TOP, PANEL_TOP, TOP } from './layout.ts'

const css = readFileSync(new URL('./panels/panels.css', import.meta.url), 'utf8')
const v = (n) => Number(new RegExp(String.raw`--lay-${n}:\s*(\d+)px`).exec(css)?.[1])
const want = { top: TOP, bottom: BOTTOM, 'controls-top': CONTROLS_TOP, 'panel-top': PANEL_TOP }
for (const [k, n] of Object.entries(want)) if (v(k) !== n) throw new Error(`layout.check: --lay-${k} is ${v(k)}, layout.ts says ${n}`)
console.log('layout.check: ok')
