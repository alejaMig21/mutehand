import { titleOf } from './catalog.js'
import { Icon } from './icons.jsx'

const WORDS = {
  running: 'started', done: 'done', blocked: 'stopped', skipped: 'skipped', continued: 'failed, carried on',
  paused: 'paused: you moved the mouse',
}

// The sheet along the bottom: what each node did, in order.
export default function RunLog({ log, nodes, running, onClose }) {
  const title = (id) => {
    const node = nodes.find((n) => n.id === id)
    return node ? titleOf(node.data.node) : id
  }
  return (
    <section className="run-log" aria-label="Run log" data-testid="run-log">
      <header>
        <h2>Run log</h2>
        {!running && <button className="icon-button" aria-label="Close the run log" onClick={onClose}><Icon name="close" /></button>}
      </header>
      <ol aria-live="polite">
        {log.length === 0 && <li className="muted">{running ? 'Starting…' : 'No node ran.'}</li>}
        {log.map((event, i) => (
          <li key={i}><time>{event.at}</time> <b>{title(event.node)}</b> {WORDS[event.status] ?? event.status}</li>
        ))}
      </ol>
    </section>
  )
}
