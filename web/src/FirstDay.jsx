import { useEffect } from 'react'
import ChatMessage from './ChatMessage.jsx'
import { Icon } from './icons.jsx'
import { useLoad } from './useLoad.js'

export const FIRST_DAY_TITLE = 'Show it a computer chore once. Then it does the chore for you.'
const STAGES = [
  ['Teach', 'Once, in the chat.'],
  ['Put in order', 'Pick the actions; they join up by themselves.'],
  ['Let it repeat', 'Press Run, or choose a time for every day.'],
]

// What Home shows with no chore: the message that starts teaching and the three stages, while nothing is learned,
// or the way to the first chore once something is. Nothing here starts a lesson: the message is for a chat.
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
      <div className="empty-state" data-testid="no-chores">
        <p>No chores yet. Build your first one from what it has learned.</p>
        <button className="primary" data-testid="new-chore" onClick={onNew}><Icon name="plus" size={20} /> New chore</button>
      </div>
    )
  }
  return (
    <div className="first-day" data-testid="first-day">
      <section aria-labelledby="teach-heading" className="first-day-teach">
        <h2 id="teach-heading">Teach it your first chore</h2>
        <ChatMessage message="I want to teach you a chore: [what you want done, and in which program]"
          intro="Open Claude Code in the Workflow Factory folder and send this:" />
      </section>
      <ol className="stages" data-testid="stages">
        {STAGES.map(([name, words], i) => <li key={name}><b>{i + 1}. {name}</b><span className="muted">{words}</span></li>)}
      </ol>
    </div>
  )
}
