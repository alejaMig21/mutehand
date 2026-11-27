import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { api, loadAppNames, LOCKED } from './api.js'
import Apps from './Apps.jsx'
import { useTryAgain } from './Attention.jsx'
import { getAppNames, onAppNames } from './catalog.js'
import Checks from './Checks.jsx'
import Consents from './Consents.jsx'
import Editor from './Editor.jsx'
import History from './History.jsx'
import Home from './Home.jsx'
import Library from './Library.jsx'
import Queue from './Queue.jsx'
import Schedules from './Schedules.jsx'
import { useRuns } from './useRuns.js'

const SCREENS = [
  ['home', 'Home', null],
  ['apps', 'Apps', Apps],
  ['editor', 'Flow editor', null],
  ['library', 'Steps', Library],
  ['queue', 'Tutor queue', Queue],
  ['history', 'Run history', History],
  ['schedules', 'Schedules', Schedules],
  ['consents', 'Consents', Consents],
  ['checks', 'Setup check', Checks],
]

// the screen survives a reload of this tab, except the setup check: it is shown once
const remembered = () => {
  const id = sessionStorage.getItem('wf-screen')
  return id !== 'checks' && SCREENS.some(([known]) => known === id) ? id : 'home'
}

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
    // the first time, a setup that lacks something says so before anything else; a working one stays on Home
    api('/api/checks').then((r) => r.first_run && r.checks.some((c) => !c.ok && !c.optional)
      && setScreen((now) => (now === 'home' ? 'checks' : now))).catch(() => {})
    return () => window.removeEventListener(LOCKED, lock)
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
    document.title = `${label} · Workflow Factory`
  }, [screen, label])

  async function quit() {
    const lost = unsaved ? ' Changes to the flow that are not saved will be lost.' : ''
    if (!window.confirm(`Close Workflow Factory? Flows that are running will be stopped.${lost}`)) return
    await api('/api/quit', { method: 'POST' }).catch(() => {})
    setClosed(true)
  }
  if (closed) {
    return <main data-testid="closed" className="notice-page"><h1>Workflow Factory is closed</h1>
      <p>You can close this tab. To open it again, run <code>uv run workflow-factory</code> in the project folder.</p></main>
  }
  if (locked) {
    return (
      <main data-testid="locked" className="notice-page" role="alert">
        <h1>This link no longer works</h1>
        <p>Close this tab and start Workflow Factory again: it opens a new link.</p>
      </main>
    )
  }
  return (
    <div className="shell">
      <nav className="tabs" aria-label="screens">
        {SCREENS.map(([id, name]) => (
          <button key={id} data-testid={`tab-${id}`} aria-current={id === screen ? 'page' : undefined} onClick={() => setScreen(id)}>
            {name}
          </button>
        ))}
        <button data-testid="quit" onClick={quit} className="tabs-end">Quit</button>
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
