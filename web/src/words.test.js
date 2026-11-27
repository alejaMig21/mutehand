import assert from 'node:assert/strict'
import test from 'node:test'
import { blockedWords, boxState, effectWords, flowTitle, freshTitle, lastRunWords, PAUSED_WORDS, reasonWords, runNoteWords, runWords, whenWords, whyWords } from './words.js'

test('a box says how far the run got with it, and nothing is left running after a run ends', () => {
  const run = (status, nodes) => ({ status, nodes })

  assert.equal(boxState(undefined, 'a'), undefined) // nothing ran
  assert.equal(boxState(run('running', { a: 'running' }), 'a'), 'running')
  assert.equal(boxState(run('running', { a: 'pending' }), 'a'), 'unreached')
  assert.equal(boxState(run('finished', { a: 'skipped' }), 'a'), 'unreached') // the path not taken
  assert.equal(boxState(run('emergency', { a: 'running' }), 'a'), 'blocked')
  assert.equal(boxState(run('error', { a: 'paused' }), 'a'), 'blocked')
  assert.equal(boxState(run('finished', { a: 'done' }), 'a'), 'done')
  assert.equal(boxState(run('finished', { a: 'done' }), 'added-later'), undefined)
})

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

test('run results and effects are plain words', () => {
  assert.deepEqual(['finished', 'stopped', 'waiting', 'emergency', 'error'].map(runWords), ['Finished', 'Stopped', 'Waiting', 'Stopped by you', 'Failed'])
  assert.equal(effectWords('no_change'), 'nothing changed on screen')
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

test('a run that left no record says what happened, and never repeats a code', () => {
  assert.match(runNoteWords({ status: 'waiting' }, 'Paint'), /open question/)
  assert.match(runNoteWords({ status: 'busy' }, 'Paint'), /already running/)
  assert.match(runNoteWords({ status: 'error', error: 'APP_NOT_FOUND' }, 'Paint'), /^It failed to run\. Check that Paint is open/)
  assert.match(runNoteWords({ status: 'error', error: 'INTERNAL' }, 'Paint'), /problem inside Workflow Factory/)
  assert.equal(runNoteWords({ status: 'error', error: 'no such run' }, 'Paint'), 'The run was lost (no such run).')
  for (const run of [undefined, { status: 'finished' }, { status: 'running' }, { status: 'stopped' }]) assert.equal(runNoteWords(run, 'Paint'), '')
})

test('why a chore cannot run is said with its actions and its app, never as a code', () => {
  const words = (why, steps = []) => blockedWords({ why, steps }, 'Paint')

  for (const why of ['empty', 'no_app', 'expression', 'question', 'unreadable', 'something_new']) assert.match(words(why), /^[A-Z][^_]*\.$/, why)
  assert.equal(words('not_learned', ['a', 'b']), '“a”, “b” are not learned for Paint yet.')
  assert.equal(blockedWords({ why: 'not_learned', steps: ['a'] }, ''), '“a” is not learned yet.')
  assert.equal(words('rejected', ['a', 'b']), '“a”, “b” are rejected. To run this chore, restore them in Steps.')
  assert.equal(words('to_revalidate', ['a', 'b']), 'Paint was updated: “a”, “b” have to be learned again.')
  assert.equal(blockedWords(null, 'Paint'), '')
})

test('how the last run of a chore went is said with the day and the time', () => {
  const now = new Date(2026, 10, 26, 18, 0)
  const at = (...when) => new Date(...when).toISOString()
  const words = (status, when) => lastRunWords({ status, at: when }, now).words

  assert.equal(words('finished', at(2026, 10, 26, 7, 0)), 'Worked today at 07:00')
  assert.equal(words('stopped', at(2026, 10, 25, 9, 0)), 'Stopped yesterday at 09:00')
  assert.equal(words('emergency', at(2026, 10, 3, 23, 5)), 'You stopped it on 3 Nov at 23:05')
  assert.equal(words('error', at(2025, 11, 31, 0, 30)), 'Failed on 31 Dec 2025 at 00:30')
  assert.equal(lastRunWords({ status: 'finished', at: at(2026, 9, 31, 12, 0) }, new Date(2026, 10, 1, 1, 0)).words, 'Worked yesterday at 12:00')
  assert.equal(words('finished', 'soon'), 'Worked soon')
  assert.deepEqual(lastRunWords(null, now), { words: 'Never run', tone: 'muted', icon: 'help' })
  assert.deepEqual(['finished', 'stopped', 'emergency', 'error'].map((s) => lastRunWords({ status: s, at: 'x' }, now).tone),
    ['ok', 'bad', 'warn', 'bad'])
})

test('a paused run says why: you used the mouse', () => {
  assert.match(PAUSED_WORDS, /you moved the mouse/)
  assert.match(PAUSED_WORDS, /resumes when you stop/)
})
