import { api } from './api.js'
import { act, useLoad } from './useLoad.js'

// There is deliberately no "grant" here: a consent is given by the person while the tutor teaches.
export default function Consents() {
  const { data: consents, error, reload, setError } = useLoad('/api/consents')

  return (
    <section>
      <h1>Consents</h1>
      <p>These are the sensitive actions you gave consent to. You can revoke a consent at any time; a new one is only given while teaching.</p>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}
      {consents.length === 0 && <p data-testid="no-consents">No consent granted.</p>}
      <ul>
        {consents.map((consent) => (
          <li key={`${consent.app}/${consent.control}/${consent.action}`} data-testid="consent">
            <b>{consent.app}</b> · control {consent.control} · action {consent.action}{' '}
            <button data-testid={`revoke-${consent.control}`} aria-label={`Revoke ${consent.action} on ${consent.control} in ${consent.app}`} onClick={() =>
              act(() => api('/api/consents', { method: 'DELETE', body: consent }), reload, setError)}>
              Revoke
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
