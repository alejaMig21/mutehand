import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { api, loadAppNames, LOCKED } from './api.js'
import Apps from './Apps.jsx'
import { useTryAgain } from './Attention.jsx'
import { getAppNames, onAppNames } from './catalog.js'
import Editor from './Editor.jsx'
import Home from './Home.jsx'
import { useRuns } from './useRuns.js'

// Home and Apps are the places; the flow screen is reached from Home and has no tab of its own
const SCREENS = [
  ['home', 'Home', null],
  ['apps', 'Apps', Apps],
  ['editor', 'Flow', null],
]
const TABS = SCREENS.filter(([id]) => id !== 'editor')

// the screen survives a reload of this tab (the flow screen brings back the flow it showed)
const remembered = () => {
  const id = sessionStorage.getItem('wf-screen')
  return SCREENS.some(([known]) => known === id) ? id : 'home'
}

const OPEN_AGAIN = 'To open it again, run “uv run mutehand” in the project folder.'

export default function App() {
  const [screen, setScreen] = useState(remembered)
  const [closed, setClosed] = useState(false)
  const [locked, setLocked] = useState(false)
  const [unsaved, setUnsaved] = useState(false)
  const following = useRuns() // shared by Home and the flow screen: a run stays followed across screens
  const tried = useTryAgain(following) // so is a try again: it is reported wherever the person is when it ends
  const flowScreen = useRef(null)
  // the flow screen answers false when the person keeps what it holds instead: then Home stays
  const showFlow = (shown) => shown && setScreen('editor')
  const left = useRef(null) // the flow left through the flow screen's way back: Home gives the focus to its row
  const goHome = (id) => { left.current = id ?? ''; setScreen('home') }
  useEffect(() => {
    const lock = () => setLocked(true)
    window.addEventListener(LOCKED, lock)
    return () => window.removeEventListener(LOCKED, lock)
  }, [])
  const menu = useRef(null)
  useEffect(() => { // the More menu closes when the page is clicked anywhere else (a tab included) or Escape is pressed
    const close = (e) => {
      if (!menu.current?.open) return
      if (e.type === 'keydown' ? e.key === 'Escape' : !menu.current.contains(e.target)) menu.current.open = false
    }
    document.addEventListener('click', close)
    document.addEventListener('keydown', close)
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', close) }
  }, [])
  const [, label, Current] = SCREENS.find(([id]) => id === screen)
  useSyncExternalStore(onAppNames, getAppNames) // every screen is drawn again when the apps' names arrive
  useEffect(() => { // an app may have been seen since: the tutor teaching, or a scheduled run
    loadAppNames()
    window.addEventListener('focus', loadAppNames)
    return () => window.removeEventListener('focus', loadAppNames)
  }, [screen])
  useEffect(() => {
    sessionStorage.setItem('wf-screen', screen)
    document.title = `${label} · Mutehand`
  }, [screen, label])

  // it asks only when something would be lost: a run in progress or a change not kept. Nothing is lost otherwise.
  const running = Object.values(following.runs).some((run) => run.status === 'running')
  async function quit() {
    const lost = [running && 'The flow that is running will be stopped.', unsaved && 'Changes that are not saved will be lost.'].filter(Boolean)
    if (lost.length && !window.confirm(`Close the program? ${lost.join(' ')} ${OPEN_AGAIN}`)) return
    await api('/api/quit', { method: 'POST' }).catch(() => {})
    setClosed(true)
  }
  if (closed) {
    return <main data-testid="closed" className="notice-page"><h1>Mutehand is closed</h1>
      <p>You can close this tab. {OPEN_AGAIN}</p></main>
  }
  if (locked) {
    return (
      <main data-testid="locked" className="notice-page" role="alert">
        <h1>This link no longer works</h1>
        <p>Close this tab and start Mutehand again: it opens a new link.</p>
      </main>
    )
  }
  return (
    <div className="shell">
      <nav className="tabs" aria-label="screens">
        <button className="brand" data-testid="brand" aria-label="Mutehand: go to Home" onClick={() => setScreen('home')}>Mutehand</button>
        {/* the flow screen belongs to Home: its tab stays the current one */}
        {TABS.map(([id, name]) => (
          <button key={id} data-testid={`tab-${id}`} aria-current={id === screen || (id === 'home' && screen === 'editor') ? 'page' : undefined}
            onClick={() => setScreen(id)}>
            {name}
          </button>
        ))}
        {/* closing is rare and a browser tab can be closed anyway, so it is kept one step away from the tabs */}
        <details className="tabs-end app-more" ref={menu}>
          <summary data-testid="app-more-toggle">More</summary>
          <div className="app-more-menu">
            <button data-testid="quit" onClick={quit} title={`Closes the program. ${OPEN_AGAIN}`}>Close the program</button>
          </div>
        </details>
      </nav>
      <main className="screen">
        {/* the editor stays mounted so unsaved nodes, edges and run context survive a tab change */}
        <div style={{ display: screen === 'editor' ? 'block' : 'none', height: '100%' }}>
          <Editor ref={flowScreen} active={screen === 'editor'} onOpen={setScreen} onBack={goHome} onUnsaved={setUnsaved}
            following={following} tried={tried} />
        </div>
        {screen === 'home' && (
          <Home following={following} tried={tried} left={left} onOpen={(id) => showFlow(flowScreen.current.open(id))}
            onNew={() => showFlow(flowScreen.current.create())} />
        )}
        {Current && <Current onStart={() => setScreen('editor')} />}
      </main>
    </div>
  )
}
