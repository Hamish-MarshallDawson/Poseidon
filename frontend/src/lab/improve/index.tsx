import type { LabSectionProps } from '../sections'

// Placeholder slot: lab-improve replaces this file (keep the export name and props). Lab.tsx draws the section heading.
export function Improve(props: LabSectionProps) {
  return <p className="lab-muted">Coming soon: built by lab-improve. {props.sample ? 'Showing sample data.' : ''}</p>
}
