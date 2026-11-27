import { useCallback, useEffect, useRef, useState } from 'react'
import { api, encode } from './api.js'
import { appLabel } from './catalog.js'
import ChatMessage from './ChatMessage.jsx'
import { Icon } from './icons.jsx'
import { helpMessage, rejectedWords, relearnWords, stoppedWords, titles, triedResult } from './stopped.js'

// Trying again, shared by Home and the flow screen so that a try started on one is reported on both. `tries` holds, by
// flow, what was tried and, once the run ends, how it went. `ensure` runs first on the flow screen: what is stored
// must be what is on screen.
export function useTryAgain({ runs, follow, forget }) {
  const [tries, setTries] = useState({})
  const going = useRef(new Set())
  const asked = useRef(new Set())

  const tryAgain = useCallback(async (item, ensure) => {
    if (going.current.has(item.flow)) return
    going.current.add(item.flow)
    const fail = (e) => setTries((all) => ({ ...all, [item.flow]: { before: item, result: {
      tone: 'bad', title: `“${item.title}” was not tried again.`, detail: e.message } } }))
    try {
      if (ensure) await ensure()
      forget(item.flow)
      const { run_id } = await api(`/api/flows/${encode(item.flow)}/try-again`, { method: 'POST', body: { context: {} } })
      setTries((all) => ({ ...all, [item.flow]: { before: item, runId: run_id, result: null } }))
      follow(item.flow, run_id)
    } catch (e) {
      fail(e)
    } finally {
      going.current.delete(item.flow)
    }
  }, [follow, forget])

  // a try that ended is told how it went: the flow is read again, to see whether it stopped again and where
  useEffect(() => {
    for (const [flow, tried] of Object.entries(tries)) {
      const run = runs[flow]
      if (!tried.runId || tried.result || run?.runId !== tried.runId || run.status === 'running' || asked.current.has(tried.runId)) continue
      asked.current.add(tried.runId)
      api('/api/attention').then((list) => list.find((item) => item.flow === flow) ?? null).catch(() => null)
        .then((after) => setTries((all) => (all[flow]?.runId === tried.runId
          ? { ...all, [flow]: { ...all[flow], result: triedResult(tried.before, run, after) } } : all)))
    }
  }, [runs, tries])

  const hide = useCallback((flow) => setTries(({ [flow]: _gone, ...rest }) => rest), [])
  // a new run is about to answer: what an earlier try said must not stay above it
  const clearDone = useCallback(() => setTries((all) => Object.fromEntries(Object.entries(all).filter(([, tried]) => !tried.result))), [])
  return { tries, tryAgain, hide, clearDone }
}

// How a try went, above whatever else the screen shows. Only a finished answer is shown.
export function TriedResults({ tries, hide }) {
  const done = Object.entries(tries).filter(([, tried]) => tried.result)
  if (done.length === 0) return null
  return (
    <div className="tried-results">
      {done.map(([flow, { result }]) => <Tried key={flow} flow={flow} result={result} hide={hide} />)}
    </div>
  )
}

// One try's answer. Without `hide` it is still going: there is nothing to hide yet.
function Tried({ flow, result, hide }) {
  return (
    <section className={`tried tried-${result.tone}`} role="status" data-testid={`tried-${flow}`}>
      <Icon name={result.tone === 'ok' ? 'checkcircle' : result.tone === 'info' ? 'spinner' : 'alert'} size={28} />
      <div>
        <h2>{result.title}</h2>
        {result.detail && <p>{result.detail}</p>}
      </div>
      {hide && <button data-testid={`tried-hide-${flow}`} onClick={() => hide(flow)}>Hide</button>}
    </section>
  )
}

// What is half typed in a note stays while the person looks at another screen or reloads, until it is kept on the doubt.
const NOTES = 'wf-notes'
const typed = (doubt) => { try { return JSON.parse(sessionStorage.getItem(NOTES))?.[doubt] } catch { return undefined } }
const keepTyped = (doubt, note) => {
  try {
    const all = JSON.parse(sessionStorage.getItem(NOTES)) ?? {}
    if (note) all[doubt] = note
    else delete all[doubt]
    sessionStorage.setItem(NOTES, JSON.stringify(all))
  } catch { /* the note simply is not remembered */ }
}

// "Try again" and "Ask for help" for a stopped flow. A step the person rejected is not lifted by trying again: it is
// allowed again first. `prefix` and `suffix` keep the test ids of the card and of the strip apart.
export function StoppedActions({ item, onTry, onChanged, trying, prefix, suffix = '' }) {
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState(() => typed(item.doubt) ?? item.note ?? '')
  const write = (text) => { setNote(text); keepTyped(item.doubt, text === (item.note ?? '') ? '' : text) }
  const [problem, setProblem] = useState('')
  const [allowing, setAllowing] = useState(false)
  const help = useRef(null)
  const blocked = item.rejected_by_person.length > 0

  async function allow() {
    if (allowing) return
    setAllowing(true)
    setProblem('')
    try {
      for (const { app, step } of item.rejected_by_person) await api(`/api/steps/${encode(app)}/${encode(step)}/restore`, { method: 'POST' })
      onChanged()
    } catch (e) {
      setProblem(e.message)
    } finally {
      setAllowing(false)
    }
  }

  // what the person wrote stays on the doubt, which stays open; the tutor reads it there
  const keepNote = () => api(`/api/doubts/${item.doubt}/help`, { method: 'POST', body: { note } })
    .then(() => { keepTyped(item.doubt, ''); onChanged() }, (e) => setProblem(e.message))

  useEffect(() => { if (asking) help.current?.querySelector('textarea')?.focus() }, [asking])

  return (
    <>
      <div className="stopped-buttons">
        {blocked
          ? <button className="primary" data-testid={`${prefix}-allow-again${suffix}`} aria-disabled={allowing || undefined} onClick={allow}>Allow again</button>
          : (
            <button className="primary" data-testid={`${prefix}-try-again${suffix}`} aria-disabled={trying || undefined}
              aria-label={`Try again: ${item.title}`} onClick={() => !trying && onTry(item)}>
              <Icon name="retry" size={20} /> Try again
            </button>
          )}
        <button data-testid={`${prefix}-ask-help${suffix}`} aria-expanded={asking} aria-label={`Ask for help: ${item.title}`}
          onClick={() => setAsking(!asking)}>
          <Icon name="chat" size={20} /> Ask for help
        </button>
      </div>
      {problem && <p className="stopped-problem" role="alert">{problem}</p>}
      {asking && (
        <div className="help-panel" ref={help} data-testid={`${prefix}-help${suffix}`}>
          <label>
            Add a note for whoever helps, if you like
            <textarea value={note} maxLength={500} rows={2} data-testid={`${prefix}-note${suffix}`} onChange={(e) => write(e.target.value)} />
          </label>
          <ChatMessage message={helpMessage(item, appLabel(item.app || 'the app'), note)} onCopy={keepNote} />
        </div>
      )}
    </>
  )
}

function Card({ id, title, detail, hint, children, below, done }) {
  return (
    <li className={`attention-card${done ? ' attention-done' : ''}`} data-testid={`attention-${id}`}>
      <Icon name={done ? 'checkcircle' : 'alert'} size={28} />
      <div className="attention-words">
        <h3>{title}</h3>
        <p role={done ? 'status' : undefined}>{detail}</p>
        {hint && <p className="muted">{hint}</p>}
      </div>
      {children && <div className="attention-buttons">{children}</div>}
      {below}
    </li>
  )
}

// The message to send is folded behind a button: the card stays short.
function Relearn({ item }) {
  const says = relearnWords(item)
  const [shown, setShown] = useState(false)
  return (
    <Card id={`relearn-${item.app}`} title={says.title} detail={says.detail}
      below={shown && <div className="help-panel"><ChatMessage message={says.message} /></div>}>
      <button data-testid={`attention-message-relearn-${item.app}`} aria-expanded={shown} onClick={() => setShown(!shown)}>
        <Icon name="chat" size={20} /> {shown ? 'Hide the message' : 'Show the message to send'}
      </button>
    </Card>
  )
}

function Rejected({ item, onAllowed }) {
  const says = rejectedWords(item)
  const [problem, setProblem] = useState('')
  const [allowing, setAllowing] = useState(false)
  const id = `${item.app}-${item.step}`
  async function allow() {
    if (allowing) return
    setAllowing(true)
    setProblem('')
    try {
      await api(`/api/steps/${encode(item.app)}/${encode(item.step)}/restore`, { method: 'POST' })
      onAllowed(item.private ? `A step in ${appLabel(item.app)} is allowed again.` : `“${item.step}” is allowed again.`)
    } catch (e) {
      setProblem(e.message)
      setAllowing(false)
    }
  }
  return (
    <Card id={`rejected-${id}`} title={says.title} detail={says.detail}>
      <button className="primary" data-testid={`attention-allow-again-${id}`} aria-disabled={allowing || undefined}
        aria-label={`Allow again: ${item.private ? appLabel(item.app) : item.step}`} onClick={allow}>Allow again</button>
      {problem && <p className="stopped-problem" role="alert">{problem}</p>}
    </Card>
  )
}

function Setup({ item }) {
  return <Card id={`setup-${item.id}`} title={`${item.title}: missing`} detail={item.why} hint={`To fix: ${item.fix}`} />
}

// Told once, after an upgrade starts the person's data again: where the earlier data was kept.
function Notice({ item, onDismissed }) {
  const [problem, setProblem] = useState('')
  const dismiss = () => api(`/api/notices/${encode(item.id)}/dismiss`, { method: 'POST' }).then(onDismissed, (e) => setProblem(e.message))
  return (
    <Card id={`notice-${item.id}`} title="A fresh start"
      detail={`This version starts with no Steps and no Flows. Everything you had before was kept in a copy: ${item.copy}`}
      hint="Nothing was moved into the new data. Keep that file if you want to look at the old one later.">
      <button className="primary" data-testid={`attention-notice-dismiss-${item.id}`} onClick={dismiss}>Got it</button>
      {problem && <p className="stopped-problem" role="alert">{problem}</p>}
    </Card>
  )
}

const rejectedKey =(item) => `rejected-${item.app}-${item.step}`

// The things that need the person, first on Home. Absent when there are none. A rejected step that was just allowed again
// stays where it was, saying so, until the person dismisses it: the list below does not jump up under the next press.
//
// A try again answers the same way: its answer stands in the card, or where the card was once the flow no longer needs
// the person, until it is hidden. `tries` and `hide` are the ones `useTryAgain` gives.
export function Attention({ items, tries, hide, tryAgain, onChanged, running }) {
  const [kept, setKept] = useState({}) // key -> {item, at, words}
  const placed = useRef({}) // flow -> where its card was when Try again was pressed
  const list = items.map((item) => ({ item }))
  for (const [key, one] of Object.entries(kept)) {
    if (!items.some((item) => item.kind === 'rejected' && rejectedKey(item) === key)) list.splice(Math.min(one.at, list.length), 0, { key, ...one })
  }
  for (const [flow, tried] of Object.entries(tries)) {
    if (!items.some((item) => item.kind === 'stopped' && item.flow === flow)) list.splice(Math.min(placed.current[flow] ?? 0, list.length), 0, { flow, tried })
  }
  if (list.length === 0) return null
  const allowed = (item, at) => (words) => { setKept((all) => ({ ...all, [rejectedKey(item)]: { item, at, words } })); onChanged() }
  return (
    <section className="attention" aria-labelledby="attention-title" data-testid="attention">
      <h2 id="attention-title">{items.length ? `Needs your attention (${items.length})` : 'Done'}</h2>
      <ul>
        {list.map(({ item, key, words, flow, tried }, at) => {
          if (flow) {
            return <li key={`tried-${flow}`}><Tried flow={flow} hide={tried.result ? hide : undefined}
              result={tried.result ?? { tone: 'info', title: `Trying “${tried.before.title}” again…` }} /></li>
          }
          if (key) {
            return (
              <Card key={key} id={key} done title={words} detail={`${titles(item.flows)} can run now.`}>
                <button autoFocus onClick={() => setKept(({ [key]: _gone, ...rest }) => rest)}>OK</button>
              </Card>
            )
          }
          if (item.kind === 'notice') return <Notice key={`notice-${item.id}`} item={item} onDismissed={onChanged} />
          if (item.kind === 'relearn') return <Relearn key={`relearn-${item.app}`} item={item} />
          if (item.kind === 'rejected') return <Rejected key={rejectedKey(item)} item={item} onAllowed={allowed(item, at)} />
          if (item.kind === 'setup') return <Setup key={`setup-${item.id}`} item={item} />
          const says = stoppedWords(item)
          return (
            <Card key={item.flow} id={item.flow} title={says.title} detail={says.detail} hint={says.hint}
              below={tries[item.flow]?.result && <Tried flow={item.flow} result={tries[item.flow].result} hide={hide} />}>
              <StoppedActions item={item} prefix="attention" suffix={`-${item.flow}`} onChanged={onChanged}
                trying={running(item.flow) || Boolean(tries[item.flow] && !tries[item.flow].result)}
                onTry={(one) => { placed.current[one.flow] = at; tryAgain(one) }} />
            </Card>
          )
        })}
      </ul>
    </section>
  )
}
