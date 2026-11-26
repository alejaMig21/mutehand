import { Fragment } from 'react'
import { api, encode } from './api.js'
import { appLabel } from './catalog.js'
import Screen from './Screen.jsx'
import { useAction, useLoad } from './useLoad.js'
import { stateWords, whyWords } from './words.js'

const TONES = { trusted: 'ok', suspect: 'warn', to_revalidate: 'warn', rejected: 'bad' }
const MEANING = [
  ['suspect', 'It can run. It is not trusted yet: it has not worked enough times, or it writes or selects, which leaves nothing to compare.'],
  ['trusted', 'It can run. It has worked several times and never failed.'],
  ['rejected', 'The apprentice knows it but will not run it, until you press Restore.'],
  ['to_revalidate', 'The app changed version. It will not run until it is taught again.'],
]

export default function Library() {
  const load = useLoad('/api/library')
  const { act, busy, said } = useAction(load.reload, load.setError)
  const steps = load.data
  const apps = [...new Set(steps.map((step) => step.app))].sort((a, b) => appLabel(a).localeCompare(appLabel(b)))
  const mark = (step, action, done) =>
    act(() => api(`/api/steps/${encode(step.app)}/${encode(step.name)}/${action}`, { method: 'POST', body: {} }), done)

  return (
    <Screen title="Steps" help="A step is one action the apprentice learned in an app. Its state says whether it may run."
      load={load} said={said} isEmpty={steps.length === 0} emptyId="no-steps"
      empty="No steps yet. An agent teaches them in a chat; they show up here.">
      <div className="state-help" data-testid="state-help">
        <dl>
          {MEANING.map(([state, words]) => (
            <div key={state}>
              <dt><span className={`badge tone-${TONES[state]}`}>{stateWords(state)}</span></dt>
              <dd>{words}</dd>
            </div>
          ))}
        </dl>
        <p className="muted">How a step gets rejected: when it was learned, the apprentice noted what changed on screen. Each run
          compares. A step with little history is rejected by a single run that changes something else. You can also reject it yourself.</p>
      </div>
      {apps.map((app) => (
        <section key={app} className="group" aria-label={appLabel(app)}>
          <h2>{appLabel(app)}</h2>
          <div className="table-scroll">
            <table>
              <colgroup><col /><col className="col-state" /><col className="col-number" /><col className="col-number" /><col className="col-action" /></colgroup>
              <thead>
                <tr><th>Step</th><th>State</th><th>Worked</th><th>Failed</th><th><span className="sr-only">Action</span></th></tr>
              </thead>
              <tbody>
                {steps.filter((step) => step.app === app).map((step) => (
                  <Fragment key={step.name}>
                  <tr data-testid={`step-row-${step.name}`} className={step.state === 'rejected' ? 'blocked' : undefined}>
                    <td>
                      {step.name}
                      <small>{[step.origin === 'factory' && 'Came with the app (factory)', step.sensitive && 'Needs your permission'].filter(Boolean).join(' · ')}</small>
                    </td>
                    <td><span className={`badge tone-${TONES[step.state] ?? 'muted'}`} data-testid={`state-${step.name}`}>{stateWords(step.state)}</span></td>
                    <td>{step.successes}</td>
                    <td>{step.failures}</td>
                    <td className="cell-action">
                      {step.state === 'rejected' ? (
                        <button className="primary small" disabled={busy} data-testid={`restore-${step.name}`} aria-label={`Restore ${step.name}`}
                          onClick={() => mark(step, 'restore', `'${step.name}' is restored: it is on trial and can run again.`)}>
                          Restore
                        </button>
                      ) : (
                        <button className="small" disabled={busy} data-testid={`reject-${step.name}`} aria-label={`Reject ${step.name}`}
                          onClick={() => mark(step, 'reject', `'${step.name}' is rejected. It will not run until you restore it.`)}>
                          Reject
                        </button>
                      )}
                    </td>
                  </tr>
                  {step.state === 'rejected' && (
                    <tr className="why">
                      <td colSpan={5} data-testid={`why-${step.name}`}>
                        <b>Why:</b> {whyWords(step.why)}
                        <small>The editor will not start a flow that uses this step. Restore lets it run again and sets its counts to
                          zero. Restore does not fix the step: if the same thing happens, it is rejected again. Teaching it again does
                          not unblock it; only Restore does.</small>
                      </td>
                    </tr>
                  )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      <details className="muted">
        <summary>The exact rule</summary>
        <p>The score is (worked + 1) / (worked + 3 × failed + 2). Below 0.30 a step is rejected. It is trusted from 0.80 with at
          least two successes on this computer and no failures.</p>
      </details>
    </Screen>
  )
}
