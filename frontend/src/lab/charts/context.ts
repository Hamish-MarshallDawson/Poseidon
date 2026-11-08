import { createContext, useContext, type ReactNode } from 'react'
import type { Domain, Scale } from './scale'

// The chart context: scales and plot box that <Chart> hands to its marks.

export type NumAxis = {
  type?: 'linear' | 'time'
  domain: Domain
  label?: string
  /** Tick label; defaults to time labels (UTC) for `time`, numbers (or percent with `percent`) otherwise. */
  format?: (v: number) => string
  percent?: boolean
  ticks?: number
  /** No gridlines along this axis. */
  noGrid?: boolean
}
export type CatAxis = { type: 'band'; domain: string[]; label?: string; format?: (k: string) => string }
export type Axis = NumAxis | CatAxis

export type Tip = { x: number; y: number; content: ReactNode } | null

export interface ChartCtx {
  /** x position in px of a value (number for linear/time, category for band). */
  X: (v: number | string) => number
  Y: (v: number | string) => number
  /** Band width in px when the axis is categorical, else 0. */
  xBand: number
  yBand: number
  xNum: Scale | null
  yNum: Scale | null
  /** Plot area in px. */
  box: { left: number; top: number; right: number; bottom: number; width: number; height: number }
  tip: (t: Tip) => void
}

export const Ctx = createContext<ChartCtx | null>(null)

export function useChart(): ChartCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('chart marks must sit inside <Chart>')
  return c
}

