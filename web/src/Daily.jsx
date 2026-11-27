import { useEffect, useRef, useState } from 'react'
import { api, encode } from './api.js'

// Set, or with null stop, the daily time of a stored chore. The server keeps the Windows task and the first box in step.
export const changeDaily = (flowId, at) => api(`/api/flows/${encode(flowId)}/daily`,
  at ? { method: 'PUT', body: { at } } : { method: 'DELETE' })

// The form that sets, changes and stops a daily time, the same on Home and on the first box. `submit(at)` makes the change
// (at is null to stop) and throws the reason in words when it cannot; `onDone` closes the form, with whether it changed (and the time it was set to, null when stopped)
// anything. `initial` is the time to offer when there is none yet. `suffix` makes the test ids of one row's form unique.
export function DailyForm({ at, initial, suffix = '', submit, onDone }) {
  const [time, setTime] = useState(at || initial || '09:00')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')
  const field = useRef(null)
  useEffect(() => { field.current?.focus() }, [])

  async function send(value) {
    if (busy) return
    setBusy(true)
    setProblem('')
    try {
      await submit(value)
      onDone(true, value)
    } catch (e) {
      setProblem(e.message)
      setBusy(false)
    }
  }

  return (
    <form className="daily-form" onSubmit={(e) => { e.preventDefault(); if (time) send(time) }}
      onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onDone(false) } }}>
      <label>Time of day <input ref={field} type="time" required value={time} data-testid={`daily-time${suffix}`}
        onChange={(e) => setTime(e.target.value)} /></label>
      <button type="submit" className="primary" data-testid={`daily-set${suffix}`} aria-disabled={busy || undefined}>
        {at ? 'Change the time' : 'Run every day'}
      </button>
      {at && <button type="button" className="danger" data-testid={`daily-stop${suffix}`} aria-disabled={busy || undefined}
        onClick={() => send(null)}>Stop the daily run</button>}
      <button type="button" className="ghost" data-testid={`daily-cancel${suffix}`} onClick={() => onDone(false)}>Cancel</button>
      {problem && <p className="daily-problem" role="alert">{problem}</p>}
    </form>
  )
}
