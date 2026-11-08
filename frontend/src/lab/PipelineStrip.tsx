import { when } from './format'
import type { Stage } from './model'

// The pipeline strip on top of a model page: each step with its real count and latest time. Promote and reject are
// one step ("Promote / reject").
export function PipelineStrip({ stages }: { stages: Stage[] }) {
  const by = Object.fromEntries(stages.map((s) => [s.key, s]))
  const steps: { label: string; value: string; last: number | null }[] = [
    { label: 'New data', value: n(by.new_data?.n, 'examples'), last: by.new_data?.last ?? null },
    { label: 'Gemini proposes', value: n(by.proposed?.n, 'ideas'), last: by.proposed?.last ?? null },
    { label: 'Train', value: n(by.trained?.n, 'runs'), last: by.trained?.last ?? null },
    { label: 'Judge on frozen test', value: n(by.judged?.n, 'judged'), last: by.judged?.last ?? null },
    { label: 'Promote / reject', value: `${by.promoted?.n ?? '–'} ✓ · ${by.rejected?.n ?? '–'} ✗`, last: latest(by.promoted?.last, by.rejected?.last) },
    { label: 'Live grading', value: n(by.graded?.n, 'graded'), last: by.graded?.last ?? null },
  ]
  return (
    <ol className="lab-pipe" aria-label="How a model improves">
      {steps.map((s) => (
        <li key={s.label}>
          <span className="lab-pipe__label">{s.label}</span>
          <span className="lab-pipe__n">{s.value}</span>
          <span className="lab-pipe__t">{s.last ? when(s.last) : '–'}</span>
        </li>
      ))}
    </ol>
  )
}
const n = (x: number | null | undefined, unit: string) => (x == null ? '–' : `${x.toLocaleString('en-GB')} ${unit}`)
const latest = (a: number | null | undefined, b: number | null | undefined) => (a == null ? b ?? null : b == null ? a : Math.max(a, b))
