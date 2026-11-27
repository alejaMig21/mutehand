import { useEffect } from 'react'
import ChatMessage from './ChatMessage.jsx'
import { Icon } from './icons.jsx'
import { useLoad } from './useLoad.js'

export const FIRST_DAY_TITLE = 'Show it a computer flow once. Then it does the flow for you.'
const STAGES = [
  ['Teach', 'Show it the flow once, in the chat.'],
  ['Choose the steps', 'Pick what it learned, one step after another.'],
  ['Let it repeat', 'Press Run now, or choose a time for every day.'],
]

// The message that starts teaching, for Home and Apps while nothing is learned.
export function TeachFirst() {
  return (
    <section aria-labelledby="teach-heading" className="first-day-teach">
      <h2 id="teach-heading">Teach it your first flow</h2>
      <ChatMessage message="I want to teach you a flow: [what you want done, and in which program]" />
    </section>
  )
}

// What Home shows with no flow: the message that starts teaching and the three stages, while nothing is learned,
// or the way to the first flow once something is. Nothing here starts a lesson: the message is for a chat.
export default function FirstDay({ onNew, onFirstDay }) {
  const learned = useLoad('/api/steps')
  const { reload, loading, loadError, data } = learned
  useEffect(() => { // the tutor may have taught something in a chat since
    window.addEventListener('focus', reload)
    return () => window.removeEventListener('focus', reload)
  }, [reload])
  const nothing = !loading && !loadError && data.length === 0
  useEffect(() => onFirstDay(nothing), [nothing]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loadError) {
    return <div className="error" role="alert" data-testid="load-error"><span>This could not be loaded. {loadError}</span>
      <button data-testid="retry" onClick={reload}>Try again</button></div>
  }
  if (loading) return <p className="empty-state" role="status">Loading…</p>
  if (!nothing) {
    return (
      <div className="empty-state" data-testid="no-flows">
        <p>No flows yet. Build your first one from what it has learned.</p>
        <button className="primary" data-testid="new-flow" onClick={onNew}><Icon name="plus" size={20} /> New flow</button>
      </div>
    )
  }
  return (
    <div className="first-day" data-testid="first-day">
      <TeachFirst />
      <section aria-labelledby="stages-heading">
        <h2 id="stages-heading" className="stages-heading">How it works</h2>
        <ol className="stages" data-testid="stages">
          {STAGES.map(([name, words], i) => (
            <li key={name}><span className="stage-no" aria-hidden="true">{i + 1}</span><b>{name}</b><span className="muted">{words}</span></li>
          ))}
        </ol>
      </section>
    </div>
  )
}
