import { api } from './api.js'
import { appLabel } from './catalog.js'
import Screen from './Screen.jsx'
import { useAction, useLoad } from './useLoad.js'

const VERBS = { click: 'Click', select: 'Select', type_value: 'Type into', type_secret: 'Type a password into', read_value: 'Read', paste_text: 'Paste into',
  press_keys: 'Send keys to', drag: 'Drag' }

// There is deliberately no "grant" here: a consent is given by the person while the tutor teaches.
export default function Consents() {
  const load = useLoad('/api/consents')
  const { act, busy, said } = useAction(load.reload, load.setError)
  const phrase = (c) => `${VERBS[c.action] ?? c.action} “${c.control}” in ${appLabel(c.app)}`

  return (
    <Screen title="Consents" help="Sensitive actions you allowed. You can take a permission back at any time; a new one is only given while teaching."
      load={load} said={said} isEmpty={load.data.length === 0} emptyId="no-consents" empty="No permissions given.">
      <ul className="cards">
        {load.data.map((consent) => (
          <li key={`${consent.app}/${consent.control}/${consent.action}`} data-testid="consent" className="row-card">
            <div className="card-body"><b>{phrase(consent)}</b></div>
            <button className="small" disabled={busy} data-testid={`revoke-${consent.control}`} aria-label={`Revoke: ${phrase(consent)}`}
              onClick={() => {
                if (window.confirm(`Revoke the permission to ${phrase(consent)}? Steps that need it will stop until you give it again while teaching.`)) {
                  act(() => api('/api/consents', { method: 'DELETE', body: consent }), 'Permission revoked.')
                }
              }}>
              Revoke
            </button>
          </li>
        ))}
      </ul>
    </Screen>
  )
}
