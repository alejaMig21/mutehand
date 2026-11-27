// What the strip under the canvas says about the chosen box. Pure, so node can test it.
//
// A sentence is made only of the box's kind, operation, action, control and app. Field values are never read: they hold
// what was typed. In a private app the control's name may be screen content, so only its role is said.

import { appLabel } from './catalog.js'
import { roleWords } from './words.js'

// action -> what comes before and after the control
const ACTIONS = {
  click: (app) => ['Presses', ` in ${app}.`],
  select: (app) => ['Selects', ` in ${app}.`],
  drag: (app) => ['Drags', ` in ${app} to another place.`],
  type_value: (app) => ['Types text into', ` in ${app}.`],
  type_secret: (app) => ['Types a saved secret into', ` in ${app}.`],
  read_value: (app) => ['Reads what', ` shows in ${app}.`],
  paste_text: (app) => [`Pastes text into ${app} where the cursor is, once it finds`, '.'],
  press_keys: (app) => [`Types on the keyboard in ${app}, once it finds`, '.'],
}
const OTHER_ACTION = (app) => ['Acts on', ` in ${app}.`] // an action newer than this screen

// system box -> its sentence; a trigger is told apart by its mode, a data box by its operation
const SYSTEM = {
  'trigger:manual': 'Starts the chore when you run it.',
  'trigger:daily': 'Starts the chore on its daily run.',
  foreach: 'Repeats the action it leads to, once for each item in its list.',
  if: 'Takes the yes path or the no path, depending on its condition.',
  'if:effect': 'Takes the yes path or the no path, depending on what an earlier box changed on screen.',
  join: 'Waits for every path that leads here, then goes on.',
  wait: 'Waits a while before the chore goes on.',
  stop: 'Ends the chore here on purpose.',
  'data:compare': 'Compares two values.',
  'data:and': 'Answers yes when both values are true.',
  'data:or': 'Answers yes when at least one of two values is true.',
  'data:not': 'Turns true into false, and false into true.',
  'data:fixed': 'Gives later boxes a value set here.',
  'data:convert': 'Turns a value into another kind, such as a number or a text.',
  'data:split': 'Cuts a text into a list.',
  'data:join': 'Puts a list together into one text.',
  'data:format': 'Fills the named places of a text pattern.',
  'data:regex': 'Looks for a pattern in a text.',
  'data:get': 'Takes one part out of a group of values.',
  'data:set': 'Changes one part of a group of values.',
  'data:math': 'Calculates with two numbers.',
}

function systemKey(node) {
  if (node.kind === 'trigger') return `trigger:${node.fields?.mode?.value}`
  if (node.kind === 'data') return `data:${node.op}`
  return node.kind === 'if' && !node.fields?.condition ? 'if:effect' : node.kind
}

// [before, the control's name or '', after]: the name stands apart so the screen can show it strong
function actionSentence(meta, app) {
  if (!meta || meta.missing) {
    const where = app ? appLabel(app) : 'this app'
    const hole = meta?.hole
    return [hole ? `The “${hole.hole}” part of the recipe “${hole.recipe}” has not been taught for ${where} yet.`
      : `Nobody has taught this action for ${where} yet.`, '', '']
  }
  const [lead, tail] = (ACTIONS[meta.action] ?? OTHER_ACTION)(appLabel(meta.app))
  const role = roleWords(meta.locator?.role || 'item')
  const name = meta.private ? '' : String(meta.locator?.name ?? '').replace(/\s+/g, ' ').trim()
  return name ? [`${lead} the `, name, ` ${role}${tail}`] : [`${lead} ${/^[aeiou]/i.test(role) ? 'an' : 'a'} ${role}${tail}`, '', '']
}

export function sentenceOf(node, meta, app = '') {
  if (!node.kind || node.kind === 'step') return actionSentence(meta, app)
  if (node.kind === 'loop') {
    const [before, name, after] = actionSentence(meta, app)
    const repeated = meta && !meta.missing ? before.charAt(0).toLowerCase() + before.slice(1) : before
    return [`Repeats this until it reaches its limit: ${repeated}`, name, after]
  }
  return [SYSTEM[systemKey(node)] ?? 'This screen cannot say what this box does.', '', '']
}

const times = (n) => (n === 1 ? 'once' : `${n} times`)

// Only an action that leaves something on screen to compare with is counted: the others say nothing.
export function workedWords(meta) {
  if (!meta?.counted) return ''
  const worked = meta.successes ? `It has worked ${times(meta.successes)}.` : 'It has not worked yet.'
  if (!meta.failures) return worked
  const failed = times(meta.failures)
  return `${worked} ${failed.charAt(0).toUpperCase()}${failed.slice(1)} it did not do what was expected.`
}
