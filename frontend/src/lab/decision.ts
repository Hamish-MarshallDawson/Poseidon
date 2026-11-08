// One reading of a run's stored promotion decision, shared by the runs table and the Improve markers, so both say
// the same thing: who decided (the rule or a person), what the run was compared with, and the plain-words verdict.

export interface DecisionLike {
  promote?: boolean | null
  against?: string | null
  /** 'human' when a person promoted or kept the run by hand; 'rule' (or absent) when the promotion rule decided. */
  by?: string | null
  reasons?: string[] | null
  horizons?: Record<string, { win?: boolean | null } | null | undefined> | null
}

/** `against` names a baseline (no champion to beat), not a champion run: "baseline (no champion yet)",
 *  "global base rate", "dead reckoning (no champion yet)". Anything else ("champion f1", "route-dma14-v3") is a champion. */
export const againstBaseline = (against: string | null | undefined): boolean =>
  !!against && /baseline|base rate|dead reckoning|no champion/i.test(against)

/** "the baseline" or "the champion": what the decision compared the run with. */
export const againstLabel = (d: DecisionLike | null | undefined): 'the baseline' | 'the champion' =>
  againstBaseline(d?.against) ? 'the baseline' : 'the champion'

export const byHand = (d: DecisionLike | null | undefined): boolean => d?.by === 'human'

/** The first stored reason, as stored. */
export function firstReason(d: DecisionLike | null | undefined): string | null {
  return d?.reasons?.find((x) => x && x.trim())?.trim() ?? null
}

export interface Verdict {
  against: 'the baseline' | 'the champion'
  hand: boolean
  /** Horizons (seconds) the run won or lost against `against`, shortest first. */
  won: number[]
  lost: number[]
  reason: string | null
}

export function verdict(d: DecisionLike): Verdict {
  const hs = Object.entries(d.horizons ?? {}).map(([h, v]) => [Number(h), v?.win] as const).sort((a, b) => a[0] - b[0])
  return {
    against: againstLabel(d),
    hand: byHand(d),
    won: hs.filter(([, w]) => w === true).map(([h]) => h),
    lost: hs.filter(([, w]) => w === false).map(([h]) => h),
    reason: firstReason(d),
  }
}

/** A decision made by hand, in words, led by its first reason: "promoted by hand to give the live predictor a go-dark
 *  model", "promoted by hand: first route model: …", "kept as a candidate by hand: no frozen held-out set". The rule's
 *  horizon wins are not claimed: a person decided. `notPromoted` names the outcome when the run was not promoted. */
export function byHandLine(d: DecisionLike, notPromoted = 'not promoted'): string {
  const verb = d.promote ? 'promoted by hand' : `${notPromoted} by hand`
  const r = firstReason(d)
  if (!r) return verb
  if (r.toLowerCase().startsWith(verb)) return r
  return `${verb}: ${r}`
}

/** A promotion by the rule as one phrase, without the verb: "beat the champion at 3 h, 6 h" (the horizons it won), or
 *  "passed the promotion rule against the baseline" when no horizon win is stored. `fmtH` writes a horizon. */
export function promotionWhy(d: DecisionLike, fmtH: (s: number) => string): string {
  const v = verdict(d)
  if (v.won.length) return `beat ${v.against} at ${v.won.map(fmtH).join(', ')}`
  return `passed the promotion rule against ${v.against}`
}
