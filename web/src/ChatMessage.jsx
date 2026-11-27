import { useRef, useState } from 'react'
import { Icon } from './icons.jsx'

// A message the person sends to the tutor in a chat, with a button that copies it. The editor only shows the words:
// nothing starts here. `message` must never hold screen content of a private app.
// `onCopy` runs first, to keep what the message was made from (a note the person added) before it leaves.
export default function ChatMessage({ message, intro = 'Copy this message and paste it in your assistant chat:', onCopy }) {
  const [outcome, setOutcome] = useState({}) // what was said about copying belongs to the words that were copied
  const text = useRef(null)

  async function copy() {
    try {
      await onCopy?.()
      await navigator.clipboard.writeText(message)
      setOutcome({ message, copied: true, words: 'Copied. Paste it in the chat.' })
    } catch { // the browser refuses: the message is selected for the person, who copies it by hand
      window.getSelection()?.selectAllChildren(text.current)
      setOutcome({ message, words: 'Could not copy by itself. The message is selected: press Ctrl+C, then paste it in the chat.' })
    }
  }

  const copied = outcome.message === message && outcome.copied
  return (
    <div className="chat-message" data-testid="chat-message">
      <p>{intro}</p>
      <p className="chat-text" data-testid="chat-text" ref={text}>{message}</p>
      <button type="button" className={copied ? 'copied' : undefined} onClick={copy}>
        {copied ? <><Icon name="check" /> Copied</> : <><Icon name="copy" /> Copy this message</>}
      </button>
      <p className="chat-outcome" role="status">{outcome.message === message && outcome.words}</p>
    </div>
  )
}
