import assert from 'node:assert/strict'
import test from 'node:test'
import { doubtWords, effectWords, flowTitle, flowWords, freshTitle, reasonWords, runWords, stateWords, whenWords, whyWords } from './words.js'

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
  assert.equal(effectWords('no_change'), 'nothing changed on screen')
  assert.equal(doubtWords({ button: 2, textfield: 1 }), '2 buttons, 1 text field')
  assert.equal(doubtWords({}), 'nothing')
})

test('a time is shown in the local short form, and anything else is left as it is', () => {
  assert.doesNotMatch(whenWords('2026-01-01T09:30:00Z'), /T|Z$/)
  assert.equal(whenWords('soon'), 'soon')
})

test('a new flow never starts with the name of an existing one, whatever the capitals', () => {
  assert.equal(freshTitle([]), 'My flow')
  assert.equal(freshTitle([{ title: 'my FLOW' }, { title: 'My flow 2' }]), 'My flow 3')
  assert.equal(freshTitle([{ title: 'Report copy' }], 'Report copy'), 'Report copy 2')
})

test('why a step is rejected is told as what happened', () => {
  const different = whyWords({ kind: 'different_effect', expected: 'revealed', got: 'no_change', at: '2026-01-01T09:30:00Z' })

  assert.match(different, /When it was learned, something new appeared\. The last time it ran, nothing changed on screen/)
  assert.equal(whyWords({ kind: 'person' }), 'You rejected it.')
  assert.match(whyWords(null), /not recorded/)
})

test('a flow is called by its name, and two with one name are told apart', () => {
  const flows = [{ id: 'm', title: 'Morning report' }, { id: 'a', title: 'Twin' }, { id: 'b', title: 'Twin' }]

  assert.equal(flowTitle('m', flows), 'Morning report')
  assert.equal(flowTitle('a', flows), 'Twin (a)')
  assert.equal(flowTitle('gone', flows), 'gone') // a flow that is no longer stored keeps its identifier
})

test('a test of one node is named after its flow', () => {
  const flows = [{ id: 'morning', title: 'Morning report' }]

  assert.equal(flowWords('morning#test:n2', flows), 'Morning report (one node tested)')
  assert.equal(flowWords('morning', flows), 'Morning report')
})
