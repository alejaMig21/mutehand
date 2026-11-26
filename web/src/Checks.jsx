import { useEffect } from 'react'
import { api } from './api.js'
import { Icon } from './icons.jsx'
import Screen from './Screen.jsx'
import { useLoad } from './useLoad.js'

// What the product needs, in plain words. It reads only: it installs nothing, and every missing piece says how to fix it.
export default function Checks({ onStart }) {
  const load = useLoad('/api/checks')
  const checks = load.data.checks ?? []

  useEffect(() => { api('/api/checks/seen', { method: 'POST' }).catch(() => {}) }, []) // shown once: it is not the first run any more

  const missing = checks.filter((c) => !c.ok && !c.optional)
  return (
    <Screen title="Is everything ready?" load={load}
      tools={<button className="primary" data-testid="start-building" onClick={onStart}>Start building a flow</button>}>
      <p data-testid="checks-summary">
        {missing.length === 0 ? 'Everything you need is here.' : `${missing.length} thing${missing.length === 1 ? '' : 's'} to fix before this works.`}
      </p>
      <ul className="cards check-list">
        {checks.map((c) => (
          <li key={c.id} data-testid={`check-${c.id}`}>
            <span className={`check-state tone-${c.ok ? 'ok' : c.optional ? 'warn' : 'bad'}`}>
              <Icon name={c.ok ? 'checkcircle' : c.optional ? 'half' : 'xcircle'} size={18} />{' '}
              {c.ok ? 'Ready' : c.optional ? 'Optional' : 'Missing'}
            </span>
            <div className="card-body">
              <b>{c.title}</b>
              <small>{c.why}</small>
              {c.fix && <div className="check-fix">To fix: {c.fix}</div>}
            </div>
          </li>
        ))}
      </ul>
    </Screen>
  )
}
