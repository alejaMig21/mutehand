import { useCallback, useEffect, useRef, useState } from 'react'
import { api, encode } from './api.js'
import { appLabel } from './catalog.js'
import ChatMessage from './ChatMessage.jsx'
import { Icon } from './icons.jsx'
import { helpMessage, stoppedWords, triedResult } from './stopped.js'

// Trying again, shared by Home and the flow screen so that a try started on one is reported on both. `tries` holds, by
// chore, what was tried and, once the run ends, how it went. `ensure` runs first on the flow screen: what is stored
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
      const { run_id } = await api(`/api/flows/${encode(item.flow)}/try-again`, { method: 'POST', body: { app: item.app, context: {} } })
      setTries((all) => ({ ...all, [item.flow]: { before: item, runId: run_id, result: null } }))
      follow(item.flow, run_id)
    } catch (e) {
      fail(e)
    } finally {
      going.current.delete(item.flow)
    }
  }, [follow, forget])

  // a try that ended is told how it went: the chore is read again, to see whether it stopped again and where
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
  return { tries, tryAgain, hide }
}

// How a try went, above whatever else the screen shows. Only a finished answer is shown.
export function TriedResults({ tries, hide }) {
  const done = Object.entries(tries).filter(([, tried]) => tried.result)
  if (done.length === 0) return null
  return (
    <div className="tried-results">
      {done.map(([flow, { result }]) => (
        <section key={flow} className={`tried tried-${result.tone}`} role="status" data-testid={`tried-${flow}`}>
          <Icon name={result.tone === 'ok' ? 'checkcircle' : 'alert'} size={28} />
          <div>
            <h2>{result.title}</h2>
            {result.detail && <p>{result.detail}</p>}
          </div>
          <button data-testid={`tried-hide-${flow}`} onClick={() => hide(flow)}>Hide</button>
        </section>
      ))}
    </div>
  )
}

// "Try again" and "Ask for help" for a stopped chore. A step the person rejected is not lifted by trying again: it is
// allowed again first. `prefix` and `suffix` keep the test ids of the card and of the strip apart.
export function StoppedActions({ item, onTry, onChanged, trying, prefix, suffix = '' }) {
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState(item.note ?? '')
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
    .then(onChanged, (e) => setProblem(e.message))

  useEffect(() => { if (asking) help.current?.querySelector('textarea')?.focus() }, [asking])

  return (
    <>
      <div className="stopped-actions">
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
            <textarea value={note} maxLength={500} rows={2} data-testid={`${prefix}-note${suffix}`} onChange={(e) => setNote(e.target.value)} />
          </label>
          <ChatMessage message={helpMessage(item, appLabel(item.app || 'the app'), note)} onCopy={keepNote} />
        </div>
      )}
    </>
  )
}

// The things that need the person, first on Home. Absent when there are none.
export function Attention({ items, tries, tryAgain, onChanged, running }) {
  if (items.length === 0) return null
  return (
    <section className="attention" aria-labelledby="attention-title" data-testid="attention">
      <h2 id="attention-title">Needs your attention ({items.length})</h2>
      <ul>
        {items.map((item) => {
          const says = stoppedWords(item)
          return (
            <li key={item.flow} className="attention-card" data-testid={`attention-${item.flow}`}>
              <Icon name="alert" size={28} />
              <div className="attention-words">
                <h3>{says.title}</h3>
                <p>{says.detail}</p>
                <p className="muted">{says.hint}</p>
              </div>
              <div className="attention-buttons">
                <StoppedActions item={item} prefix="attention" suffix={`-${item.flow}`} onChanged={onChanged}
                  trying={running(item.flow) || Boolean(tries[item.flow] && !tries[item.flow].result)}
                  onTry={tryAgain} />
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
