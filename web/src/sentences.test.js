import assert from 'node:assert/strict'
import test from 'node:test'
import { SYSTEM_NODES } from './catalog.js'
import { sentenceOf, workedWords } from './sentences.js'

const words = (...args) => sentenceOf(...args).join('')
const meta = (action, extra) => ({ app: 'paint.exe', action, locator: { role: 'button', name: 'Menu' }, ...extra })

test('each action of a step has its own sentence, with the control and the app', () => {
  const said = Object.fromEntries(['click', 'select', 'drag', 'type_value', 'type_secret', 'read_value', 'paste_text', 'press_keys']
    .map((action) => [action, words({ step: 'open-menu' }, meta(action))]))

  assert.deepEqual(said, {
    click: 'Presses the Menu button in Paint.',
    select: 'Selects the Menu button in Paint.',
    drag: 'Drags the Menu button in Paint to another place.',
    type_value: 'Types text into the Menu button in Paint.',
    type_secret: 'Types a saved secret into the Menu button in Paint.',
    read_value: 'Reads what the Menu button shows in Paint.',
    paste_text: 'Pastes text into Paint where the cursor is, once it finds the Menu button.',
    press_keys: 'Types on the keyboard in Paint, once it finds the Menu button.',
  })
  assert.equal(sentenceOf({ step: 'open-menu' }, meta('click'))[1], 'Menu') // the control stands apart, to be shown strong
  assert.equal(words({ step: 'x' }, meta('something_new')), 'Acts on the Menu button in Paint.')
})

test('a control with no name, or a name that may be screen content of a private app, is only called by what it is', () => {
  const field = (extra) => meta('type_value', { locator: { role: 'textfield', name: 'Alice  from\naccounts' }, ...extra })

  assert.equal(words({ step: 'x' }, field()), 'Types text into the Alice from accounts text field in Paint.')
  assert.equal(words({ step: 'x' }, field({ private: true })), 'Types text into a text field in Paint.')
  assert.equal(words({ step: 'x' }, meta('click', { locator: { role: 'icon', name: ' ' } })), 'Presses an icon in Paint.')
})

test('every system box has a sentence of its own, never made of what was typed into it', () => {
  const said = SYSTEM_NODES.map((entry) => {
    const typed = Object.fromEntries(Object.entries(entry.node.fields ?? {})
      .map(([name, binding]) => [name, name === 'mode' ? binding : { value: 'typed-secret-value' }]))
    return words({ ...entry.node, fields: typed })
  })

  for (const sentence of said) {
    assert.match(sentence, /^[A-Z].+\.$/)
    assert.doesNotMatch(sentence, /typed-secret-value|cannot say/)
  }
  assert.equal(new Set(said).size, SYSTEM_NODES.length)
  assert.equal(words({ kind: 'stop' }), 'Ends the chore here on purpose.')
  assert.equal(words({ kind: 'if', on: 'a', equals: 'revealed' }),
    'Takes the yes path or the no path, depending on what an earlier box changed on screen.')
})

test('a repeat that runs one action says which action it repeats', () => {
  assert.equal(words({ kind: 'loop', step: 'open-menu', max_iterations: 7 }, meta('click')),
    'Repeats this until it reaches its limit: presses the Menu button in Paint.')
})

test('an action nobody taught says so, and names the hole of a recipe', () => {
  assert.equal(words({ step: 'x' }, { missing: true }, 'word.exe'), 'Nobody has taught this action for Word yet.')
  assert.equal(words({ step: 'x' }, { missing: true, hole: { recipe: 'send-message', hole: 'compose' } }, 'word.exe'),
    'The “compose” part of the recipe “send-message” has not been taught for Word yet.')
  assert.equal(words({ step: 'x' }, undefined, ''), 'Nobody has taught this action for this app yet.')
})

test('how often an action has worked is said only where it is counted', () => {
  const counts = (successes, failures, counted = true) => workedWords({ successes, failures, counted })

  assert.equal(counts(4, 0), 'It has worked 4 times.')
  assert.equal(counts(1, 0), 'It has worked once.')
  assert.equal(counts(0, 0), 'It has not worked yet.')
  assert.equal(counts(4, 1), 'It has worked 4 times. Once it did not do what was expected.')
  assert.equal(counts(0, 2), 'It has not worked yet. 2 times it did not do what was expected.')
  assert.equal(counts(3, 0, false), '') // nothing on screen to compare with: nothing is counted
  assert.equal(workedWords(undefined), '')
})
