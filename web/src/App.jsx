import { useState } from 'react'
import { api } from './api.js'
import Consents from './Consents.jsx'
import Editor from './Editor.jsx'
import History from './History.jsx'
import Library from './Library.jsx'
import Queue from './Queue.jsx'
import Schedules from './Schedules.jsx'

const SCREENS = [
  ['editor', 'Flow editor', Editor],
  ['library', 'Steps', Library],
  ['queue', 'Tutor queue', Queue],
  ['history', 'Run history', History],
  ['schedules', 'Schedules', Schedules],
  ['consents', 'Consents', Consents],
]

export default function App() {
  const [screen, setScreen] = useState('editor')
  const [closed, setClosed] = useState(false)
  const Current = SCREENS.find(([id]) => id === screen)[2]
  async function quit() {
    if (!window.confirm('Close Workflow Factory? Flows that are running will be stopped.')) return
    await api('/api/quit', { method: 'POST' }).catch(() => {})
    setClosed(true)
  }
  if (closed) {
    return <p data-testid="closed" className="screen">Workflow Factory is closed. You can close this tab.</p>
  }
  return (
    <div className="shell">
      <nav className="tabs" aria-label="screens">
        {SCREENS.map(([id, label]) => (
          <button key={id} data-testid={`tab-${id}`} aria-current={id === screen} onClick={() => setScreen(id)}>
            {label}
          </button>
        ))}
        <button data-testid="quit" onClick={quit} style={{ marginLeft: 'auto' }}>Quit</button>
      </nav>
      <main className="screen">
        {/* the editor stays mounted so unsaved nodes, edges and run context survive a tab change */}
        <div style={{ display: screen === 'editor' ? 'block' : 'none', height: '100%' }}><Editor /></div>
        {screen !== 'editor' && <Current />}
      </main>
    </div>
  )
}
