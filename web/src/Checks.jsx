import { useEffect } from 'react'
import { api } from './api.js'
import { Icon } from './icons.jsx'
import { useLoad } from './useLoad.js'

// What the product needs, in plain words. It reads only: it installs nothing, and every missing piece says how to fix it.
export default function Checks() {
  const { data, error } = useLoad('/api/checks')
  const checks = data.checks ?? []

  useEffect(() => { api('/api/checks/seen', { method: 'POST' }).catch(() => {}) }, []) // shown once: it is not the first run any more

  const missing = checks.filter((c) => !c.ok && !c.optional)
  return (
    <section className="checks">
      <h1>Is everything ready?</h1>
      <p data-testid="checks-summary">
        {checks.length === 0 ? 'Checking…' : missing.length === 0 ? 'Everything you need is here.' : `${missing.length} thing${missing.length === 1 ? '' : 's'} to fix before this works.`}
      </p>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}
      <ul className="check-list">
        {checks.map((c) => (
          <li key={c.id} data-testid={`check-${c.id}`} className={c.ok ? 'tone-ok' : c.optional ? 'tone-warn' : 'tone-bad'}>
            <span className="check-state">
              <Icon name={c.ok ? 'checkcircle' : c.optional ? 'half' : 'xcircle'} size={18} />{' '}
              {c.ok ? 'Ready' : c.optional ? 'Optional' : 'Missing'}
            </span>
            <div>
              <b>{c.title}</b>
              <div className="muted">{c.why}</div>
              {c.fix && <div className="check-fix">To fix: {c.fix}</div>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
