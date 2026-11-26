import assert from 'node:assert/strict'
import test from 'node:test'
import { safetySummary, summaryMarks, whyNotRunnable } from './safety.js'

const step = (id, name, state, extra = {}) => ({ id, data: { node: { step: name }, meta: { state, ...extra } } })
const system = (id) => ({ id, data: { node: { kind: 'wait' }, meta: {} } })

test('the summary counts steps on trial, rejected steps, missing consents and open doubts', () => {
  const nodes = [step('a', 'Read', 'trusted'), step('b', 'Send', 'suspect', { consent: 'missing' }), step('c', 'Old', 'rejected'),
    step('d', 'Check', 'to_revalidate', { consent: 'given' }), system('e')]

  assert.deepEqual(safetySummary(nodes, { b: 1, c: 2 }), {
    onTrial: 2, rejected: [{ id: 'c', step: 'Old' }], needsConsent: 1, doubts: 3,
  })
})

test('every mark says its words as well as its icon, and a clean flow says nothing', () => {
  assert.deepEqual(summaryMarks({ onTrial: 0, rejected: [], needsConsent: 0, doubts: 0 }), [])
  const marks = summaryMarks({ onTrial: 1, rejected: [{ id: 'c', step: 'Old' }], needsConsent: 2, doubts: 1 })

  assert.deepEqual(marks.map((m) => m[1]), ['1 rejected step', '1 step on trial', '2 steps need consent', '1 doubt'])
  assert.ok(marks.every(([icon, words]) => icon && words))
})

test('a flow with a rejected step says which one will not let it start', () => {
  assert.equal(whyNotRunnable({ rejected: [] }), '')
  assert.match(whyNotRunnable({ rejected: [{ id: 'c', step: 'Old' }] }), /'Old' is rejected/)
  assert.match(whyNotRunnable({ rejected: [{ id: 'c', step: 'Old' }, { id: 'd', step: 'Odd' }] }), /'Old', 'Odd' are rejected/)
})
