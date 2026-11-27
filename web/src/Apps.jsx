import { Fragment, useEffect, useRef, useState } from 'react'
import { api, encode } from './api.js'
import { noteWords, permissionWords, stopsWords, takeBackWords, teachMessage } from './apps.js'
import { relearnMessage } from './stopped.js'
import { appKey, appLabel, chipFor } from './catalog.js'
import ChatMessage from './ChatMessage.jsx'
import { TeachFirst } from './FirstDay.jsx'
import { Icon } from './icons.jsx'
import Screen from './Screen.jsx'
import { useLoad } from './useLoad.js'
import { whyWords } from './words.js'

const PAGE = 14 // rows shown before "Show more"
const PROBLEMS = ['rejected', 'to_revalidate']
const MAX_SEARCH = 200 // a pasted wall of text must never become a request the server refuses

// The programs the apprentice knows: a search across all of them, one row each, and one opened above the rows with its
// actions (problems first), what it may do without asking, and the message to teach it another.
export default function Apps() {
  const [typed, setTyped] = useState('')
  const [query, setQuery] = useState('')
  const [shown, setShown] = useState(PAGE)
  const [open, setOpen] = useState(null)
  const [said, setSaid] = useState('')
  const back = useRef(null) // the row an opened app was opened from: the focus returns to it
  const load = useLoad(`/api/apps${query ? `?q=${encodeURIComponent(query)}` : ''}`, { keep: true })
  const needs = useLoad('/api/attention', { keep: true })
  const { reload } = load
  const reloadNeeds = needs.reload
  const stopped = (app) => needs.data.filter((item) => item.kind === 'stopped' && item.app && appKey(item.app) === appKey(app)).length
  // a chore stopped on a program comes before the rest (the server knows only the actions that need the person)
  const rows = [...load.data].sort((a, b) => !stopped(a.app) - !stopped(b.app))

  useEffect(() => { // a lesson in a chat, or a run, may have changed what is true
    const again = () => { reload(); reloadNeeds() }
    window.addEventListener('focus', again)
    return () => window.removeEventListener('focus', again)
  }, [reload, reloadNeeds])

  useEffect(() => {
    if (open === null && back.current) {
      document.querySelector(`[data-testid="app-row-${back.current}"]`)?.focus()
      back.current = null
    }
  }, [open])

  const search = (event) => { event.preventDefault(); setQuery(typed.trim().slice(0, MAX_SEARCH)); setShown(PAGE); setOpen(null) }
  const choose = (app) => { back.current = app; setSaid(''); setOpen(open === app ? null : app) }
  const changed = (words) => { setSaid(words); reload(); reloadNeeds() }

  return (
    <div className="home apps">
      <Screen title="Programs it knows" load={load} said={said} isEmpty={load.data.length === 0}
        emptyId={query ? 'apps-none' : 'apps-empty'}
        empty={query ? `No program or action matches “${query}”.` : <><p>It has not learned any program yet.</p><TeachFirst /></>}
        above={(
          <form className="apps-search" role="search" onSubmit={search}>
            <label htmlFor="apps-search">What do you want to do?</label>
            <div>
              <input id="apps-search" data-testid="apps-search" type="search" value={typed} maxLength={MAX_SEARCH} placeholder="for example: save a spreadsheet"
                onChange={(e) => setTyped(e.target.value)} />
              <button type="submit" data-testid="apps-search-go"><Icon name="search" size={20} /> Search</button>
            </div>
          </form>
        )}>
        <ul className="apps-grid">
          {rows.slice(0, shown).map((row) => {
            const note = noteWords(row, stopped(row.app))
            const chip = chipFor(row.app)
            return (
              <Fragment key={row.app}>
              <li>
                <button className="app-row" data-testid={`app-row-${row.app}`} aria-expanded={open === row.app} onClick={() => choose(row.app)}>
                  <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
                  <span className="app-words">
                    <b>{appLabel(row.app)}</b>
                    <span className="muted">{row.actions} {row.actions === 1 ? 'action' : 'actions'}{row.permissions > 0 && ` · ${row.permissions} ${row.permissions === 1 ? 'permission' : 'permissions'}`}</span>
                    {row.found?.length > 0 && <span className="app-found">{row.found.join(' · ')}</span>}
                  </span>
                  {note && <span className={`app-note tone-${note.tone}`}>{note.words}</span>}
                  <Icon name="chevron" size={20} />
                </button>
              </li>
              {/* the card opens under its row: what is above it, and the row itself, stay where they are */}
              {open === row.app && <li className="app-card-slot"><AppCard app={open} onClose={() => choose(open)} onChanged={changed} /></li>}
              </Fragment>
            )
          })}
        </ul>
        {rows.length > shown && (
          <p className="apps-more">
            <button data-testid="apps-show-more" onClick={() => setShown(shown + PAGE)}>Show {rows.length - shown} more programs</button>
          </p>
        )}
      </Screen>
    </div>
  )
}

function AppCard({ app, onClose, onChanged }) {
  const load = useLoad(`/api/apps/${encode(app)}`, { keep: true })
  const detail = load.data
  const heading = useRef(null)
  const name = appLabel(app)
  const chip = chipFor(app)
  const [allowed, setAllowed] = useState({}) // action -> what was said when it was allowed again: it stays where it was pressed
  useEffect(() => {
    heading.current?.focus({ preventScroll: true })
    heading.current?.scrollIntoView({ block: 'nearest' }) // moves the page only when the card is not in view
  }, [])

  const ready = !load.loading && !load.loadError && detail.actions
  const hidden = ready && detail.private
  const problems = ready ? detail.actions.filter((action) => PROBLEMS.includes(action.state)) : []
  const fine = ready ? detail.actions.filter((action) => !PROBLEMS.includes(action.state)) : []
  const rejected = problems.filter((action) => action.state === 'rejected')
  const relearn = problems.filter((action) => action.state === 'to_revalidate')
  const slots = [...rejected.map((action) => action.name), ...Object.keys(allowed).filter((one) => !rejected.some((action) => action.name === one))]
  const done = (words) => { load.reload(); onChanged(words) }

  return (
    <section className="app-card" data-testid={`app-card-${app}`} aria-labelledby="app-card-title">
      <header>
        <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
        <div className="app-words">
          <h2 id="app-card-title" tabIndex={-1} ref={heading}>{name}</h2>
          {ready && <span className="muted">{detail.actions.length} {detail.actions.length === 1 ? 'action' : 'actions'}</span>}
        </div>
        <button data-testid="app-close" onClick={onClose}>Close <Icon name="chevronup" size={20} /></button>
      </header>
      {load.loadError && (
        <div className="error" role="alert"><span>This program could not be read. {load.loadError}</span>
          <button onClick={load.reload}>Try again</button></div>
      )}
      {relearn.length > 0 && <Relearn actions={relearn} name={name} hidden={hidden} />}
      {slots.map((one) => (allowed[one]
        ? <p key={one} className="app-problem app-allowed" role="status" data-testid={`app-allowed-${one}`}><Icon name="checkcircle" size={24} /> {allowed[one]}</p>
        : <Problem key={one} action={rejected.find((action) => action.name === one)} name={name} hidden={hidden}
          onChanged={(words) => { setAllowed((all) => ({ ...all, [one]: words })); done(words) }} />))}
      {hidden
        ? <p className="muted">{fine.length + problems.length} actions. Their names stay private.</p>
        : fine.length > 0 && (
          <ul className="app-actions">
            {fine.map((action) => <li key={action.name} data-testid={`app-action-${action.name}`}>{action.name}</li>)}
          </ul>
        )}
      {ready && (
        <div className="app-permissions">
          <h3>Allowed without asking</h3>
          {detail.permissions.length > 0 ? (
            <ul>
              {detail.permissions.map((permission) => (
                <Permission key={`${permission.control}/${permission.action}`} permission={permission} hidden={hidden} onChanged={done} />
              ))}
            </ul>
          ) : <p className="muted" data-testid="app-no-permissions">You have not given it any permission.</p>}
        </div>
      )}
      {ready && <Teach name={name} />}
    </section>
  )
}

// Every action that has to be learned again, with one message for the app: the tutor finds which ones.
function Relearn({ actions, name, hidden }) {
  const [message, setMessage] = useState(false)
  const many = actions.length
  return (
    <div className="app-problem" data-testid="app-relearn">
      <Icon name="alert" size={24} />
      <p>
        <b>{many === 1 ? '1 action has' : `${many} actions have`}</b> to be learned again.
        {!hidden && ` ${actions.map((action) => `“${action.name}”`).join(', ')}`}
      </p>
      <button data-testid="app-message-relearn" aria-expanded={message} onClick={() => setMessage(!message)}
        aria-label={`${message ? 'Hide the message' : 'Show me what to send'}: ${name}`}>
        <Icon name="chat" size={20} /> {message ? 'Hide the message' : 'Show me what to send'}
      </button>
      {message && <div className="help-panel"><ChatMessage message={relearnMessage(name)} /></div>}
    </div>
  )
}

function Problem({ action, name, hidden, onChanged }) {
  const [problem, setProblem] = useState('')
  const [busy, setBusy] = useState(false)
  const title = hidden ? 'An action' : `“${action.name}”`

  async function allow() {
    if (busy) return
    setBusy(true)
    setProblem('')
    try {
      await api(`/api/steps/${encode(action.app)}/${encode(action.name)}/restore`, { method: 'POST' })
      onChanged(`${title} is allowed again.`)
    } catch (e) {
      setProblem(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-problem" data-testid={`app-problem-${action.name}`}>
      <Icon name="alert" size={24} />
      <p><b>{title}</b> is rejected. {hidden && action.why?.kind !== 'person' ? '' : whyWords(action.why)}</p>
      <button className="primary" data-testid={`app-allow-again-${action.name}`} aria-disabled={busy || undefined}
        aria-label={`Allow again: ${hidden ? name : action.name}`} onClick={allow}>Allow again</button>
      {problem && <p className="stopped-problem" role="alert">{problem}</p>}
    </div>
  )
}

function Permission({ permission, hidden, onChanged }) {
  const [asking, setAsking] = useState(false)
  const [problem, setProblem] = useState('')
  const [busy, setBusy] = useState(false)
  const keep = useRef(null)
  const phrase = permissionWords(permission, hidden)
  const id = `${permission.control}-${permission.action}`
  useEffect(() => { if (asking) keep.current?.focus() }, [asking]) // the safe answer has the focus

  async function takeBack() {
    if (busy) return
    setBusy(true)
    setProblem('')
    try {
      const { app, control, action } = permission
      await api('/api/consents', { method: 'DELETE', body: { app, control, action } })
      onChanged(`Permission taken back: ${phrase}. ${stopsWords(permission, hidden)}`)
    } catch (e) {
      setProblem(e.message)
      setBusy(false)
    }
  }

  return (
    <li data-testid={`app-permission-${id}`}>
      <span>{phrase}</span>
      <button data-testid={`app-take-back-${id}`} aria-expanded={asking} aria-label={`Take back: ${phrase}`} onClick={() => setAsking(!asking)}>Take back</button>
      {problem && <p className="stopped-problem" role="alert">{problem}</p>}
      {asking && (
        <div className="take-back-ask" data-testid="take-back-ask" role="group" aria-label={`Take back: ${phrase}`}>
          <p>{takeBackWords(permission, hidden)}</p>
          <button className="primary" data-testid="take-back-yes" aria-disabled={busy || undefined} onClick={takeBack}>Take it back</button>
          <button data-testid="take-back-no" ref={keep} onClick={() => setAsking(false)}>Keep it</button>
        </div>
      )}
    </li>
  )
}

function Teach({ name }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="app-teach">
      <button data-testid="app-teach" aria-expanded={shown} onClick={() => setShown(!shown)}>
        <Icon name="plus" size={20} /> Teach another {name} action
      </button>
      {shown && <div className="help-panel"><ChatMessage message={teachMessage(name)} /></div>}
    </div>
  )
}
