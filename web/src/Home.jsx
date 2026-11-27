import { useEffect, useRef, useState } from 'react'
import { api, encode, loadAppNames, UNREACHABLE } from './api.js'
import { Attention, TriedResults } from './Attention.jsx'
import { appLabel, chipFor } from './catalog.js'
import { changeDaily, DailyForm } from './Daily.jsx'
import FirstDay, { FIRST_DAY_TITLE } from './FirstDay.jsx'
import { Icon } from './icons.jsx'
import More, { useDeleted } from './More.jsx'
import Screen from './Screen.jsx'
import { useLoad } from './useLoad.js'
import { blockedWords, flowTitle, lastRunWords, PAUSED_WORDS, runNoteWords } from './words.js'

// The first screen: the person's flows ("chores" on screen), how each went, and Run now. `onOpen` shows a flow on the
// flow screen, `onNew` an empty one; `left` holds the flow the person has just come back from, if any.
export default function Home({ following, tried, left, onOpen, onNew }) {
  const { offline, attach, settled } = following
  const load = useLoad('/api/flow-overview', { keep: true })
  const { reload } = load
  const flows = load.data
  const needs = useLoad('/api/attention', { keep: true }) // what stopped and waits for the person
  const stopped = needs.data.filter((item) => item.kind === 'stopped')
  const reloadNeeds = needs.reload
  const undo = useDeleted(reload, flows)
  const [bare, setBare] = useState(false) // nothing is learned yet: Home says what the product is for
  const none = flows.length === 0

  // the button that led back is gone with the flow screen: the focus goes to the flow's row
  useEffect(() => {
    if (load.loading || left.current === null) return
    const target = flows.some((flow) => flow.id === left.current) ? `open-chore-${left.current}` : 'new-chore'
    left.current = null
    document.querySelector(`[data-testid="${target}"]`)?.focus()
  }, [load.loading]) // eslint-disable-line react-hooks/exhaustive-deps

  // a run that ended, another window or a scheduled run may have changed what is true: read it again
  useEffect(() => {
    const again = () => { reload(); reloadNeeds(); attach(); loadAppNames() }
    again()
    window.addEventListener('focus', again)
    return () => window.removeEventListener('focus', again)
  }, [settled, reload, reloadNeeds, attach])

  return (
    <div className="home">
      <TriedResults tries={tried.tries} hide={tried.hide} />
      <Attention items={needs.data} tries={tried.tries} tryAgain={tried.tryAgain} onChanged={() => { reload(); reloadNeeds() }}
        running={(id) => following.runs[id]?.status === 'running'} />
      <Screen title={none && bare ? FIRST_DAY_TITLE : 'Your chores'} load={load} isEmpty={false}
        help={none && bare ? 'When you press a button, or by itself every morning.' : undefined}
        above={offline && <p role="status">{UNREACHABLE} Trying again…</p>}
        tools={!none && <button data-testid="new-chore" onClick={onNew}><Icon name="plus" size={20} /> New chore</button>}>
        {none ? <FirstDay onNew={onNew} onFirstDay={setBare} /> : (
          <ul className="chores">
            {flows.map((flow) => (
              <Chore key={flow.id} flow={flow} title={flowTitle(flow.id, flows)} following={following} reload={reload}
                stopped={stopped.find((item) => item.flow === flow.id)} tryAgain={tried.tryAgain}
                onDeleted={undo.onDeleted} onOpen={() => onOpen(flow.id)} />
            ))}
          </ul>
        )}
      </Screen>
      {undo.notice}
    </div>
  )
}

function Chore({ flow, title, following: { runs, follow, attach, forget }, reload, stopped, tryAgain, onOpen, onDeleted }) {
  const { id, app } = flow
  const run = runs[id]
  const running = run?.status === 'running'
  const [starting, setStarting] = useState(false)
  const [problem, setProblem] = useState('')
  const [setting, setSetting] = useState(false) // the form of the daily time is open
  const dailyButton = useRef(null)
  useEffect(() => { if (running) setProblem('') }, [running]) // it runs after all: what went wrong asking no longer matters

  const appName = app ? appLabel(app) : 'No app chosen'
  const chip = chipFor(app || title)
  const paused = running && Object.values(run.nodes).includes('paused')
  const last = lastRunWords(flow.last_run)
  const line = !running ? last : paused
    ? { words: PAUSED_WORDS, tone: 'warn', icon: 'pause' }
    : { words: 'Running now', tone: 'info', icon: 'spinner' }
  const wrong = !running && (problem || runNoteWords(run, appName))
  // a chore that stopped is tried again, not run: what it is waiting for is the person's Try again
  const again = Boolean(stopped) && !stopped.rejected_by_person.length
  const why = !running && blockedWords(again && flow.blocked?.why === 'question' ? null : flow.blocked, app && appName)
  const label = running ? 'Stop' : starting ? 'Starting…' : why ? 'Cannot run yet' : again ? 'Try again' : 'Run now'
  const unavailable = starting || (running && !run.armed) || Boolean(why)

  async function press() {
    if (unavailable) return
    setProblem('')
    if (again && !running) { tryAgain(stopped); return }
    try {
      if (running) { // one mouse and keyboard: this ends every run at once
        await api(`/api/runs/${run.runId}/stop`, { method: 'POST' })
        return
      }
      setStarting(true) // drawn before a second press arrives, so the server is asked once
      forget(id)
      const { run_id } = await api(`/api/flows/${encode(id)}/run`, { method: 'POST', body: { app, context: {} } })
      follow(id, run_id)
    } catch (e) {
      if (running && e.status === 409) return // it had just ended
      setProblem(e.message)
      // the answer may be all that was lost, or it runs already: show it, with its Stop button, or what is true by now
      attach().then(reload)
    } finally {
      setStarting(false)
    }
  }

  const { daily } = flow
  const closeDaily = (changed) => {
    setSetting(false)
    if (changed) reload()
    setTimeout(() => dailyButton.current?.focus(), 0) // the form is gone: the focus goes back to the button that opened it
  }

  return (
    <li className="chore" data-testid={`chore-${id}`}>
      <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
      <div className="chore-words">
        {/* the button covers the whole row, under the row's other controls */}
        <h2><button className="chore-open" data-testid={`open-chore-${id}`} onClick={onOpen}>{title}</button></h2>
        <p className="muted">{appName}</p>
        <p className={`chore-line tone-${line.tone}`} role="status"><Icon name={line.icon} size={18} /> {line.words}{again && !running && '. See above.'}</p>
        {why && <p className="chore-line tone-warn" id={`why-${id}`} data-testid={`chore-why-${id}`}><Icon name="alert" size={18} /> {why}</p>}
        {wrong && <p className="chore-line tone-bad" role="alert"><Icon name="alert" size={18} /> {wrong}</p>}
      </div>
      {/* one button that changes its words, so the keyboard focus stays on it; aria-disabled keeps it focusable */}
      <button className={`chore-run ${running ? 'danger' : why ? 'cannot' : 'primary'}`} data-testid={`run-now-${id}`} onClick={press}
        aria-disabled={unavailable || undefined} aria-describedby={why ? `why-${id}` : undefined} aria-label={`${label}: ${title}`}>
        <Icon name={running ? 'stop' : again && !why ? 'retry' : 'play'} size={20} /> {label}
      </button>
      <button ref={dailyButton} className="chore-daily" data-testid={`daily-${id}`} onClick={() => setSetting(!setting)}
        aria-expanded={setting} aria-label={`${daily ? `Every day at ${daily}. Change or stop` : 'Run every day'}: ${title}`}>
        <Icon name="clock" size={20} />
        {daily ? <span>Every day at <b>{daily}</b><small>Change or stop</small></span> : 'Run every day'}
      </button>
      <More flow={flow} title={title} reload={reload} onDeleted={onDeleted} />
      {setting && <DailyForm at={daily} suffix={`-${id}`} submit={(at) => changeDaily(id, at)} onDone={closeDaily} />}
    </li>
  )
}
