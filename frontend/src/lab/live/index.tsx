import type { LabSectionProps } from '../sections'
import { DataCollected } from './DataCollected'
import { LiveTrackRecord } from './LiveTrackRecord'

// The Lab's "Live track record" slot (Lab.tsx draws the section heading): graded predictions from /lab/metrics,
// then "Data collected" from /lab/data. The headline sentence speaks for the running route champion.
export function Live({ metrics, data, summary }: LabSectionProps) {
  const champions = summary?.models.map((m) => m.champion.version).filter(Boolean) ?? []
  return (
    <>
      <LiveTrackRecord metrics={metrics} champions={champions} />
      <DataCollected data={data} />
    </>
  )
}

export { LiveTab, StatusDot } from './LiveTab'
export type { Level, ModelRef } from './plain'
export type { LiveTabProps } from './LiveTab'
