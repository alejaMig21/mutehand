import assert from 'node:assert/strict'
import test from 'node:test'
import { doubtWords, effectWords, flowWords, nameProblem, freshName, reasonWords, runWords, stateWords, whenWords, whyWords } from './words.js'

test('every reason a run can stop for is said in a sentence, never as a code', () => {
  const reasons = ['no_consent', 'control_not_found', 'unreadable', 'out_of_frame', 'rejected', 'to_revalidate',
    'template_no_match', 'missing_input', 'bad_data', 'unsendable_text', 'effect_mismatch', 'step_missing', 'action_failed', 'cell_requires_paste_text',
    'wrong_window', 'user_active', 'precondition_not_met', 'secure_field_requires_type_secret']
  for (const reason of reasons) {
    assert.doesNotMatch(reasonWords(reason), /_|^Stopped:/, reason)
    assert.match(reasonWords(reason), /^[A-Z].*\.$/, reason)
  }
  assert.match(reasonWords('something_new'), /something new/) // an unknown one still reads as words
})

test('states, effects and doubts are plain words', () => {
  assert.deepEqual(['trusted', 'suspect', 'rejected', 'to_revalidate'].map(stateWords), ['Trusted', 'On trial', 'Rejected', 'Needs a re-check'])
  assert.deepEqual(['finished', 'stopped', 'waiting', 'emergency', 'error'].map(runWords), ['Finished', 'Stopped', 'Waiting', 'Stopped by you', 'Failed'])
  assert.match(nameProblem('a'.repeat(101)), /100 characters/)
  assert.equal(effectWords('no_change'), 'nothing changed on screen')
  assert.equal(doubtWords({ button: 2, textfield: 1 }), '2 buttons, 1 text field')
  assert.equal(doubtWords({}), 'nothing')
})

test('a time is shown in the local short form, and anything else is left as it is', () => {
  assert.doesNotMatch(whenWords('2026-01-01T09:30:00Z'), /T|Z$/)
  assert.equal(whenWords('soon'), 'soon')
})

test('a flow name the server would refuse is refused before it is sent', () => {
  for (const name of ['report', 'mañana', 'a.b-c_1']) assert.equal(nameProblem(name), '', name)
  for (const name of ['', 'two words', 'a/b', 'x?v2', 'old#1', '..', '50%']) assert.match(nameProblem(name), /flow name/i, name)
})

test('a new flow never starts with the name of an existing one', () => {
  assert.equal(freshName([]), 'my-flow')
  assert.equal(freshName(['my-flow', 'my-flow-2']), 'my-flow-3')
})

test('why a step is rejected is told as what happened', () => {
  const different = whyWords({ kind: 'different_effect', expected: 'revealed', got: 'no_change', at: '2026-01-01T09:30:00Z' })

  assert.match(different, /When it was learned, something new appeared\. The last time it ran, nothing changed on screen/)
  assert.equal(whyWords({ kind: 'person' }), 'You rejected it.')
  assert.match(whyWords(null), /not recorded/)
})

test('a test of one node is named after its flow', () => {
  assert.equal(flowWords('morning#test:n2'), 'morning (one node tested)')
  assert.equal(flowWords('morning'), 'morning')
})
