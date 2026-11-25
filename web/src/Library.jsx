import { api } from './api.js'
import { act, useLoad } from './useLoad.js'

export default function Library() {
  const { data: steps, error, reload, setError } = useLoad('/api/library')
  const apps = [...new Set(steps.map((step) => step.app))]

  return (
    <section>
      <h1>Steps</h1>
      <p>Confidence is (successes + 1) / (successes + 3 x failures + 2). A step is trusted from 0.80 with two successes of its own and no failures.</p>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}
      {apps.map((app) => (
        <div key={app}>
          <h2>{app}</h2>
          <table>
            <thead>
              <tr><th>Step</th><th>Origin</th><th>State</th><th>Successes</th><th>Failures</th><th>Confidence</th><th>Action</th></tr>
            </thead>
            <tbody>
              {steps.filter((step) => step.app === app).map((step) => (
                <tr key={step.name} data-testid={`step-row-${step.name}`}>
                  <td>{step.name}{step.sensitive ? ' (needs consent)' : ''}</td>
                  <td>{step.origin}</td>
                  <td data-testid={`state-${step.name}`}>{step.state}</td>
                  <td>{step.successes}</td>
                  <td>{step.failures}</td>
                  <td>{step.confidence}</td>
                  <td>
                    {step.state === 'rejected' ? (
                      <button data-testid={`restore-${step.name}`} aria-label={`Restore ${step.name}`} onClick={() =>
                        act(() => api(`/api/steps/${step.app}/${step.name}/restore`, { method: 'POST', body: {} }), reload, setError)}>
                        Restore
                      </button>
                    ) : (
                      <button data-testid={`reject-${step.name}`} aria-label={`Reject ${step.name}`} onClick={() =>
                        act(() => api(`/api/steps/${step.app}/${step.name}/reject`, { method: 'POST', body: {} }), reload, setError)}>
                        Reject
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  )
}
