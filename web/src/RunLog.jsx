import { useState } from 'react'
import { titleOf } from './catalog.js'
import { Icon } from './icons.jsx'
import { RUN_MARKS } from './NodeCard.jsx'

const WORDS = {
  running: 'started', done: 'done', blocked: 'stopped', skipped: 'skipped', continued: 'failed, carried on',
  paused: 'paused: you moved the mouse',
}

// A small card over the corner of the canvas: one picture per box (so the progress reads without words), and the
// full list of what each box did one button away. It floats, so a run never shrinks the boxes.
export default function RunLog({ log, nodes, steps, running, onClose }) {
  const [open, setOpen] = useState(false)
  const title = (id) => {
    const node = nodes.find((n) => n.id === id)
    return node ? titleOf(node.data.node) : id
  }
  return (
    <section className="run-log" aria-label="Run log" data-testid="run-log">
      <header>
        <h2>Run</h2>
        <ul className="run-progress" aria-label="Progress by box">
          {steps.map(({ id, number, state }) => {
            const [glyph, word, tone] = RUN_MARKS[state] ?? RUN_MARKS.unreached
            return (
              <li key={id} className={`tone-${tone}`} data-testid={`progress-${id}`} data-state={state} title={`${number}. ${title(id)}: ${word}`}>
                {number}<Icon name={glyph} size={16} /><span className="sr-only">{`Box ${number}: ${word}`}</span>
              </li>
            )
          })}
        </ul>
        <button aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Hide details' : 'Show details'}</button>
        {!running && <button className="icon-button" aria-label="Close the run log" onClick={onClose}><Icon name="close" /></button>}
      </header>
      {open && (
        <ol aria-live="polite">
          {log.length === 0 && <li className="muted">{running ? 'Starting…' : 'No node ran.'}</li>}
          {log.map((event, i) => (
            <li key={i}><time>{event.at}</time> <b>{title(event.node)}</b> {WORDS[event.status] ?? event.status}</li>
          ))}
        </ol>
      )}
    </section>
  )
}
