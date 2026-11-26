import { useEffect, useRef, useState } from 'react'
import { api, encode, loadAppNames, UNREACHABLE } from './api.js'
import { appLabel, chipFor } from './catalog.js'
import { Icon } from './icons.jsx'
import Screen from './Screen.jsx'
import { useLoad } from './useLoad.js'
import { blockedWords, flowTitle, lastRunWords, runNoteWords } from './words.js'

// The first screen: the person's flows ("chores" on screen), how each went, and Run now. `onOpen` shows a flow on the
// flow screen, `onNew` an empty one.
export default function Home({ following, onOpen, onNew }) {
  const { offline, attach, settled } = following
  const load = useLoad('/api/flow-summaries')
  const { reload } = load
  const flows = load.data

  // a run that ended, another window or a scheduled run may have changed what is true: read it again
  useEffect(() => {
    const again = () => { reload(); attach(); loadAppNames() }
    again()
    window.addEventListener('focus', again)
    return () => window.removeEventListener('focus', again)
  }, [settled, reload, attach])

  return (
    <div className="home">
      <Screen title="Your chores" load={load} isEmpty={flows.length === 0} emptyId="no-chores"
        empty="No chores yet. Press “New chore” to make your first one."
        above={offline && <p className="home-notice" role="status">{UNREACHABLE} Trying again…</p>}
        tools={<button data-testid="new-chore" onClick={onNew}><Icon name="plus" size={20} /> New chore</button>}>
        <ul className="chores">
          {flows.map((flow) => (
            <Chore key={flow.id} flow={flow} title={flowTitle(flow.id, flows)} following={following} reload={reload}
              onOpen={() => onOpen(flow.id)} />
          ))}
        </ul>
      </Screen>
    </div>
  )
}

function Chore({ flow, title, following: { runs, follow, attach, forget }, reload, onOpen }) {
  const { id, app } = flow
  const run = runs[id]
  const running = run?.status === 'running'
  const [starting, setStarting] = useState(false)
  const [problem, setProblem] = useState('')
  const asked = useRef(false) // two presses ask the server once
  useEffect(() => { if (running) setProblem('') }, [running]) // it runs after all: what went wrong asking no longer matters

  const appName = app ? appLabel(app) : 'No app chosen'
  const chip = chipFor(app || title)
  const paused = running && Object.values(run.nodes).includes('paused')
  const last = lastRunWords(flow.last_run)
  const line = !running ? last : paused
    ? { words: 'Paused: you moved the mouse. It resumes when you stop using the PC.', tone: 'warn', icon: 'pause' }
    : { words: 'Running now', tone: 'info', icon: 'spinner' }
  const wrong = !running && (problem || runNoteWords(run, appName))
  const why = !running && blockedWords(flow.blocked, app && appName)
  const label = running ? 'Stop' : starting ? 'Starting…' : why ? 'Cannot run yet' : 'Run now'
  const unavailable = starting || (running && !run.armed) || Boolean(why)

  async function press() {
    if (unavailable) return
    setProblem('')
    try {
      if (running) { // one mouse and keyboard: this ends every run at once
        await api(`/api/runs/${run.runId}/stop`, { method: 'POST' })
        return
      }
      if (asked.current) return
      asked.current = true
      setStarting(true)
      forget(id)
      const { run_id } = await api(`/api/flows/${encode(id)}/run`, { method: 'POST', body: { app, context: {} } })
      follow(id, run_id)
    } catch (e) {
      if (running && e.status === 409) return // it had just ended
      setProblem(e.message)
      // the answer may be all that was lost, or it runs already: show it, with its Stop button, or what is true by now
      attach().then(reload)
    } finally {
      asked.current = false
      setStarting(false)
    }
  }

  return (
    <li className="chore" data-testid={`chore-${id}`}>
      <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
      <div className="chore-words">
        {/* the button covers the whole row, under the row's other controls */}
        <h2><button className="chore-open" data-testid={`open-chore-${id}`} onClick={onOpen}>{title}</button></h2>
        <p className="muted">{appName}</p>
        <p className={`chore-line tone-${line.tone}`} role="status"><Icon name={line.icon} size={18} /> {line.words}</p>
        {why && <p className="chore-line tone-warn" id={`why-${id}`} data-testid={`chore-why-${id}`}><Icon name="alert" size={18} /> {why}</p>}
        {wrong && <p className="chore-line tone-bad" role="alert"><Icon name="alert" size={18} /> {wrong}</p>}
      </div>
      {/* one button that changes its words, so the keyboard focus stays on it; aria-disabled keeps it focusable */}
      <button className={`chore-run ${running ? 'danger' : why ? 'cannot' : 'primary'}`} data-testid={`run-now-${id}`} onClick={press}
        aria-disabled={unavailable || undefined} aria-describedby={why ? `why-${id}` : undefined} aria-label={`${label}: ${title}`}>
        <Icon name={running ? 'stop' : 'play'} size={20} /> {label}
      </button>
    </li>
  )
}
