import { useEffect, useState } from 'react'
import { api } from './api.js'
import Screen from './Screen.jsx'
import { useAction, useLoad } from './useLoad.js'
import { doubtWords, reasonWords } from './words.js'

const MAX_NOTE = 500
// what is half typed stays while the person looks at another screen
const kept = () => { try { return JSON.parse(sessionStorage.getItem('wf-notes')) ?? {} } catch { return {} } }
const EMPTY = { open: 'No open questions. Nothing is waiting for you.', answered: 'No answered questions yet.', dismissed: 'No dismissed questions.' }

export default function Queue() {
  const [status, setStatus] = useState('open')
  const load = useLoad(`/api/doubts?status=${status}`)
  const { act, busy, said } = useAction(load.reload, load.setError)
  const [notes, setNotes] = useState(kept)
  useEffect(() => { sessionStorage.setItem('wf-notes', JSON.stringify(notes)) }, [notes])
  const post = (doubt, action, body, done) => act(() => api(`/api/doubts/${doubt.id}/${action}`, { method: 'POST', body }), done)

  return (
    <Screen title="Tutor queue" help="Questions left by flows that stopped. A flow with an open question does not run again until you close it."
      load={load} said={said} isEmpty={load.data.length === 0} emptyId="no-doubts" empty={EMPTY[status]}
      tools={(
        <label className="field-inline">Show
          <select data-testid="doubt-filter" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="open">Open</option>
            <option value="answered">Answered</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </label>
      )}>
      <ul className="cards">
        {load.data.map((doubt) => (
          <li key={doubt.id} data-testid={`doubt-${doubt.id}`}>
            <div className="card-body">
              <div><b>{doubt.flow_id}</b> stopped at the step <b>{doubt.step}</b></div>
              <div>{reasonWords(doubt.reason)}</div>
              <small>On screen then: {doubtWords(doubt.capture)} (only kinds and counts are kept, never text)</small>
              {doubt.note ? <div>Your answer: {doubt.note}</div> : null}
            </div>
            {doubt.status === 'open' && (
              <form className="answer" onSubmit={(e) => {
                e.preventDefault()
                post(doubt, 'answer', { note: notes[doubt.id].trim() }, 'Answer saved. You can run the flow again; if nothing changed in the app, it stops in the same place.')
              }}>
                <label htmlFor={`note-${doubt.id}`}>What should the tutor know?</label>
                <textarea id={`note-${doubt.id}`} data-testid={`note-${doubt.id}`} maxLength={MAX_NOTE} rows={2}
                  value={notes[doubt.id] ?? ''} onChange={(e) => setNotes({ ...notes, [doubt.id]: e.target.value })} />
                <div className="answer-actions">
                  <small>{(notes[doubt.id] ?? '').length} / {MAX_NOTE}</small>
                  <button type="button" className="small" disabled={busy} data-testid={`dismiss-${doubt.id}`}
                    onClick={() => {
                      if (window.confirm(`Dismiss the question about '${doubt.step}' without answering it? The flow can run again.`)) {
                        post(doubt, 'dismiss', {}, 'Question dismissed.')
                      }
                    }}>
                    Dismiss
                  </button>
                  <button type="submit" className="primary small" disabled={busy || !(notes[doubt.id] ?? '').trim()} data-testid={`answer-${doubt.id}`}>
                    Save answer
                  </button>
                </div>
              </form>
            )}
          </li>
        ))}
      </ul>
    </Screen>
  )
}
