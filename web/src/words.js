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
const ROLES = { textfield: 'text field', menubutton: 'menu button', menuitem: 'menu item' }

const spaced = (code) => String(code).replaceAll('_', ' ')

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

// What rejected a step: {kind: 'person'} or {kind: 'different_effect', expected, got, at}.
export function whyWords(why) {
  if (why?.kind === 'person') return 'You rejected it.'
  if (why?.kind !== 'different_effect') return 'Why it was rejected was not recorded.'
  return `When it was learned, ${effectWords(why.expected)}. The last time it ran, ${effectWords(why.got)}.`
    + (why.at ? ` (${whenWords(why.at)})` : '')
}

// Mirrors the server (schedule.SAFE_NAME): a name goes into a web address and into a Windows task.
export function nameProblem(name) {
  if (name.length > 100) return 'A flow name can have at most 100 characters.'
  return /^[\p{L}\p{N}_.-]+$/u.test(name) && /[^.]/.test(name) ? ''
    : 'A flow name may only use letters, digits, "_", "." and "-" (no spaces).'
}

export function freshName(taken, base = 'my-flow') {
  let name = base
  for (let n = 2; taken.includes(name); n++) name = `${base}-${n}`
  return name
}
