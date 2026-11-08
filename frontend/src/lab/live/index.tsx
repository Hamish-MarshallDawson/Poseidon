import type { LabSectionProps } from '../sections'

// Placeholder slot: lab-live replaces this file (keep the export name and props). Lab.tsx draws the section heading.
export function Live(props: LabSectionProps) {
  return <p className="lab-muted">Coming soon: built by lab-live. {props.sample ? 'Showing sample data.' : ''}</p>
}
