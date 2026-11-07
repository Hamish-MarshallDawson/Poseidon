import type { SizeTier } from '../geo'

// Runtime sprite atlas built on a canvas from the Figma SVGs in ../sprites (Ship hull 33:108, Ship overlay 33:127).
// Two coverage channels instead of colours, so one atlas serves every theme and signal set:
//   R = the mark itself (fill, or the outline for hollow states), G = the mark grown by the keyline width.
// The shader paints R in the state colour and the rest of G in --dvm-ship-keyline (bg/app), i.e. the keyline is
// baked under the fill exactly as the stacking report asks; a theme change only swaps two uniforms.

const svgs = import.meta.glob('../sprites/*.svg', { query: '?raw', import: 'default', eager: true }) as Record<string, string>

export const TYPES = ['tanker', 'cargo', 'fishing', 'passenger', 'other'] as const
export type HullType = (typeof TYPES)[number]
export const TIERS: SizeTier[] = ['far', 'mid', 'near']
const KEYLINE: Record<SizeTier, number> = { far: 1, mid: 1.5, near: 2 }       // R2 stacking report
const HOLLOW: Record<SizeTier, number> = { far: 1.25, mid: 1.25, near: 1.5 }  // outline width of No AIS hulls
const SCALE = 2   // atlas at @2x; sprites are drawn at CSS size, so they stay sharp on 1× and 2× screens
const PAD = 4     // CSS px around each sprite for the keyline
export const LETTER_PX = 14

export interface Sprite { u0: number; v0: number; u1: number; v1: number; w: number; h: number }  // w/h in CSS px incl. pad
export interface Atlas { width: number; height: number; pixels: Uint8Array; sprites: Map<string, Sprite> }

interface Svg { w: number; h: number; paths: Path2D[]; stroke: number }
function parse(text: string): Svg {
  const num = (k: string) => Number(new RegExp(`<svg[^>]*\\b${k}="([\\d.]+)"`).exec(text)![1])
  const ds = [...new Set([...text.matchAll(/\sd="([^"]+)"/g)].map((m) => m[1]))]
  const isStroke = /stroke-width="([\d.]+)"/.exec(text)
  // overlay-selected is drawn as a stroke; the sanctioned badge's stroke is only its keyline mask, so it fills.
  const stroke = isStroke && !/fill-rule/.test(text) ? Number(isStroke[1]) : 0
  return { w: num('width'), h: num('height'), paths: ds.map((d) => new Path2D(d)), stroke }
}
const SVG = new Map(Object.entries(svgs).map(([path, text]) => [path.replace(/^.*\/(.*)\.svg$/, '$1'), parse(text)]))

export function hullKey(type: HullType, tier: SizeTier, hollow: boolean, heading: boolean): string {
  return `hull:${type}:${tier}:${hollow ? 'o' : 's'}:${heading ? 'h' : 'n'}`
}
function hullSvg(type: HullType, tier: SizeTier, heading: boolean): Svg {
  return SVG.get(heading ? `ship-${type}-${tier}` : tier === 'far' ? 'ship-far-noheading' : `ship-${type}-${tier}-noheading`)!
}

type Draw = (g: CanvasRenderingContext2D, grow: number) => void   // grow = extra stroke width for the G channel
interface Job { key: string; w: number; h: number; draw: Draw }

function svgJob(key: string, svg: Svg, tier: SizeTier, hollow: boolean): Job {
  return {
    key, w: svg.w, h: svg.h,
    draw(g, grow) {
      for (const p of svg.paths) {
        if (svg.stroke) { g.lineWidth = svg.stroke + grow; g.stroke(p); continue }
        if (hollow) { g.lineWidth = HOLLOW[tier] + grow; g.stroke(p); continue }
        g.fill(p, 'evenodd')
        if (grow) { g.lineWidth = grow; g.stroke(p) }
      }
    },
  }
}

function letterJob(letter: string): Job {
  return {
    key: `letter:${letter}`, w: LETTER_PX, h: LETTER_PX,
    draw(g, grow) {
      if (grow) { g.fillRect(0, 0, LETTER_PX, LETTER_PX); return }      // badge background (keyline colour)
      g.lineWidth = 1; g.strokeRect(0.5, 0.5, LETTER_PX - 1, LETTER_PX - 1)
      g.font = `600 11px "Barlow Semi Condensed", "Arial Narrow", sans-serif`
      g.textAlign = 'center'; g.textBaseline = 'middle'
      g.fillText(letter, LETTER_PX / 2, LETTER_PX / 2 + 0.5)
    },
  }
}

export function buildAtlas(letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'): Atlas {
  const jobs: Job[] = []
  for (const tier of TIERS) {
    for (const type of TYPES) for (const heading of [true, false]) for (const hollow of [false, true]) {
      jobs.push(svgJob(hullKey(type, tier, hollow, heading), hullSvg(type, tier, heading), tier, hollow))
    }
    jobs.push(svgJob(`ovl:selected:${tier}`, SVG.get(`overlay-selected-${tier}`)!, tier, false))
    jobs.push(svgJob(`ovl:sanctioned:${tier}`, SVG.get(`overlay-sanctioned-${tier}`)!, tier, false))
  }
  for (const l of letters) jobs.push(letterJob(l))

  // Shelf packing into a 1024 px wide atlas.
  const W = 1024
  let x = 0, y = 0, rowH = 0
  const placed = jobs.map((j) => {
    const pw = Math.ceil((j.w + 2 * PAD) * SCALE), ph = Math.ceil((j.h + 2 * PAD) * SCALE)
    if (x + pw > W) { x = 0; y += rowH + 1; rowH = 0 }
    const at = { j, x, y, pw, ph }
    x += pw + 1; rowH = Math.max(rowH, ph)
    return at
  })
  const H = y + rowH
  const canvas = document.createElement('canvas')
  canvas.width = W; canvas.height = H
  const g = canvas.getContext('2d', { willReadFrequently: true })!
  const pixels = new Uint8Array(W * H * 4)
  const sprites = new Map<string, Sprite>()
  for (const channel of [0, 1]) {
    g.clearRect(0, 0, W, H)
    for (const { j, x, y, pw, ph } of placed) {
      g.save()
      g.translate(x, y); g.scale(SCALE, SCALE); g.translate(PAD, PAD)
      g.fillStyle = g.strokeStyle = '#fff'
      g.lineJoin = 'round'; g.lineCap = 'butt'
      const tier = (j.key.split(':')[2] as SizeTier) ?? 'far'
      j.draw(g, channel ? 2 * (KEYLINE[tier] ?? 1) : 0)
      g.restore()
      if (!channel) sprites.set(j.key, { u0: x / W, v0: y / H, u1: (x + pw) / W, v1: (y + ph) / H, w: pw / SCALE, h: ph / SCALE })
    }
    const data = g.getImageData(0, 0, W, H).data
    for (let i = 0; i < W * H; i++) pixels[i * 4 + channel] = data[i * 4 + 3]
  }
  for (let i = 0; i < W * H; i++) pixels[i * 4 + 3] = 255
  return { width: W, height: H, pixels, sprites }
}
