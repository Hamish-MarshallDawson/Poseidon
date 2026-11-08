import { useEffect, useState } from 'react'
import { adapter } from '../data/index'

// "How the forecast is made" (GET /model/report): shown only when the backend serves the report (fetched once, with
// the login, and opened as a blob: URL because a new-tab link cannot carry the Bearer token).
let report: Promise<string | null> | undefined
export function ReportLink({ className }: { className?: string }) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => { report ??= adapter?.modelReport?.() ?? Promise.resolve(null); report.then(setUrl, () => {}) }, [])
  return url ? <a className={className} href={url} target="_blank" rel="noopener noreferrer">How the forecast is made</a> : null
}
