import assert from 'node:assert/strict'
import test from 'node:test'
import { helpMessage, stoppedWords, triedResult } from './stopped.js'

const item = { flow: 'weekly', title: 'Weekly export', app: 'paint.exe', private: false, node: 'n2', box: 'Close message',
  reason: 'control_not_found', doubt: 12, note: null, at: new Date(2026, 10, 25, 9, 0).toISOString(), rejected_by_person: [] }
const now = new Date(2026, 10, 26, 18, 0)

test('a stopped chore says which chore, when, at which box and why, in plain words', () => {
  const says = stoppedWords(item, now)

  assert.equal(says.title, '“Weekly export” stopped yesterday at 09:00')
  assert.equal(says.detail, 'At “Close message”: The button or field this step uses is not on the screen.')
  assert.match(says.hint, /try again/i)
  assert.doesNotMatch(JSON.stringify(says), /control_not_found|_/)
})

test('a box in a private app is not named, and a stop with no time is still said', () => {
  const says = stoppedWords({ ...item, private: true, box: null, at: null }, now)

  assert.equal(says.title, '“Weekly export” stopped')
  assert.match(says.detail, /^At one of its boxes: /)
})

test('a stop the person caused says to allow the action again before anything else', () => {
  const says = stoppedWords({ ...item, rejected_by_person: [{ app: 'paint.exe', step: 'close-message' }] }, now)

  assert.match(says.hint, /rejected/)
  assert.match(says.hint, /Allow again/)
})

test('the message to send names the chore, the box and the reason, and carries the note', () => {
  const message = helpMessage(item, 'Paint', 'It happens only when Paint is minimised')

  assert.match(message, /“Weekly export”/)
  assert.match(message, /“Close message”/)
  assert.match(message, /The button or field this step uses is not on the screen\./)
  assert.match(message, /open question 12/)
  assert.match(message, /It happens only when Paint is minimised/)
  assert.doesNotMatch(message, /control_not_found|lesson|teach|learn|study/i)
  assert.doesNotMatch(helpMessage(item, 'Paint', '  '), /note/i) // no note, no mention of one
})

test('a private app is named in the message, its box is not', () => {
  const message = helpMessage({ ...item, private: true, box: null }, 'Chat', '')

  assert.match(message, /Chat/)
  assert.doesNotMatch(message, /Close message/)
})

const run = (status, nodes = {}, extra = {}) => ({ status, nodes, ...extra })

test('trying again that works says it is fixed and how many boxes finished', () => {
  const result = triedResult(item, run('finished', { t: 'done', a: 'done', b: 'continued', c: 'skipped' }), null)

  assert.equal(result.tone, 'ok')
  assert.equal(result.title, 'Fixed: “Weekly export” ran to the end just now.')
  assert.equal(result.detail, '3 boxes finished.')
  assert.equal(triedResult(item, run('finished', { a: 'done' }), null).detail, '1 box finished.')
})

test('trying again that stops at the same box for the same reason is the same problem', () => {
  const result = triedResult(item, run('stopped', {}, { stopped: 'n2' }), { ...item, doubt: 13 })

  assert.equal(result.tone, 'bad')
  assert.match(result.title, /^Still stopped: “Weekly export”/)
  assert.match(result.detail, /Close message/)
})

test('trying again that stops somewhere else, or for another reason, is a new problem', () => {
  const elsewhere = triedResult(item, run('stopped', {}, { stopped: 'n3' }), { ...item, node: 'n3', box: 'Save picture' })
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
