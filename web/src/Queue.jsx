import { useState } from 'react'
import { api } from './api.js'
import { act, useLoad } from './useLoad.js'

export default function Queue() {
  const [status, setStatus] = useState('open')
  const { data: doubts, error, reload, setError } = useLoad(`/api/doubts?status=${status}`)
  const [notes, setNotes] = useState({})

  return (
    <section>
      <h1>Tutor queue</h1>
      <p>Where the apprentice stopped and why. The capture only has roles and counts, never text.</p>
      <label>
        Show{' '}
        <select data-testid="doubt-filter" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option>open</option>
          <option>answered</option>
          <option>dismissed</option>
        </select>
      </label>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}
      {doubts.length === 0 && <p data-testid="no-doubts">Nothing here.</p>}
      <ul>
        {doubts.map((doubt) => (
          <li key={doubt.id} data-testid={`doubt-${doubt.id}`}>
            Flow <b>{doubt.flow_id}</b>, node {doubt.node_id} (lesson {doubt.lesson}): <b>{doubt.reason}</b>
            {' '}· screen: {Object.entries(doubt.capture).map(([role, count]) => `${count} ${role}`).join(', ') || 'nothing'}
            {doubt.note ? ` · answer: ${doubt.note}` : ''}
            {doubt.status === 'open' && (
              <>
                {' '}
                <input aria-label={`Note for doubt ${doubt.id}`} data-testid={`note-${doubt.id}`} maxLength={500}
                  value={notes[doubt.id] ?? ''} onChange={(e) => setNotes({ ...notes, [doubt.id]: e.target.value })} />
                <button data-testid={`answer-${doubt.id}`} aria-label={`Record answer for doubt ${doubt.id}`} onClick={() =>
                  act(() => api(`/api/doubts/${doubt.id}/answer`, { method: 'POST', body: { note: notes[doubt.id] ?? '' } }), reload, setError)}>
                  Record answer
                </button>
                <button data-testid={`dismiss-${doubt.id}`} aria-label={`Dismiss doubt ${doubt.id}`} onClick={() =>
                  act(() => api(`/api/doubts/${doubt.id}/dismiss`, { method: 'POST', body: {} }), reload, setError)}>
                  Dismiss
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
