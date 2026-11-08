import type { LabSectionProps } from '../sections'

// Placeholder slot: lab-runs replaces this file (keep the export name and props). Lab.tsx draws the section heading.
export function Runs(props: LabSectionProps) {
  return <p className="lab-muted">Coming soon: built by lab-runs. {props.sample ? 'Showing sample data.' : ''}</p>
}
