import './collab.css'
import { useState } from 'react'

// The one avatar for every collaboration surface: the Auth0 picture, or initials on a colour made from the user id.
// `ring` draws a coloured ring (presence on the map); `online` a small dot. Names are plain text.

export interface Person { id: string; name: string | null; picture: string | null }

export function initials(name: string | null | undefined): string {
  const w = (name ?? '').trim().split(/\s+/).filter(Boolean)
  return ((w[0]?.[0] ?? '?') + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase()
}

/** A stable hue per user, so a person looks the same everywhere. */
export function userHue(id: string): number {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 360
  return h
}

export function Avatar({ user, size = 24, ring, online, className }: { user: Person; size?: number; ring?: boolean; online?: boolean; className?: string }) {
  const [broken, setBroken] = useState(false)
  const hue = userHue(user.id)
  const showImg = user.picture && !broken
  return (
    <span
      className={`collab-avatar ${className ?? ''}`}
      title={user.name ?? 'Unknown'}
      style={{
        width: size, height: size, fontSize: Math.max(9, Math.round(size * 0.42)),
        background: showImg ? 'var(--dvm-bg-raised)' : `hsl(${hue} 35% 38%)`,
        boxShadow: ring ? `0 0 0 2px hsl(${hue} 70% 55%)` : undefined,
      }}
    >
      {showImg
        ? <img src={user.picture!} alt="" width={size} height={size} referrerPolicy="no-referrer" onError={() => setBroken(true)} />
        : initials(user.name)}
      {online && <i className="collab-avatar__dot" aria-hidden />}
    </span>
  )
}
