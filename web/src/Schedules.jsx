import { useEffect, useState } from 'react'
import { api, encode } from './api.js'
import { appLabel, guessApp } from './catalog.js'
import Screen from './Screen.jsx'
import { useAction, useLoad } from './useLoad.js'

// The schedules this product made in Windows Task Scheduler. Nothing else is listed and nothing else can be removed here.
export default function Schedules() {
  const load = useLoad('/api/schedules')
  const { act, busy, said } = useAction(load.reload, load.setError)
  const { data: flows } = useLoad('/api/flows')
  const { data: steps } = useLoad('/api/steps')
  const [flow, setFlow] = useState('') // chosen on purpose: a stray click must not make the computer act every day
  const [typed, setApp] = useState(null)
  const [guessed, setGuessed] = useState('')
  const [at, setAt] = useState('09:00')
  const apps = [...new Set(steps.map((step) => step.app))]
  const app = typed ?? guessed
  useEffect(() => { // the program is the one the chosen flow's steps belong to
    setGuessed('')
    if (!flow) return undefined
    let ignore = false
    api(`/api/flows/${encode(flow)}`)
      .then((stored) => { if (!ignore) setGuessed(guessApp(stored.nodes.map((n) => n.step).filter(Boolean), steps) ?? '') })
      .catch(() => {}) // the person can still type it
    return () => { ignore = true }
  }, [flow, steps])

  function add(event) {
    event.preventDefault()
    const same = load.data.find((s) => s.flow === flow && s.at === at)
    if (same && !window.confirm(`'${flow}' is already scheduled at ${at} on ${same.app}. Replace it?`)) return
    act(() => api('/api/schedules', { method: 'POST', body: { flow, app, at } }), `'${flow}' will run every day at ${at}.`)
  }

  const form = (
    <form className="schedule-form" onSubmit={add}>
      <label>Flow
        <select data-testid="schedule-flow" value={flow} onChange={(e) => { setFlow(e.target.value); setApp(null) }}>
          <option value="">{flows.length ? 'Choose a flow…' : 'Save a flow first'}</option>
          {flows.map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
        </select>
      </label>
      <label>App to run on
        <input data-testid="schedule-app" list="schedule-apps" value={app} onChange={(e) => setApp(e.target.value)} required />
        <datalist id="schedule-apps">{apps.map((a) => <option key={a} value={a}>{appLabel(a)}</option>)}</datalist>
      </label>
      <label>Every day at
        <input type="time" data-testid="schedule-time" value={at} onChange={(e) => setAt(e.target.value)} required />
      </label>
      <button className="primary" type="submit" data-testid="schedule-add" disabled={busy || !flow || !app}>Add schedule</button>
    </form>
  )

  return (
    <Screen title="Schedules"
      help="Run a flow every day at a time, with no window of ours open. Windows runs it while you are signed in. Only schedules made here are listed."
      load={load} said={said} above={form} isEmpty={load.data.length === 0} emptyId="no-schedules" empty="No schedules yet.">
      <ul className="cards">
        {load.data.map((s) => (
          <li key={s.name} data-testid={`schedule-row-${s.name}`} className="row-card">
            <div className="card-body">
              <b>{s.flow ?? s.name}</b>
              <small>every day at {s.at ?? '?'} · {s.app ?? 'unknown app'}</small>
            </div>
            <button className="small" disabled={busy} data-testid={`schedule-remove-${s.name}`} aria-label={`Remove the schedule ${s.name}`}
              onClick={() => {
                if (window.confirm(`Remove the daily run of '${s.flow ?? s.name}' at ${s.at}?`)) {
                  act(() => api('/api/schedules', { method: 'DELETE', body: { name: s.name } }), 'Schedule removed.')
                }
              }}>
              Remove
            </button>
          </li>
        ))}
      </ul>
    </Screen>
  )
}
