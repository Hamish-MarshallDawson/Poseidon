import { useEffect } from 'react'
import { ui } from '../store/ui'

// Follow selected (replay): only the open windows' ships are drawn (controller.ts reads ui.follow), cells and chips are
// hidden, and track.ts draws each followed ship's track with the replay head. This hook owns the on/off rule.

/** Turn follow on when replay starts with windows open; off on live or when the last window closes. */
export function useFollowState() {
  useEffect(() => ui.subscribe((s, p) => {
    let next = s.follow
    if (s.feed.mode === 'live' || s.windows.length === 0) next = false
    else if (p.feed.mode === 'live' || p.windows.length === 0) next = true      // entering replay, or the first window opens in replay
    if (next !== s.follow) ui.set({ follow: next })
  }), [])
}
