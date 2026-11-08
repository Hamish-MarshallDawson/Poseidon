import { lazy, Suspense, useEffect } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import ThemeMenu from './theme/ThemeMenu'
import { Button, Panel } from './ui'
import MapView from './map/MapView'
import { adapter, onDetail, useFeed } from './data/index'
import { ScrubBar } from './timeline/ScrubBar'
import { ReplayChrome } from './timeline/ReplayChrome'
import { ForecastOverlay } from './forecast/ForecastOverlay'
import { WindowsRoot } from './windows/WindowsRoot'
import { bindDetailSender, receiveDetail } from './windows/detail'
import { BriefingPanel } from './briefing/BriefingPanel'
import { bindBriefingAuth } from './briefing/store'
import { Review } from './review/ReviewPanel'

const TokensDemo = lazy(() => import('./tokens/TokensDemo'))
const WindowsDemo = lazy(() => import('./windows/demo/WindowsDemo'))
const BasemapDemo = lazy(() => import('./basemap/BasemapDemo'))

// Auth0 login gates the map; the backend checks the same access token on the WebSocket.
export default function App() {
  const { isLoading, isAuthenticated, error, loginWithRedirect, logout, getAccessTokenSilently } = useAuth0()
  const demo = new URLSearchParams(location.search).get('demo')
  if (demo === 'tokens') return <Suspense><TokensDemo /></Suspense>
  if (demo === 'windows') return <Suspense><WindowsDemo /></Suspense>
  if (demo === 'basemap') return <Suspense><BasemapDemo /></Suspense>
  if (isLoading) return <div className="gate"><p className="gate__foot">Loading…</p></div>
  if (!isAuthenticated) {
    return (
      <div className="gate">
        <Panel className="gate__card">
          <h1>POSEIDON</h1>
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
      onLogout={() => logout({ logoutParams: { returnTo: window.location.origin } })}
    />
  )
}

// The map-first screen: the map is everything; windows, panels, the scrub bar and the forecast drop in over it.
function Monitor({ getToken, onLogout }: { getToken: () => Promise<string | undefined>; onLogout: () => void }) {
  useFeed(getToken)
  useEffect(() => {
    bindDetailSender((m) => adapter?.send(m))
    bindBriefingAuth(getToken)
    const off = onDetail(receiveDetail)
    return () => { off(); bindDetailSender(null); bindBriefingAuth(null) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return (
    <>
      <MapView />
      <ForecastOverlay />
      <WindowsRoot onLogout={onLogout} />
      <BriefingPanel />
      <Review />
      <ReplayChrome />
      <ScrubBar />
      <ThemeMenu />
    </>
  )
}
