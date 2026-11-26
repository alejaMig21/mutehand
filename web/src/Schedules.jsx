import { useState } from 'react'
import { api } from './api.js'
import { act, useLoad } from './useLoad.js'

// The schedules this product made in Windows Task Scheduler. Nothing else is listed and nothing else can be removed here.
export default function Schedules() {
  const { data: schedules, error, reload, setError } = useLoad('/api/schedules')
  const { data: flows } = useLoad('/api/flows')
  const [flow, setFlow] = useState('')
  const [app, setApp] = useState('mspaint.exe')
  const [at, setAt] = useState('09:00')
  const chosen = flow || flows[0]?.id || ''

  return (
    <section className="schedules">
      <h1>Schedules</h1>
      <p>
        A schedule runs a flow every day at a time, with no window of ours open. Windows runs it while you are signed in, and it starts the
        flow's daily triggers. Only schedules made here are shown.
      </p>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}

      <form className="schedule-form" onSubmit={(e) => {
        e.preventDefault()
        act(() => api('/api/schedules', { method: 'POST', body: { flow: chosen, app, at } }), reload, setError)
      }}>
        <label>Flow
          <select data-testid="schedule-flow" value={chosen} onChange={(e) => setFlow(e.target.value)}>
            {flows.map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
          </select>
        </label>
        <label>App to run on
          <input data-testid="schedule-app" value={app} onChange={(e) => setApp(e.target.value)} />
        </label>
        <label>Every day at
          <input type="time" data-testid="schedule-time" value={at} onChange={(e) => setAt(e.target.value)} required />
        </label>
        <button className="primary" type="submit" data-testid="schedule-add" disabled={!chosen}>Add schedule</button>
      </form>

      {schedules.length === 0 && <p data-testid="no-schedules">No schedules yet.</p>}
      <ul className="schedule-list">
        {schedules.map((s) => (
          <li key={s.name} data-testid={`schedule-row-${s.name}`}>
            <b>{s.flow ?? s.name}</b> · {s.app ?? 'unknown app'} · every day at {s.at ?? '?'}{' '}
            <button className="ghost small" data-testid={`schedule-remove-${s.name}`} aria-label={`Remove the schedule ${s.name}`}
              onClick={() => act(() => api('/api/schedules', { method: 'DELETE', body: { name: s.name } }), reload, setError)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
