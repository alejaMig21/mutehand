// What the person reads instead of the codes the engine stores. Pure, so node can test it.

const REASONS = {
  no_consent: 'You have not given permission for this action.',
  control_not_found: 'The button or field this step uses is not on the screen.',
  unreadable: 'The control is there but cannot be read.',
  out_of_frame: 'The app window is not set up the way it was when the step was learned.',
  rejected: 'This step is rejected.',
  to_revalidate: 'The app was updated, so this step needs a re-check.',
  template_no_match: 'The picture this step looks for is not on the screen.',
  missing_input: 'A value this node needs was not there.',
  bad_data: 'A value had the wrong kind.',
  unsendable_text: 'The text has characters that cannot be typed.',
  cell_requires_paste_text: 'A table cell cannot be written this way. The step has to be learned again as a paste.',
  effect_mismatch: 'The screen did not change the way it did when the step was learned.',
  step_missing: 'There is no step with this name for the app.',
  secure_field_requires_type_secret: 'A password field can only be filled from a stored secret.',
  action_failed: 'The app refused the action.',
  wrong_window: 'Another window was in front of the app.',
  user_active: 'You kept using the mouse or keyboard.',
  precondition_not_met: 'Something the step needs was not ready.',
}
const STATES = { trusted: 'Trusted', suspect: 'On trial', rejected: 'Rejected', to_revalidate: 'Needs a re-check' }
const RUNS = { finished: 'Finished', stopped: 'Stopped', waiting: 'Waiting', emergency: 'Stopped by you', error: 'Failed', running: 'Running' }
const EFFECTS = {
  closed_dialog: 'a dialog closed', revealed: 'something new appeared', value_changed: 'a value changed',
  no_change: 'nothing changed on screen', pixels_changed: 'the picture changed',
}
const ROLES = {
  textfield: 'text field', menubutton: 'menu button', menuitem: 'menu item', combobox: 'drop-down list',
  checkbox: 'check box', radiobutton: 'option button', listitem: 'list item', treeitem: 'list item',
}
export const roleWords = (role) => ROLES[role] ?? role

const spaced = (code) => String(code).replaceAll('_', ' ')

// What a flow is called on screen; two flows with one name are told apart by their identifiers.
export function flowTitle(id, flows) {
  const flow = flows.find((f) => f.id === id)
  if (!flow) return id
  return flows.some((f) => f !== flow && f.title === flow.title) ? `${flow.title} (${id})` : flow.title
}

// A test of one node is kept apart from its flow, under "<flow>#test:<node>".
export function flowWords(id, flows) {
  const flow = id.replace(/#test:.*$/, '')
  return flow === id ? flowTitle(id, flows) : `${flowTitle(flow, flows)} (one node tested)`
}

export const reasonWords = (code) => REASONS[code] ?? `Stopped: ${spaced(code)}.`
export const stateWords = (state) => STATES[state] ?? spaced(state)
export const runWords = (status) => RUNS[status] ?? spaced(status)
export const effectWords = (effect) => EFFECTS[effect] ?? spaced(effect)

// {button: 2, textfield: 1} -> '2 buttons, 1 text field'
export const doubtWords = (capture) => Object.entries(capture)
  .map(([role, count]) => `${count} ${ROLES[role] ?? role}${count === 1 ? '' : 's'}`).join(', ') || 'nothing'

export function whenWords(iso) {
  const when = new Date(iso)
  return /^\d{4}-\d\d-\d\dT/.test(iso) && !Number.isNaN(when.getTime())
    ? when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : iso
}

const LAST_RUNS = {
  finished: ['Worked', 'ok', 'check'], stopped: ['Stopped', 'bad', 'alert'], emergency: ['You stopped it', 'warn', 'stop'],
  error: ['Failed', 'bad', 'alert'],
}

// "today at 07:00", "yesterday at 09:00", "on 3 Nov at 23:05": the day is the person's own, not the clock's in UTC.
function sinceWords(iso, now) {
  const when = new Date(iso)
  if (Number.isNaN(when.getTime())) return iso
  const days = (date) => Math.round(new Date(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000)
  const ago = days(now) - days(when)
  const year = when.getFullYear() === now.getFullYear() ? undefined : 'numeric'
  const day = ago === 0 ? 'today' : ago === 1 ? 'yesterday'
    : `on ${when.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year })}`
  return `${day} at ${when.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
}

// How a flow's last run went: {words, tone, icon}. `run` is {status, at}, or null when none is recorded.
export function lastRunWords(run, now = new Date()) {
  if (!run) return { words: 'Never run', tone: 'muted', icon: 'help' }
  const [said, tone, icon] = LAST_RUNS[run.status] ?? [runWords(run.status), 'muted', 'help']
  return { words: `${said} ${sinceWords(run.at, now)}`, tone, icon }
}

const NO_RECORD = {
  waiting: 'It did not run: it still has an open question from an earlier run.', busy: 'It is already running somewhere else.',
}

// What to say about a followed run that the history does not tell, or ''. An error is a code from the server: it is
// not repeated to the person.
export function runNoteWords(run, app) {
  if (run?.status !== 'error') return NO_RECORD[run?.status] ?? ''
  if (run.error === 'INTERNAL') return 'It failed to run because of a problem inside Workflow Factory.'
  return /^[A-Z_]+$/.test(run.error) ? `It failed to run. Check that ${app} is open, then try again.` : `The run was lost (${run.error}).`
}

const BLOCKED = {
  empty: 'It has no boxes yet. Open it to add some.', no_app: 'No app is chosen for it. Open it, choose one and press Save.',
  expression: 'It uses an expression, which cannot run yet.', unreadable: 'It cannot be read.',
  question: 'It stopped earlier and left a question. Answer it in Tutor queue.',
}

// Why the server says a flow cannot run, {why, steps}, or '' when it can.
export function blockedWords(blocked, app) {
  if (!blocked) return ''
  const { why, steps } = blocked
  const names = steps.map((step) => `“${step}”`).join(', ')
  const one = steps.length === 1
  if (why === 'not_learned') return `${names} ${one ? 'is' : 'are'} not learned ${app ? `for ${app} ` : ''}yet.`
  if (why === 'rejected') return `${names} ${one ? 'is' : 'are'} rejected. To run this chore, restore ${one ? 'it' : 'them'} in Steps.`
  if (why === 'to_revalidate') return `${app} was updated: ${names} ${one ? 'has' : 'have'} to be learned again.`
  return BLOCKED[why] ?? `It cannot run: ${spaced(why)}.`
}

// What rejected a step: {kind: 'person'} or {kind: 'different_effect', expected, got, at}.
export function whyWords(why) {
  if (why?.kind === 'person') return 'You rejected it.'
  if (why?.kind !== 'different_effect') return 'Why it was rejected was not recorded.'
  return `When it was learned, ${effectWords(why.expected)}. The last time it ran, ${effectWords(why.got)}.`
    + (why.at ? ` (${whenWords(why.at)})` : '')
}

// How far the shown run got with one box: undefined when the run knows nothing of it; 'unreached' for what has not run
// or was on the path not taken; and, once the run is over, what was still going is where it stopped.
export function boxState(run, id) {
  const state = run?.nodes[id]
  if (state === 'pending' || state === 'skipped') return 'unreached'
  if (run?.status !== 'running' && (state === 'running' || state === 'paused')) return 'blocked'
  return state
}

// A name no stored flow has yet, whatever the capitals.
export function freshTitle(flows, base = 'My flow') {
  const taken = flows.map((f) => f.title.toLowerCase())
  let title = base
  for (let n = 2; taken.includes(title.toLowerCase()); n++) title = `${base} ${n}`
  return title
}
