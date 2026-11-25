import { useState } from 'react'
import Consents from './Consents.jsx'
import Editor from './Editor.jsx'
import History from './History.jsx'
import Library from './Library.jsx'
import Queue from './Queue.jsx'

const SCREENS = [
  ['editor', 'Flow editor', Editor],
  ['library', 'Lessons', Library],
  ['queue', 'Tutor queue', Queue],
  ['history', 'Run history', History],
  ['consents', 'Consents', Consents],
]

export default function App() {
  const [screen, setScreen] = useState('editor')
  const Current = SCREENS.find(([id]) => id === screen)[2]
  return (
    <div className="shell">
      <nav className="tabs" aria-label="screens">
        {SCREENS.map(([id, label]) => (
          <button key={id} data-testid={`tab-${id}`} aria-current={id === screen} onClick={() => setScreen(id)}>
            {label}
          </button>
        ))}
      </nav>
      <main className="screen">
        {/* the editor stays mounted so unsaved nodes, edges and run context survive a tab change */}
        <div style={{ display: screen === 'editor' ? 'block' : 'none', height: '100%' }}><Editor /></div>
        {screen !== 'editor' && <Current />}
      </main>
    </div>
  )
}
