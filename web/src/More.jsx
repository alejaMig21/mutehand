import { useEffect, useRef, useState } from 'react'
import { api, encode } from './api.js'
import { historyWords } from './history.js'
import { Icon } from './icons.jsx'

// What a chore row offers besides Run: rename it, read its past runs, delete it. Deleting is undone from the notice that
// `useDeleted` keeps on Home, so nothing here asks "are you sure".
export default function More({ flow, title, reload, onDeleted }) {
  const { id } = flow
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('menu') // menu | rename | history
  const [problem, setProblem] = useState('')
  const [busy, setBusy] = useState(false)
  const toggle = useRef(null)
  const renameButton = useRef(null)

  function close() {
    setOpen(false)
    setMode('menu')
    setProblem('')
    toggle.current?.focus()
  }

  async function remove() {
    if (busy) return
    setBusy(true)
    setProblem('')
    try {
      const gone = await api(`/api/flows/${encode(id)}`, { method: 'DELETE' })
      onDeleted(gone)
      reload()
    } catch (e) {
      setProblem(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button className="chore-more" data-testid={`more-${id}`} ref={toggle} aria-expanded={open} aria-controls={`more-panel-${id}`}
        aria-label={`More: ${title}`} onClick={() => (open ? close() : setOpen(true))}>
        More
      </button>
      {open && (
        <div className="more-panel" id={`more-panel-${id}`} data-testid={`more-panel-${id}`}
          onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); close() } }}>
          <div className="more-actions">
            <button data-testid={`more-rename-${id}`} ref={renameButton} aria-label={`Rename ${title}`}
              onClick={() => { setProblem(''); setMode('rename') }}>Rename</button>
            <button data-testid={`more-history-${id}`} aria-expanded={mode === 'history'} aria-label={`History of ${title}`}
              onClick={() => { setProblem(''); setMode(mode === 'history' ? 'menu' : 'history') }}>History</button>
            <button className="quiet-danger" data-testid={`more-delete-${id}`} aria-label={`Delete ${title}`} onClick={remove}>
              <Icon name="trash" size={18} /> Delete
            </button>
          </div>
          {mode === 'rename' && (
            <Rename id={id} title={title} reload={reload}
              done={() => close()} cancel={() => { setMode('menu'); renameButton.current?.focus() }} />
          )}
          {mode === 'history' && <History id={id} />}
          {problem && <p className="chore-line tone-bad" role="alert"><Icon name="alert" size={18} /> {problem}</p>}
        </div>
      )}
    </>
  )
}

function Rename({ id, title, reload, done, cancel }) {
  const [text, setText] = useState(title)
  const [problem, setProblem] = useState('')
  const [saving, setSaving] = useState(false)
  const field = useRef(null)
  useEffect(() => { field.current?.focus(); field.current?.select() }, [])

  async function save(e) {
    e.preventDefault()
    if (saving) return
    setSaving(true)
    setProblem('')
    try {
      await api(`/api/flows/${encode(id)}/rename`, { method: 'POST', body: { title: text } })
      reload()
      done()
    } catch (err) {
      setProblem(err.message)
      setSaving(false)
    }
  }

  return (
    <form className="more-rename" onSubmit={save}
      onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); cancel() } }}>
      <label htmlFor={`rename-${id}`}>New name</label>
      <input id={`rename-${id}`} data-testid={`rename-input-${id}`} ref={field} value={text} maxLength={100}
        aria-invalid={problem ? true : undefined} onChange={(e) => setText(e.target.value)} />
      <button className="primary" type="submit" data-testid={`rename-save-${id}`} aria-disabled={saving || undefined}>Save name</button>
      <button type="button" onClick={cancel}>Cancel</button>
      {problem && <p className="chore-line tone-bad" role="alert"><Icon name="alert" size={18} /> {problem}</p>}
    </form>
  )
}

// The runs of one flow, newest first. The server keeps the name each box had when it ran.
function History({ id }) {
  const [state, setState] = useState({ runs: null, error: '' })
  useEffect(() => {
    let ignore = false
    api(`/api/history?flow=${encode(id)}`)
      .then((runs) => { if (!ignore) setState({ runs: historyWords(runs), error: '' }) })
      .catch((e) => { if (!ignore) setState({ runs: null, error: e.message }) })
    return () => { ignore = true }
  }, [id])

  const { runs, error } = state
  return (
    <section className="more-history" data-testid={`history-${id}`} aria-label="History">
      {error ? <p className="tone-bad" role="alert">The history could not be read. {error}</p>
        : runs === null ? <p role="status">Loading…</p>
          : runs.length === 0 ? <p className="muted">It has not run yet.</p>
            : (
              <ol>
                {runs.map((run) => (
                  <li key={run.id} data-testid={`history-run-${run.id}`}>
                    <h3>{run.title}</h3>
                    <ul>
                      {run.boxes.map((box, i) => <li key={i} className={`tone-${box.tone}`}>{box.words}</li>)}
                    </ul>
                  </li>
                ))}
              </ol>
            )}
    </section>
  )
}

// The notice after a delete, with Undo. Kept until it is dismissed, another flow is deleted or Home is left: there is no
// timer to race a keyboard or screen reader user. `flows` is Home's list, to give the focus back to the restored row.
export function useDeleted(reload, flows) {
  const [deleted, setDeleted] = useState(null) // {id, title, daily_runs} or, once undone, {back: true, lost}
  const [problem, setProblem] = useState('')
  const [busy, setBusy] = useState(false)
  const undo = useRef(null)
  const restored = useRef(null)

  useEffect(() => { if (deleted && !deleted.back) undo.current?.focus() }, [deleted])
  useEffect(() => {
    if (restored.current && flows.some((flow) => flow.id === restored.current)) {
      document.querySelector(`[data-testid="open-chore-${restored.current}"]`)?.focus()
      restored.current = null
    }
  }, [flows])

  async function restore() {
    if (busy) return
    setBusy(true)
    setProblem('')
    try {
      const back = await api(`/api/flows/${encode(deleted.id)}/restore`, { method: 'POST' })
      restored.current = deleted.id
      reload()
      if (back.daily_run_lost) setDeleted({ ...deleted, back: true, lost: back.daily_run_lost.length })
      else setDeleted(null)
    } catch (e) {
      setProblem(e.message)
    } finally {
      setBusy(false)
    }
  }

  const sum = deleted && (deleted.back
    ? `“${deleted.title}” is back, but its daily run could not be set again.`
    : `“${deleted.title}” was deleted${deleted.daily_runs ? ', and its daily run stopped' : ''}.`)
  const notice = deleted && (
    <div className="undo-notice" data-testid="deleted-notice" role="status">
      <span>{sum}{problem && <span className="tone-bad" role="alert"> {problem}</span>}</span>
      {!deleted.back && <button className="primary" data-testid="undo-delete" ref={undo} onClick={restore} aria-disabled={busy || undefined}>Undo</button>}
      <button data-testid="dismiss-deleted" onClick={() => setDeleted(null)}>Dismiss</button>
    </div>
  )
  return { notice, onDeleted: (gone) => { setProblem(''); setDeleted(gone) } }
}
