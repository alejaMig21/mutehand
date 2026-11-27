import { useState } from 'react'
import { Icon } from './icons.jsx'

// A message the person sends to the tutor in a chat, with a button that copies it. The editor only shows the words:
// nothing starts here. `message` must never hold screen content of a private app.
// `onCopy` runs first, to keep what the message was made from (a note the person added) before it leaves.
export default function ChatMessage({ message, intro = 'Send this message in a chat with Claude Code, opened in this project’s folder:', onCopy }) {
  const [outcome, setOutcome] = useState({}) // what was said about copying belongs to the words that were copied

  async function copy() {
    try {
      await onCopy?.()
      await navigator.clipboard.writeText(message)
      setOutcome({ message, words: 'Copied. Paste it in the chat.' })
    } catch {
      setOutcome({ message, words: 'Could not copy. Select the message and copy it yourself.' })
    }
  }

  return (
    <div className="chat-message" data-testid="chat-message">
      <p>{intro}</p>
      <p className="chat-text" data-testid="chat-text">{message}</p>
      <button type="button" onClick={copy}><Icon name="copy" /> Copy this message</button>
      <p className="chat-outcome" role="status">{outcome.message === message && outcome.words}</p>
    </div>
  )
}
