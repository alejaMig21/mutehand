import { useEffect, useRef } from 'react'

// What every list screen shares: a title with one line of help, what just happened, what went wrong, and an honest
// loading, failed or empty state.
export default function Screen({ title, help, load, said, empty, emptyId, isEmpty, children, tools, above }) {
  const announcement = useRef(null)
  // the row that had the focus may be gone: then the focus goes to what happened, without moving the page
  useEffect(() => {
    if (said && document.activeElement === document.body) announcement.current?.focus({ preventScroll: true })
  }, [said, load.data])

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>{title}</h1>
          {help && <p className="muted">{help}</p>}
        </div>
        {tools}
      </header>
      <p className="announce" data-testid="announce" role="status" tabIndex={-1} ref={announcement}>{said}</p>
      {load.error && <div className="error" role="alert" data-testid="error">{load.error}</div>}
      {above}
      {load.loadError ? (
        <div className="error" role="alert" data-testid="load-error">
          <span>This list could not be loaded. {load.loadError}</span>
          <button data-testid="retry" onClick={load.reload}>Try again</button>
        </div>
      ) : load.loading ? <p className="empty-state" role="status">Loading…</p>
        : isEmpty ? <p className="empty-state" data-testid={emptyId}>{empty}</p> : children}
    </section>
  )
}
