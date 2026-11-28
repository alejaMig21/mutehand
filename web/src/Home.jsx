import { useEffect, useRef, useState } from 'react'
import { api, encode, loadAppNames, UNREACHABLE } from './api.js'
import { Attention } from './Attention.jsx'
import { appLabel, chipFor } from './catalog.js'
import { changeDaily, DailyForm } from './Daily.jsx'
import FirstDay, { FIRST_DAY_TITLE } from './FirstDay.jsx'
import { Icon } from './icons.jsx'
import More, { useDeleted } from './More.jsx'
import Screen from './Screen.jsx'
import { useLoad } from './useLoad.js'
import { ranResult } from './stopped.js'
import { blockedWords, flowTitle, lastRunWords, PAUSED_WORDS, runNoteWords, timeWords } from './words.js'

// The first screen: the person's flows ("flows" on screen), how each went, and Run now. `onOpen` shows a flow on the
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
    const target = flows.some((flow) => flow.id === left.current) ? `open-flow-${left.current}` : 'new-flow'
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
      <Attention items={needs.data} tries={tried.tries} hide={tried.hide} tryAgain={tried.tryAgain} onChanged={() => { reload(); reloadNeeds() }}
        running={(id) => following.runs[id]?.status === 'running'} />
      <Screen title={none && bare ? FIRST_DAY_TITLE : 'Your flows'} load={load} isEmpty={false}
        help={none && bare ? 'When you press a button, or by itself every morning.' : undefined}
        above={offline && <p role="status">{UNREACHABLE} Trying again…</p>}
        tools={!none && <button data-testid="new-flow" onClick={onNew}><Icon name="plus" size={20} /> New flow</button>}>
        {none && undo.items.length === 0 ? <FirstDay onNew={onNew} onFirstDay={setBare} /> : (
          <ul className="flows">{withNotices(
            flows.map((flow, place) => (
              <Flow key={flow.id} flow={flow} title={flowTitle(flow.id, flows)} following={following} reload={reload} place={place}
                stopped={stopped.find((item) => item.flow === flow.id)} tryAgain={tried.tryAgain} clearTried={tried.clearDone}
                onDeleted={undo.onDeleted} onOpen={() => onOpen(flow.id)} />
            )), undo)}
          </ul>
        )}
      </Screen>
    </div>
  )
}

// Each undo notice stands where its flow was, under its own key so it is the same element while the list changes around it.
const withNotices = (rows, { notices, items }) => {
  const out = [...rows]
  notices.forEach((notice, n) => out.splice(Math.min(items[n].at, out.length), 0, <li key={`undo-${items[n].id}`}>{notice}</li>))
  return out
}

function Flow({ flow, title, following: { runs, follow, attach, forget }, reload, stopped, tryAgain, clearTried, place, onOpen, onDeleted }) {
  const { id } = flow
  const technologies = flow.technologies ?? [] // the programs its step nodes act on: no flow has one program of its own
  const run = runs[id]
  const running = run?.status === 'running'
  const [starting, setStarting] = useState(false)
  const [problem, setProblem] = useState('')
  const [setting, setSetting] = useState(false) // the form of the daily time is open
  const [saved, setSaved] = useState('') // what the daily form just did, said next to its button
  const dailyButton = useRef(null)
  const whyLine = useRef(null)
  useEffect(() => { if (running) setProblem('') }, [running]) // it runs after all: what went wrong asking no longer matters

  const appName = technologies.map(appLabel).join(', ')
  const chip = chipFor(technologies[0] || title)
  const paused = running && Object.values(run.nodes).includes('paused')
  const ran = !running && !starting && !problem && ranResult(run) // a run that ended here replaces the older line at once
  const last = ran ? { ...ran, icon: 'check' } : lastRunWords(flow.last_run)
  const line = starting ? { words: 'Running now', tone: 'info', icon: 'spinner' } : !running ? last : paused
    ? { words: PAUSED_WORDS, tone: 'warn', icon: 'pause' }
    : { words: 'Running now', tone: 'info', icon: 'spinner' }
  const wrong = !running && (problem || runNoteWords(run, appName || 'the app'))
  // a flow that stopped is tried again, not run: what it is waiting for is the person's Try again
  const again = Boolean(stopped) && !stopped.rejected_by_person.length
  const why = !running && blockedWords(again && flow.blocked?.why === 'question' ? null : flow.blocked, Object.keys(flow.blocked?.by_technology ?? {}).filter(Boolean).map(appLabel).join(', '))
  const label = running ? 'Stop' : starting ? 'Running…' : why ? 'Cannot run yet' : again ? 'Try again' : 'Run now'
  const unavailable = starting || (running && !run.armed) || Boolean(why)

  async function press() {
    if (why && !running) { whyLine.current?.focus(); return } // it cannot run: the press leads to the reason
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
      clearTried()
      const { run_id } = await api(`/api/flows/${encode(id)}/run`, { method: 'POST', body: { context: {} } })
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
  const closeDaily = (changed, at) => {
    setSetting(false)
    setSaved(changed ? (at ? `Saved. It runs every day at ${timeWords(at)}.` : 'Saved. It no longer runs every day.') : '')
    if (changed) reload()
    setTimeout(() => dailyButton.current?.focus(), 0) // the form is gone: the focus goes back to the button that opened it
  }

  return (
    <li className="flow" data-testid={`flow-${id}`}>
      <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
      <div className="flow-words">
        {/* the button covers the whole row, under the row's other controls */}
        <h2><button className="flow-open" data-testid={`open-flow-${id}`} onClick={onOpen}>{title}</button></h2>
        {appName && <p className="muted">{appName}</p>}
        <p className={`flow-line tone-${line.tone}`} role="status" data-testid={ran ? `flow-result-${id}` : undefined}><Icon name={line.icon} size={18} /> {line.words}{again && !running && '. See above.'}</p>
        {why && <p className="flow-line tone-warn" id={`why-${id}`} data-testid={`flow-why-${id}`} tabIndex={-1} ref={whyLine}><Icon name="alert" size={18} /> {why}</p>}
        {wrong && <p className="flow-line tone-bad" role="alert"><Icon name="alert" size={18} /> {wrong}</p>}
      </div>
      {/* one button that changes its words, so the keyboard focus stays on it; aria-disabled keeps it focusable */}
      <button className={`flow-run ${running ? 'danger' : why ? 'cannot' : 'primary'}${starting ? ' busy' : ''}`} data-testid={`run-now-${id}`} onClick={press}
        aria-disabled={unavailable || undefined} aria-describedby={why ? `why-${id}` : undefined} aria-label={`${label}: ${title}`}>
        <Icon name={running ? 'stop' : starting ? 'spinner' : again && !why ? 'retry' : 'play'} size={20} /> {label}
      </button>
      <button ref={dailyButton} className="flow-daily" data-testid={`daily-${id}`} onClick={() => setSetting(!setting)}
        aria-expanded={setting} aria-label={`${daily ? `Every day at ${timeWords(daily)}. Change or stop` : 'Run every day'}: ${title}`}>
        <Icon name="clock" size={20} />
        {daily ? <span>Every day at <b>{timeWords(daily)}</b><small>Change or stop</small></span> : 'Run every day'}
      </button>
      {saved && !setting && <p className="flow-line tone-ok flow-note" role="status" data-testid={`daily-saved-${id}`}><Icon name="checkcircle" size={18} /> {saved}</p>}
      <More flow={flow} title={title} reload={reload} onDeleted={onDeleted} place={place} />
      {setting && <DailyForm at={daily} suffix={`-${id}`} submit={(at) => changeDaily(id, at)} onDone={closeDaily} />}
    </li>
  )
}
