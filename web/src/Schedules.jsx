import { useState } from 'react'
import { api } from './api.js'
import AppSelect from './AppSelect.jsx'
import { appLabel, taughtApp } from './catalog.js'
import Screen from './Screen.jsx'
import { useAction, useLoad } from './useLoad.js'
import { flowTitle } from './words.js'

const named = (app) => (app ? appLabel(app) : 'unknown app')

// The schedules this product made in Windows Task Scheduler. Nothing else is listed and nothing else can be removed here.
export default function Schedules() {
  const load = useLoad('/api/schedules')
  const { act, busy, said } = useAction(load.reload, load.setError)
  const { data: flows } = useLoad('/api/flows')
  const { data: steps } = useLoad('/api/steps')
  const [flow, setFlow] = useState('') // chosen on purpose: a stray click must not make the computer act every day
  const [typed, setApp] = useState(null)
  const [at, setAt] = useState('09:00')
  const apps = [...new Set(steps.map((step) => step.app))]
  const app = typed ?? taughtApp(flows.find((f) => f.id === flow)?.app ?? '', apps) // the one the flow remembers

  function add(event) {
    event.preventDefault()
    const called = flowTitle(flow, flows)
    const same = load.data.find((s) => s.flow === flow && s.at === at)
    if (same && !window.confirm(`'${called}' is already scheduled at ${at} on ${named(same.app)}. Replace it?`)) return
    act(() => api('/api/schedules', { method: 'POST', body: { flow, app, at } }), `'${called}' will run every day at ${at}.`)
  }

  const form = (
    <form className="schedule-form" onSubmit={add}>
      <label>Flow
        <select data-testid="schedule-flow" value={flow} onChange={(e) => { setFlow(e.target.value); setApp(null) }}>
          <option value="">{flows.length ? 'Choose a flow…' : 'Save a flow first'}</option>
          {flows.map((f) => <option key={f.id} value={f.id}>{flowTitle(f.id, flows)}</option>)}
        </select>
      </label>
      <label>App to run on
        <AppSelect data-testid="schedule-app" apps={apps} value={app} onChange={setApp} required />
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
        {load.data.map((s) => {
          const called = s.flow ? flowTitle(s.flow, flows) : s.name
          return (
            <li key={s.name} data-testid={`schedule-row-${s.name}`} className="row-card">
              <div className="card-body">
                <b>{called}</b>
                <small>every day at {s.at ?? '?'} · {named(s.app)}</small>
              </div>
              <button className="small" disabled={busy} data-testid={`schedule-remove-${s.name}`}
                aria-label={`Remove the daily run of ${called} at ${s.at ?? '?'}`}
                onClick={() => {
                  if (window.confirm(`Remove the daily run of '${called}' at ${s.at}?`)) {
                    act(() => api('/api/schedules', { method: 'DELETE', body: { name: s.name } }), 'Schedule removed.')
                  }
                }}>
                Remove
              </button>
            </li>
          )
        })}
      </ul>
    </Screen>
  )
}
