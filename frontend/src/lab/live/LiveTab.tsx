import type { LiveTabProps } from '../tabs'
import { LiveTrackRecord } from './LiveTrackRecord'

// STUB from lab2-nav: lab2-live replaces this file (keep the export name and props).
export function LiveTab({ model, metrics }: LiveTabProps) {
  return <LiveTrackRecord metrics={metrics} champions={model.summary ? [model.summary.champion.version] : []} />
}
