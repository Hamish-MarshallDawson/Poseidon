import { lazy, Suspense, useEffect } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Button, Panel } from './ui'
import MapView from './map/MapView'
import { adapter, onDetail, useFeed } from './data/index'
import { ScrubBar } from './timeline/ScrubBar'
import { ReplayChrome } from './timeline/ReplayChrome'
import { ForecastOverlay } from './forecast/ForecastOverlay'
import { useFollowState } from './map/follow'
import { WindowsRoot } from './windows/WindowsRoot'
import { bindDetailSender, receiveDetail } from './windows/detail'
import { BriefingPanel } from './briefing/BriefingPanel'
import { bindBriefingAuth } from './briefing/store'
import { bindYachtsAuth } from './yachts/store'
import { bindPopularAuth } from './data/popular'
import { Review } from './review/ReviewPanel'
import { Channel } from './collab/docs/Channel'
import { AUTH_OFF, bindCollabAuth, devUser } from './collab/client'
import { loadMe } from './collab/store'
import { bindSocket } from './collab/socket'
import { Presence } from './collab/presence/Presence'
import { CollabEntry } from './collab/entry/CollabEntry'

const TokensDemo = lazy(() => import('./tokens/TokensDemo'))
const WindowsDemo = lazy(() => import('./windows/demo/WindowsDemo'))
const BasemapDemo = lazy(() => import('./basemap/BasemapDemo'))

// Auth0 login gates the map; the backend checks the same access token on the WebSocket.
export default function App() {
  const { isLoading, isAuthenticated, error, loginWithRedirect, logout, getAccessTokenSilently, user } = useAuth0()
  const demo = new URLSearchParams(location.search).get('demo')
  if (demo === 'tokens') return <Suspense><TokensDemo /></Suspense>
  if (demo === 'windows') return <Suspense><WindowsDemo /></Suspense>
  if (demo === 'basemap') return <Suspense><BasemapDemo /></Suspense>
  // VITE_AUTH=off (dev server only, never in a production build): skip Auth0; the backend must run with AUTH0_* empty.
  if (AUTH_OFF) return <Monitor getToken={async () => undefined} onLogout={() => {}} profile={{ name: devUser, email: `${devUser}@dev.local`.toLowerCase() }} />
  if (isLoading) return <div className="gate"><p className="gate__foot">Loading…</p></div>
  if (!isAuthenticated) {
    return (
      <div className="gate">
        <Panel className="gate__card">
          <h1><img className="gate__logo" src="/Logo/poseidon-wordmark.png" alt="POSEIDON" width={755} height={106} /></h1>
          <p className="gate__lede">Ships that go quiet on AIS while reception nearby is normal, ranked for review. Never an accusation.</p>
          <Button variant="filled" onClick={() => loginWithRedirect()}>Log in to view the map</Button>
          {error && <p className="error" role="alert">{error.message}</p>}
          <p className="gate__foot">HackTheBurgh · team Hedged Bets</p>
        </Panel>
      </div>
    )
  }
  return (
    <Monitor
      getToken={() => getAccessTokenSilently()}
      profile={user ? { name: user.name ?? user.nickname, picture: user.picture, email: user.email_verified ? user.email : undefined } : undefined}
      onLogout={() => logout({ logoutParams: { returnTo: window.location.origin } })}
    />
  )
}

// The map-first screen: the map is everything; windows, panels, the scrub bar and the forecast drop in over it.
export function Monitor({ getToken, onLogout, profile }: { getToken: () => Promise<string | undefined>; onLogout: () => void; profile?: { name?: string | null; picture?: string | null; email?: string | null } }) {
  useFeed(getToken)
  useFollowState()
  useEffect(() => {
    bindDetailSender((m) => adapter?.send(m))
    bindBriefingAuth(getToken)
    bindYachtsAuth(getToken)
    bindPopularAuth(getToken)
    bindCollabAuth(getToken)
    const unbindSocket = bindSocket()
    if (profile) void loadMe(profile)
    const off = onDetail(receiveDetail)
    return () => { off(); bindDetailSender(null); bindBriefingAuth(null); bindYachtsAuth(null); bindPopularAuth(null); bindCollabAuth(null); unbindSocket() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return (
    <>
      <MapView />
      <ForecastOverlay />
      <WindowsRoot onLogout={onLogout} />
      <BriefingPanel />
      <Review />
      <Channel />
      <Presence />
      <ReplayChrome />
      <ScrubBar />
      <CollabEntry />
    </>
  )
}
