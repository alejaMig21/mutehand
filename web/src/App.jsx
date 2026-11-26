import { useEffect, useState } from 'react'
import { api, LOCKED } from './api.js'
import Checks from './Checks.jsx'
import Consents from './Consents.jsx'
import Editor from './Editor.jsx'
import History from './History.jsx'
import Library from './Library.jsx'
import Queue from './Queue.jsx'
import Schedules from './Schedules.jsx'

const SCREENS = [
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
  return id !== 'checks' && SCREENS.some(([known]) => known === id) ? id : 'editor'
}

export default function App() {
  const [screen, setScreen] = useState(remembered)
  const [closed, setClosed] = useState(false)
  const [locked, setLocked] = useState(false)
  const [unsaved, setUnsaved] = useState(false)
  useEffect(() => {
    const lock = () => setLocked(true)
    window.addEventListener(LOCKED, lock)
    // the first time, say what is ready before anything else
    api('/api/checks').then((r) => r.first_run && setScreen('checks')).catch(() => {})
    return () => window.removeEventListener(LOCKED, lock)
  }, [])
  const [, label, Current] = SCREENS.find(([id]) => id === screen)
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
          <Editor active={screen === 'editor'} onOpen={setScreen} onUnsaved={setUnsaved} />
        </div>
        {Current && <Current onStart={() => setScreen('editor')} />}
      </main>
    </div>
  )
}
