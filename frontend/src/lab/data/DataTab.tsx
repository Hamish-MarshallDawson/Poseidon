import type { DataTabProps } from '../tabs'
import { DataCollected } from '../live/DataCollected'

// STUB from lab2-nav: lab2-live replaces this file (keep the export name and props).
export function DataTab({ data }: DataTabProps) {
  return <DataCollected data={data} />
}
