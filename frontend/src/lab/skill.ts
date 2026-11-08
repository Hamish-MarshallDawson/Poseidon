// Which held-out number a model's live number can be put next to. Go-dark's run records score log-loss skill
// (metrics.skill), but it is graded live on Brier skill, so wherever the two meet (the card strip, the Improve chart,
// the "live is below offline" note) we use the held-out Brier skill from metrics.summary[h].brier_skill, at the same
// horizon. A number is never compared with one of another statistic or horizon. The backend now names these itself
// (offline.statistic; live.statistic, live.horizon_s and live.offline); the derivations here are the fallback for
// older responses and the bundled sample.

export interface SkillRunLike {
  run_id: string
  metrics?: {
    loss_name?: string | null
    skill?: Record<string, { skill: number | null; skill_lo?: number | null; skill_hi?: number | null } | null | undefined> | null
    summary?: Record<string, Record<string, unknown> | null | undefined> | null
  } | null
}
export interface SkillModelLike {
  target: string
  champion: { run_id?: string | null; version: string }
  offline: { primary_h: number; statistic?: string | null; skill: number | null; skill_lo?: number | null; skill_hi?: number | null }
  live?: {
    model_version?: string | null; target?: string | null; statistic?: string | null; horizon_s?: number | null
    offline?: { statistic: string; horizon_s: number; skill: number | null; skill_lo?: number | null; skill_hi?: number | null } | null
    primary?: { name: string; value: number | null } | null
  } | null
}

/** A skill figure with what it measures: `name` is the statistic ("Brier skill", "log-loss skill", "skill"), `h` the horizon (s). */
export interface SkillFigure { name: string; h: number; skill: number; lo: number | null; hi: number | null }

const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const baseVersion = (v: string) => v.replace(/-cal\d+$/, '')
export const isGodark = (target: string) => target.startsWith('godark')

const LOSS_SKILL: Record<string, string> = { log_loss: 'log-loss skill', brier: 'Brier skill', error_m: 'median-error skill', median_err_m: 'median-error skill' }
/** The statistic metrics.skill is computed on, as a name (the backend's offline.statistic names). */
export const lossSkillName = (loss: string | null | undefined) => (loss ? LOSS_SKILL[loss] ?? `${loss.replace(/_/g, '-')} skill` : 'skill')

/** The held-out Brier skill (and its 95% interval) a go-dark run stored in metrics.summary at horizon h. */
export function heldOutBrier(run: SkillRunLike | null | undefined, h: number): Omit<SkillFigure, 'name' | 'h'> | null {
  const s = run?.metrics?.summary?.[String(h)]
  const v = num(s?.brier_skill)
  if (v == null) return null
  const ci = Array.isArray(s?.brier_skill_ci) ? (s!.brier_skill_ci as unknown[]) : []
  return { skill: v, lo: num(ci[0]), hi: num(ci[1]) }
}

/** The champion's run record (a recalibrated "-calN" version maps to its base run). */
export function championRun<R extends SkillRunLike>(model: SkillModelLike, runs: R[]): R | undefined {
  const ids = [model.champion.run_id, model.champion.version, baseVersion(model.champion.version)].filter((x): x is string => !!x)
  for (const id of ids) {
    const r = runs.find((x) => x.run_id === id)
    if (r) return r
  }
  return undefined
}

/** The horizon (s) the live primary figure is graded at: go-dark names it in live.target ("dark_1h"), else in the
 *  figure's name ("Brier skill over the base rate, 1 h", "skill over dead reckoning at 3 h"); otherwise the primary horizon. */
export function liveHorizon(model: SkillModelLike): number {
  if (model.live?.horizon_s != null) return model.live.horizon_s
  const t = /(\d+)h$/.exec(model.live?.target ?? '')
  if (t) return Number(t[1]) * 3600
  const n = [...(model.live?.primary?.name ?? '').matchAll(/(\d+(?:\.\d+)?)\s*(min|h|d)\b/g)].pop()
  if (n) return Number(n[1]) * (n[2] === 'min' ? 60 : n[2] === 'h' ? 3600 : 86400)
  return model.offline.primary_h
}

/** A run's held-out skill at horizon h, on the statistic the live grading uses for this model. Go-dark: Brier skill
 *  from metrics.summary (null when the run did not store it; never the log-loss value instead). Others: metrics.skill. */
export function runHeldOut(target: string, run: SkillRunLike | null | undefined, h: number): SkillFigure | null {
  if (isGodark(target)) {
    const b = heldOutBrier(run, h)
    return b && { name: 'Brier skill', h, ...b }
  }
  const s = run?.metrics?.skill?.[String(h)]
  return s?.skill != null ? { name: lossSkillName(run?.metrics?.loss_name), h, skill: s.skill, lo: s.skill_lo ?? null, hi: s.skill_hi ?? null } : null
}

/** The champion's held-out skill at horizon h (default: its primary horizon), comparable with its live skill. For
 *  route and fishing at the primary horizon this is the summary's own offline figure. */
export function offlineSkill(model: SkillModelLike, runs: SkillRunLike[], h = model.offline.primary_h): SkillFigure | null {
  const run = championRun(model, runs)
  if (isGodark(model.target)) return runHeldOut(model.target, run, h)
  if (h === model.offline.primary_h && model.offline.skill != null)
    return { name: lossSkillName(run?.metrics?.loss_name), h, skill: model.offline.skill, lo: model.offline.skill_lo ?? null, hi: model.offline.skill_hi ?? null }
  return runHeldOut(model.target, run, h)
}

/** The summary's offline figure as recorded (go-dark: log-loss skill), with its statistic named, for when no
 *  comparable figure exists. */
export function recordedOffline(model: SkillModelLike, runs: SkillRunLike[]): SkillFigure | null {
  if (model.offline.skill == null) return null
  const run = championRun(model, runs)
  const name = model.offline.statistic ?? (run ? lossSkillName(run.metrics?.loss_name) : isGodark(model.target) ? 'log-loss skill' : 'skill')
  return { name, h: model.offline.primary_h, skill: model.offline.skill, lo: model.offline.skill_lo ?? null, hi: model.offline.skill_hi ?? null }
}

/** The statistic the live number is on. */
export function liveStatistic(model: SkillModelLike, runs: SkillRunLike[]): string {
  if (model.live?.statistic) return model.live.statistic
  if (isGodark(model.target)) return 'Brier skill'
  return model.offline.statistic ?? lossSkillName(championRun(model, runs)?.metrics?.loss_name)
}

/** Live against held-out, on one statistic at one horizon: the backend's live.offline when it sent the field (null
 *  there means the run has no such number, so nothing is paired), else derived from the run records. Null when the
 *  model has no live grades for its served version. */
export function liveComparison(model: SkillModelLike, runs: SkillRunLike[]): { live: SkillFigure | null; offline: SkillFigure | null } | null {
  const live = model.live
  if (!live) return null
  const name = liveStatistic(model, runs)
  const h = liveHorizon(model)
  const value = live.primary?.value ?? null
  let offline: SkillFigure | null
  if (live.offline !== undefined) {
    const o = live.offline
    offline = o && o.skill != null && o.statistic === name && o.horizon_s === h ? { name, h, skill: o.skill, lo: o.skill_lo ?? null, hi: o.skill_hi ?? null } : null
  } else {
    const f = offlineSkill(model, runs, h)
    offline = f && f.name === name ? f : null
  }
  return { live: value == null ? null : { name, h, skill: value, lo: null, hi: null }, offline }
}
