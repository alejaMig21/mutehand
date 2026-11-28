// What the Apps screen says. Pure, so node can test it. Nothing here names a control or a step of a private app: the
// callers say `hidden` for those, and the words stay general.

const VERBS = {
  click: 'Press', select: 'Select', type_value: 'Type into', type_secret: 'Type a password into', read_value: 'Read',
  paste_text: 'Paste into', press_keys: 'Send keys to', drag: 'Drag',
}
const quoted = (names) => names.map((name) => `“${name}”`).join(', ')
const many = (n, one, other) => `${n} ${n === 1 ? one : other}`

// The note on an app's row, or null when nothing there needs the person. `stopped` counts the flows stopped on that app.
export function noteWords(row, stopped) {
  if (stopped) return { words: `${stopped} stopped`, tone: 'bad' }
  return row.problems ? { words: `${row.problems} ${row.problems === 1 ? 'needs' : 'need'} attention`, tone: 'warn' } : null
}

// What a permission lets the apprentice do. "*" is every control of the app.
export function permissionWords({ control, action }, hidden) {
  const verb = VERBS[action] ?? action.replaceAll('_', ' ')
  if (control === '*') return `${verb} anything`
  return `${verb} ${hidden ? 'a control' : `“${control}”`}`
}

// What stops working if the person takes a permission back: the flows, then the steps, from what the server found.
export function stopsWords({ stops }, hidden) {
  const { steps, flows } = stops
  const parts = []
  if (flows.length) parts.push(`${flows.length === 1 ? 'This flow' : 'These flows'} will stop: ${quoted(flows.map((flow) => flow.title))}.`)
  if (steps.length) {
    parts.push(hidden ? `${many(steps.length, 'step', 'steps')} will not run without it.`
      : steps.length === 1 ? `The step ${quoted(steps)} will not run without it.`
        : `These steps will not run without it: ${quoted(steps)}.`)
  }
  if (!parts.length) parts.push('No flow or step needs it now.')
  return parts.join(' ')
}

export const takeBackWords = (permission, hidden) => `${stopsWords(permission, hidden)} To give it again, ask the assistant in the chat to teach it.`

// The words the person sends in a chat. Only the person starts anything with them.
export const teachMessage = (app) => `In Mutehand I want to teach another step in ${app}. `
  + `Please ask me what I want it to be able to do in ${app}, then teach it.`
