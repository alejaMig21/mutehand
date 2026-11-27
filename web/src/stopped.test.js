import assert from 'node:assert/strict'
import test from 'node:test'
import { helpMessage, ranResult, rejectedWords, relearnMessage, relearnWords, stoppedWords, triedResult } from './stopped.js'

const item = { flow: 'weekly', title: 'Weekly export', app: 'paint.exe', private: false, node: 'n2', step: 'Close message',
  reason: 'control_not_found', doubt: 12, note: null, at: new Date(2026, 10, 25, 9, 0).toISOString(), rejected_by_person: [] }
const now = new Date(2026, 10, 26, 18, 0)

test('a stopped flow says which flow, when, at which node and why, in plain words', () => {
  const says = stoppedWords(item, now)

  assert.equal(says.title, '“Weekly export” stopped yesterday at 09:00')
  assert.equal(says.detail, 'At “Close message”: The button or field this step uses is not on the screen.')
  assert.match(says.hint, /try again/i)
  assert.doesNotMatch(JSON.stringify(says), /control_not_found|_/)
})

test('a node in a private app is not named, and a stop with no time is still said', () => {
  const says = stoppedWords({ ...item, private: true, step: null, at: null }, now)

  assert.equal(says.title, '“Weekly export” stopped')
  assert.match(says.detail, /^At one of its steps: /)
})

test('a stop the person caused says to allow the step again before anything else', () => {
  const says = stoppedWords({ ...item, rejected_by_person: [{ app: 'paint.exe', step: 'close-message' }] }, now)

  assert.match(says.hint, /rejected/)
  assert.match(says.hint, /Allow again/)
})

test('the message to send names the flow, the node and the reason, and carries the note', () => {
  const message = helpMessage(item, 'Paint', 'It happens only when Paint is minimised')

  assert.match(message, /“Weekly export”/)
  assert.match(message, /“Close message”/)
  assert.match(message, /The button or field this step uses is not on the screen\./)
  assert.match(message, /open question 12/)
  assert.match(message, /It happens only when Paint is minimised/)
  assert.doesNotMatch(message, /control_not_found|lesson|teach|learn|study/i)
  assert.doesNotMatch(helpMessage(item, 'Paint', '  '), /note/i) // no note, no mention of one
})

test('a private app is named in the message, its node is not', () => {
  const message = helpMessage({ ...item, private: true, step: null }, 'Chat', '')

  assert.match(message, /Chat/)
  assert.doesNotMatch(message, /Close message/)
})

const run = (status, nodes = {}, extra = {}) => ({ status, nodes, ...extra })

test('trying again that works says it is fixed and how many steps finished', () => {
  const result = triedResult(item, run('finished', { t: 'done', a: 'done', b: 'continued', c: 'skipped' }), null)

  assert.equal(result.tone, 'ok')
  assert.equal(result.title, 'Fixed: “Weekly export” ran to the end just now.')
  assert.equal(result.detail, '3 steps finished.')
  assert.equal(triedResult(item, run('finished', { a: 'done' }), null).detail, '1 step finished.')
})

test('trying again that stops at the same node for the same reason is the same problem', () => {
  const result = triedResult(item, run('stopped', {}, { stopped: 'n2' }), { ...item, doubt: 13 })

  assert.equal(result.tone, 'bad')
  assert.match(result.title, /^Still stopped: “Weekly export”/)
  assert.match(result.detail, /Close message/)
})

test('trying again that stops somewhere else, or for another reason, is a new problem', () => {
  const elsewhere = triedResult(item, run('stopped', {}, { stopped: 'n3' }), { ...item, node: 'n3', step: 'Save picture' })
  const another = triedResult(item, run('stopped', {}, { stopped: 'n2' }), { ...item, reason: 'effect_mismatch' })

  assert.match(elsewhere.title, /^A new problem: “Weekly export”/)
  assert.match(elsewhere.detail, /Save picture/)
  assert.match(another.title, /^A new problem/)
  assert.match(another.detail, /did not change the way/)
})

test('a try that ended some other way says so', () => {
  assert.match(triedResult(item, run('emergency'), null).title, /You stopped it/)
  assert.match(triedResult(item, run('error', {}, { error: 'APP_NOT_FOUND' }), null).detail, /Check that Paint is open/)
  assert.equal(triedResult(item, run('waiting'), null).tone, 'warn')
  assert.equal(triedResult(item, run('error', {}, { error: 'INTERNAL' }), null).tone, 'bad')
})

const flows = [{ id: 'a', title: 'Morning report' }, { id: 'b', title: 'Evening report' }]

test('an app update names the app and the flows it blocks, never a file name', () => {
  const says = relearnWords({ app: 'paint.exe', flows })

  assert.equal(says.title, 'Paint was updated')
  assert.match(says.detail, /These flows wait for that: “Morning report”, “Evening report”\./)
  assert.match(says.message, /Paint was updated .* learned again/)
  assert.doesNotMatch(says.message, /\.exe/)
})

test('the update message is one text, with or without the flows that wait', () => {
  const alone = relearnMessage('Paint')
  assert.equal(alone, 'In Mutehand, Paint was updated and its steps have to be learned again. Please find which ones and teach them again.')
  assert.equal(relearnWords({ app: 'paint.exe', flows }).message, relearnMessage('Paint', flows))
  assert.match(relearnMessage('Paint', flows.slice(0, 1)), /^.*again so this flow can run: “Morning report”\.$/)
})

test('a rejected step says who rejected it, and a private app is not named', () => {
  assert.equal(rejectedWords({ app: 'paint.exe', step: 'save-file', private: false, why: { kind: 'person' }, flows }).title, '“save-file” is rejected')
  const hidden = rejectedWords({ app: 'vault.exe', step: 'secret-step', private: true, why: { kind: 'different_effect' }, flows })

  assert.doesNotMatch(JSON.stringify(hidden), /secret-step/)
  assert.match(hidden.detail, /did not do what it was taught/)
})

test('a run that ended here is the one line of the row: when it worked and how many steps it did', () => {
  const now = new Date(2026, 10, 27, 12, 0)
  const ended = new Date(2026, 10, 27, 9, 5).toISOString()
  const ok = ranResult({ ...run('finished', { a: 'done', b: 'done' }), ended }, now)
  assert.equal(ok.tone, 'ok')
  assert.equal(ok.words, 'Worked today at 09:05. 2 steps finished.')
  assert.equal(ranResult({ ...run('finished', { a: 'done' }), ended }, now).words, 'Worked today at 09:05. 1 step finished.')
  assert.equal(ranResult({ ...run('running'), ended }, now), null)
  assert.equal(ranResult(run('finished', { a: 'done' }), now), null) // no time known: the history line speaks
})
