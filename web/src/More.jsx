import { useEffect, useRef, useState } from 'react'
import { api, encode } from './api.js'
import { historyWords } from './history.js'
import { Icon } from './icons.jsx'

// What a flow row offers besides Run: rename it, read its past runs, delete it. Deleting is undone from the notice that
// `useDeleted` keeps on Home, so nothing here asks "are you sure".
export default function More({ flow, title, reload, onDeleted, place }) {
  const { id } = flow
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('menu') // menu | rename | history
  const [problem, setProblem] = useState('')
  const [busy, setBusy] = useState(false)
  const [renamed, setRenamed] = useState('') // the name just kept, said where the person typed it
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
      onDeleted(gone, place)
      reload()
    } catch (e) {
      setProblem(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button className="flow-more" data-testid={`more-${id}`} ref={toggle} aria-expanded={open} aria-controls={`more-panel-${id}`}
        aria-label={`More: ${title}`} onClick={() => { setRenamed(''); if (open) close(); else setOpen(true) }}>
        More
      </button>
      {renamed && !open && (
        <p className="flow-line tone-ok" role="status" data-testid={`renamed-${id}`}><Icon name="checkcircle" size={18} /> Renamed to “{renamed}”.</p>
      )}
      {open && (
        <div className="more-panel" id={`more-panel-${id}`} data-testid={`more-panel-${id}`}
          onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); close() } }}>
          <div className="more-buttons">
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
              done={(name) => { close(); setRenamed(name) }} cancel={() => { setMode('menu'); renameButton.current?.focus() }} />
          )}
          {mode === 'history' && <History id={id} />}
          {problem && <p className="flow-line tone-bad" role="alert"><Icon name="alert" size={18} /> {problem}</p>}
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
      done(text.trim())
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
      {problem && <p className="flow-line tone-bad" role="alert"><Icon name="alert" size={18} /> {problem}</p>}
    </form>
  )
}

// The runs of one flow, newest first. The server keeps the name each node had when it ran.
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
                      {run.nodes.map((node, i) => <li key={i} className={`tone-${node.tone}`}>{node.words}</li>)}
                    </ul>
                  </li>
                ))}
              </ol>
            )}
    </section>
  )
}


// One notice per flow deleted lately, each with its own Undo, shown where the flow was. Kept until dismissed, undone or Home is left: there is no
// timer to race a keyboard or screen reader user. `flows` is Home's list, to give the focus back to the restored row.
export function useDeleted(reload, flows) {
  const [items, setItems] = useState([]) // newest first: {id, title, daily_runs, at} or, once undone with a loss, {back: true, lost}; `at` is its place in the list
  const [problems, setProblems] = useState({})
  const [busy, setBusy] = useState(false)
  const undo = useRef(null)
  const restored = useRef(null)

  useEffect(() => { // flows deleted a moment ago, before this page was loaded again, can still be undone
    api('/api/deleted').then((recent) => setItems((now) => [...now, ...recent.filter((r) => !now.some((n) => n.id === r.id)).map((r) => ({ ...r, at: 0 }))])).catch(() => {})
  }, [])
  const newest = items[0]?.back ? null : items[0]?.id
  useEffect(() => { if (newest) undo.current?.focus() }, [newest])
  useEffect(() => {
    if (restored.current && flows.some((flow) => flow.id === restored.current)) {
      document.querySelector(`[data-testid="open-flow-${restored.current}"]`)?.focus()
      restored.current = null
    }
  }, [flows])

  const drop = (id) => setItems((now) => now.filter((item) => item.id !== id))
  async function restore(item) {
    if (busy) return
    setBusy(true)
    setProblems(({ [item.id]: _, ...rest }) => rest)
    try {
      const back = await api(`/api/flows/${encode(item.id)}/restore`, { method: 'POST' })
      restored.current = item.id
      reload()
      if (back.daily_run_lost) setItems((now) => now.map((n) => (n.id === item.id ? { ...item, back: true, lost: back.daily_run_lost.length, nodeOff: back.daily_node_removed } : n)))
      else drop(item.id)
    } catch (e) {
      setProblems((now) => ({ ...now, [item.id]: e.message }))
    } finally {
      setBusy(false)
    }
  }

  const notices = items.map((item, n) => {
    const sum = item.back
      ? `“${item.title}” is back, but its daily run could not be set again${item.nodeOff ? ', so its daily start node was taken off' : ''}.`
      : `“${item.title}” was deleted${item.daily_runs ? ', and its daily run stopped' : ''}.`
    return (
      <div key={item.id} className="undo-notice" data-testid="deleted-notice" role="status">
        <span>{sum}{problems[item.id] && <span className="tone-bad" role="alert"> {problems[item.id]}</span>}</span>
        {!item.back && <button className="primary" data-testid="undo-delete" ref={n === 0 ? undo : null} onClick={() => restore(item)} aria-disabled={busy || undefined}>Undo</button>}
        <button data-testid="dismiss-deleted" onClick={() => drop(item.id)}>Dismiss</button>
      </div>
    )
  })
  return {
    notices, items,
    onDeleted: (gone, at) => { setProblems({}); setItems((now) => [{ ...gone, at }, ...now.filter((n) => n.id !== gone.id)]) },
  }
}
