import { initials, ringIndex, safePicture } from './logic'

// A round avatar with a coloured ring (stable per user) and an initials fallback. Plain text only: names are never HTML.
export function Avatar({ id, name, picture, size = 22, ring = true }: {
  id: string; name: string | null; picture: string | null; size?: number; ring?: boolean
}) {
  const src = safePicture(picture)
  return (
    <span className={`pr-av ${ring ? 'ring' : ''}`} data-ring={ringIndex(id)} style={{ width: size, height: size, fontSize: Math.round(size * 0.42) }}
      title={name ?? 'Member'} role="img" aria-label={name ?? 'Member'}>
      {src ? <img src={src} alt="" referrerPolicy="no-referrer" onError={(e) => { e.currentTarget.style.display = 'none' }} /> : null}
      <b aria-hidden>{initials(name)}</b>
    </span>
  )
}
