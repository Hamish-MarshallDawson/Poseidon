import type { CustomLayerInterface, CustomRenderMethodInput, Map as MapLibreMap } from 'maplibre-gl'
import type { Atlas, Sprite } from './sprites'
import type { ShipState } from './state'
import { clock, EXTRAP_S, shownS } from './state'

// The ship hot path: one MapLibre custom layer drawing instanced quads from a typed array.
// Measured against a symbol layer before choosing (see briefs/reports/map.md): with per-frame interpolation the
// symbol layer must setData every frame and fell to 30 fps at 25k ships; this layer holds 60 fps because the glide,
// dead reckoning, heading ease and opacity fades all run in the vertex shader from per-ship start/end values, so
// the CPU touches the buffer only when a fix arrives or the slot set changes, never per frame.

export const Colour = { Normal: 0, Selected: 1, Dark: 2, Spoof: 3, Sanctioned: 4, Keyline: 5, ClassA: 6, ClassB: 7 } as const
export type Colour = (typeof Colour)[keyof typeof Colour]
export const N_COLOURS = 8
const STRIDE = 28   // floats per instance

const VS = `#version 300 es
layout(location=0) in vec4 a_p;     // x0 y0 x1 y1 (mercator)
layout(location=1) in vec4 a_vt;    // vx vy t0 t1
layout(location=2) in vec4 a_hs;    // h0 dh  w h (css px)
layout(location=3) in vec4 a_uv;    // u0 v0 u1 v1
layout(location=4) in vec4 a_op;    // op0 op1 tFade rotate
layout(location=5) in vec4 a_oc;    // offX offY colour fadeDuration
layout(location=6) in vec4 a_fx;    // fix time on the shown clock (s)
uniform mat4 u_m; uniform float u_now; uniform float u_shown; uniform vec2 u_vp; uniform float u_wrap;
uniform vec4 u_colors[8];
out vec2 v_uv; out vec4 v_col; out float v_op;
const vec2 C[6] = vec2[6](vec2(-.5,-.5), vec2(.5,-.5), vec2(-.5,.5), vec2(-.5,.5), vec2(.5,-.5), vec2(.5,.5));
void main() {
  vec2 c = C[gl_VertexID];
  float span = a_vt.w - a_vt.z;
  float e = span > 0. ? clamp((u_now - a_vt.z) / span, 0., 1.) : 1.;
  float dt = clamp(u_shown - a_fx.x, 0., ${EXTRAP_S}.);                  // dead reckoning from the fix's own time
  vec2 pos = a_p.zw + a_vt.xy * dt + (a_p.xy - a_p.zw) * (1. - e * e * (3. - 2. * e)) + vec2(u_wrap, 0.);
  vec4 clip = u_m * vec4(pos, 0., 1.);
  float h = radians(a_hs.x + a_hs.y * e * e * (3. - 2. * e)) * a_op.w;
  vec2 o = c * a_hs.zw;                                    // y down = stern for a bow-up sprite
  o = vec2(o.x * cos(h) - o.y * sin(h), o.x * sin(h) + o.y * cos(h)) + a_oc.xy;
  gl_Position = clip + vec4(o * 2. / u_vp * vec2(1., -1.) * clip.w, 0., 0.);
  v_uv = mix(a_uv.xy, a_uv.zw, c + .5);
  v_col = u_colors[int(a_oc.z)];
  float f = a_oc.w > 0. ? clamp((u_now - a_op.z) / a_oc.w, 0., 1.) : 1.;
  v_op = mix(a_op.x, a_op.y, f);
}`
const FS = `#version 300 es
precision mediump float;
in vec2 v_uv; in vec4 v_col; in float v_op;
uniform sampler2D u_tex; uniform vec3 u_key;
out vec4 o;
void main() {
  vec2 rg = texture(u_tex, v_uv).rg;
  float k = (1. - rg.r) * rg.g;                            // keyline under the mark
  o = vec4(v_col.rgb * rg.r + u_key * k, rg.r + k) * v_op;
  if (o.a < .004) discard;
}`

export class InstanceBuffer {
  data = new Float32Array(STRIDE * 1024)
  instSlot = new Int32Array(1024)          // instance → ship slot (-1 = fixed position), for O(changed) patches
  count = 0
  private atlas: Atlas
  private state: ShipState
  constructor(atlas: Atlas, state: ShipState) { this.atlas = atlas; this.state = state }
  reset() { this.count = 0 }
  // One quad tied to a ship's motion (slot) or fixed at (x, y) mercator when slot < 0.
  push(slot: number, sprite: string | Sprite | undefined, colour: Colour, rotate: boolean, offX: number, offY: number, scale: number,
       op0: number, op1: number, tFade: number, fadeS: number, x = 0, y = 0): void {
    const sp = typeof sprite === 'string' ? this.atlas.sprites.get(sprite) : sprite
    if (!sp) return
    if ((this.count + 1) * STRIDE > this.data.length) {
      const d = new Float32Array(this.data.length * 2); d.set(this.data); this.data = d
      const q = new Int32Array(this.instSlot.length * 2); q.set(this.instSlot); this.instSlot = q
    }
    this.instSlot[this.count] = slot
    const d = this.data, i = this.count++ * STRIDE, s = this.state
    if (slot >= 0) {
      d[i] = s.x0[slot]; d[i + 1] = s.y0[slot]; d[i + 2] = s.x1[slot]; d[i + 3] = s.y1[slot]
      d[i + 4] = s.vx[slot]; d[i + 5] = s.vy[slot]; d[i + 6] = s.t0[slot]; d[i + 7] = s.t1[slot]
      d[i + 8] = s.h0[slot]; d[i + 9] = s.dh[slot]; d[i + 24] = s.tf[slot]
    } else {
      d[i] = d[i + 2] = x; d[i + 1] = d[i + 3] = y
      d[i + 4] = d[i + 5] = d[i + 6] = d[i + 7] = d[i + 8] = d[i + 9] = d[i + 24] = 0
    }
    d[i + 10] = sp.w * scale; d[i + 11] = sp.h * scale
    d[i + 12] = sp.u0; d[i + 13] = sp.v0; d[i + 14] = sp.u1; d[i + 15] = sp.v1
    d[i + 16] = op0; d[i + 17] = op1; d[i + 18] = tFade; d[i + 19] = rotate ? 1 : 0
    d[i + 20] = offX; d[i + 21] = offY; d[i + 22] = colour; d[i + 23] = fadeS
  }
}

// Rewrite only the motion fields of instance `inst` from its ship's current motion state.
export function writeMotion(buf: InstanceBuffer, state: ShipState, inst: number, slot: number): void {
  const d = buf.data, i = inst * STRIDE
  d[i] = state.x0[slot]; d[i + 1] = state.y0[slot]; d[i + 2] = state.x1[slot]; d[i + 3] = state.y1[slot]
  d[i + 4] = state.vx[slot]; d[i + 5] = state.vy[slot]; d[i + 6] = state.t0[slot]; d[i + 7] = state.t1[slot]
  d[i + 8] = state.h0[slot]; d[i + 9] = state.dh[slot]; d[i + 24] = state.tf[slot]
}

export interface ShipLayerHooks {
  rebuild(buf: InstanceBuffer): number      // fill the buffer; return the time (clock) the last motion or fade ends
  // Optional O(changed) update when only positions moved: write into buf.data, return the dirty instance range.
  patch?(buf: InstanceBuffer): { lo: number; hi: number; end: number } | null
  colours(): { list: Float32Array; key: Float32Array }  // N_COLOURS rgba colours (0..1, flat) and the keyline rgb
}

export function createShipLayer(id: string, atlas: Atlas, buf: InstanceBuffer, hooks: ShipLayerHooks) {
  let map: MapLibreMap
  let gl: WebGL2RenderingContext
  let prog: WebGLProgram, vao: WebGLVertexArrayObject, vbo: WebGLBuffer, tex: WebGLTexture
  let u: Record<string, WebGLUniformLocation | null> = {}
  let dirty = true, patchDue = false, animEnd = 0, colours = hooks.colours(), coloursDirty = false

  const layer: CustomLayerInterface = {
    id, type: 'custom', renderingMode: '2d',
    onAdd(m, g) {
      map = m; gl = g as WebGL2RenderingContext
      const sh = (type: number, src: string) => {
        const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s)
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(`ship shader: ${gl.getShaderInfoLog(s)}`)
        return s
      }
      prog = gl.createProgram()!
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog)
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(`ship program: ${gl.getProgramInfoLog(prog)}`)
      for (const n of ['u_m', 'u_now', 'u_shown', 'u_vp', 'u_wrap', 'u_colors', 'u_tex', 'u_key']) u[n] = gl.getUniformLocation(prog, n)
      vbo = gl.createBuffer()!
      vao = gl.createVertexArray()!
      gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, vbo)
      for (let a = 0; a < 7; a++) {
        gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 4, gl.FLOAT, false, STRIDE * 4, a * 16); gl.vertexAttribDivisor(a, 1)
      }
      gl.bindVertexArray(null)
      tex = gl.createTexture()!
      gl.bindTexture(gl.TEXTURE_2D, tex)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, atlas.width, atlas.height, 0, gl.RGBA, gl.UNSIGNED_BYTE, atlas.pixels)
      for (const [p, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, p, v)
      dirty = true
    },
    onRemove() {
      gl.deleteProgram(prog); gl.deleteBuffer(vbo); gl.deleteVertexArray(vao); gl.deleteTexture(tex)
    },
    render(_g, args: CustomRenderMethodInput) {
      const now = clock()
      if (dirty) {
        buf.reset()
        animEnd = hooks.rebuild(buf)
        gl.bindBuffer(gl.ARRAY_BUFFER, vbo)
        gl.bufferData(gl.ARRAY_BUFFER, buf.data.subarray(0, buf.count * STRIDE), gl.DYNAMIC_DRAW)
        dirty = false
        patchDue = false                                      // the rebuild already holds the new motion
      } else if (patchDue) {
        patchDue = false
        const r = hooks.patch?.(buf)
        if (r && r.hi > r.lo) {
          gl.bindBuffer(gl.ARRAY_BUFFER, vbo)
          gl.bufferSubData(gl.ARRAY_BUFFER, r.lo * STRIDE * 4, buf.data, r.lo * STRIDE, (r.hi - r.lo) * STRIDE)
          animEnd = Math.max(animEnd, r.end)
        }
      }
      if (coloursDirty) { colours = hooks.colours(); coloursDirty = false }
      if (!buf.count) return
      gl.useProgram(prog)
      gl.bindVertexArray(vao)
      gl.uniformMatrix4fv(u.u_m, false, args.defaultProjectionData.mainMatrix as Float32Array)   // mercator 0..1 → clip
      gl.uniform1f(u.u_now, now)
      gl.uniform1f(u.u_shown, shownS())
      const canvas = map.getCanvas()
      gl.uniform2f(u.u_vp, canvas.clientWidth, canvas.clientHeight)
      gl.uniform4fv(u.u_colors, colours.list)
      gl.uniform3fv(u.u_key, colours.key)
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1i(u.u_tex, 0)
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)
      gl.disable(gl.DEPTH_TEST); gl.disable(gl.STENCIL_TEST)
      // Draw every world copy in view (world zoom shows the globe more than once).
      const b = map.getBounds()
      for (let w = Math.floor((b.getWest() + 180) / 360); w <= Math.floor((b.getEast() + 180) / 360); w++) {
        gl.uniform1f(u.u_wrap, w)
        gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, buf.count)
      }
      gl.bindVertexArray(null)
      // Keep the frame loop alive only while something on screen still moves or fades.
      if (now < animEnd) map.triggerRepaint()
    },
  }
  return {
    layer,
    invalidate() { dirty = true; map?.triggerRepaint() },
    patch() { patchDue = true; map?.triggerRepaint() },
    recolour() { coloursDirty = true; map?.triggerRepaint() },
  }
}
