// Typed calls for every REST route in backend/dvm/collab/README.md. Plain text only: render every name, title and
// body as text, never HTML. Auth: the Auth0 access token (bound by bindCollabAuth), or in local dev (VITE_AUTH=off)
// the X-Dev-User header, which makes two browsers two users.

export interface User { id: string; name: string | null; picture: string | null }
export interface Member { id: string; name: string | null; picture: string | null; role: 'owner' | 'member'; joined_at: number; last_active_at: number }
export type Status = 'open' | 'reviewed' | 'no_action'
export interface Entry { mmsi: number; status: Status; added_by: string; added_at: number; updated_by: string; updated_at: number }
export interface Doc { id: number; mmsi: number | null; author_id: string; body: string; created_at: number }
export interface Session { id: string; title: string; created_by: string; created_at: number; members: Member[]; list: Entry[]; documents: Doc[] }
export interface SessionRow { id: string; title: string; role: 'owner' | 'member'; created_at: number; last_active_at: number; members: number }
export interface LastSession { id: string; title: string; role: 'owner' | 'member'; last_active_at: number }
export interface ActivityRow { id: number; actor_id: string; kind: string; mmsi: number | null; at: number }
export interface Invite { token: string; session_id: string; expires_at: number }

/** True only in a dev build started with VITE_AUTH=off. A production build never takes this path. */
export const AUTH_OFF = import.meta.env.DEV && import.meta.env.VITE_AUTH === 'off'

/** Local dev user: ?dev_user=Name (remembered per tab), so two tabs or contexts are two users. */
export const devUser: string | null = (() => {
  if (!AUTH_OFF) return null
  try {
    const q = new URLSearchParams(location.search).get('dev_user')
    if (q) sessionStorage.setItem('dvm.dev_user', q)
    return sessionStorage.getItem('dvm.dev_user') || 'local'
  } catch { return 'local' }
})()

let getToken: () => Promise<string | undefined> = async () => undefined
export function bindCollabAuth(fn: (() => Promise<string | undefined>) | null) { getToken = fn ?? (async () => undefined) }

const base = () => import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class CollabError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const token = await getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (devUser) headers['X-Dev-User'] = devUser
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${base()}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!res.ok) throw new CollabError(res.status, `${method} ${path}: ${res.status}`)
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export const api = {
  me: () => call<{ user: User; last_session: LastSession | null }>('GET', '/me'),
  setMe: (p: { name?: string | null; picture?: string | null }) => call<{ user: User }>('POST', '/me', p),
  createSession: (title: string) => call<Session>('POST', '/sessions', { title }),
  sessions: () => call<{ sessions: SessionRow[] }>('GET', '/sessions'),
  session: (id: string) => call<Session>('GET', `/sessions/${id}`),
  activity: (id: string, limit = 50) => call<{ activity: ActivityRow[] }>('GET', `/sessions/${id}/activity?limit=${limit}`),
  createInvite: (id: string) => call<Invite>('POST', `/sessions/${id}/invites`),
  acceptInvite: (token: string) => call<Session>('POST', `/invites/${encodeURIComponent(token)}/accept`),
  listAdd: (id: string, mmsi: number, status: Status = 'open') => call<{ entry: Entry }>('POST', `/sessions/${id}/list`, { mmsi, status }),
  listSet: (id: string, mmsi: number, status: Status) => call<{ entry: Entry }>('PATCH', `/sessions/${id}/list/${mmsi}`, { status }),
  listRemove: (id: string, mmsi: number) => call<void>('DELETE', `/sessions/${id}/list/${mmsi}`),
  addDocument: (id: string, body: string, mmsi: number | null = null) => call<{ document: Doc }>('POST', `/sessions/${id}/documents`, { mmsi, body }),
}
