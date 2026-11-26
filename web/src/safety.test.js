import assert from 'node:assert/strict'
import test from 'node:test'
import { safetySummary, summaryMarks, whyNotRunnable } from './safety.js'

const step = (id, name, state, extra = {}) => ({ id, data: { node: { step: name }, meta: { state, ...extra } } })
const system = (id) => ({ id, data: { node: { kind: 'wait' }, meta: {} } })

test('the summary counts rejected steps, missing consents and open doubts', () => {
  const nodes = [step('a', 'Read', 'trusted'), step('b', 'Send', 'suspect', { consent: 'missing' }), step('c', 'Old', 'rejected'),
    step('d', 'Check', 'to_revalidate', { consent: 'given' }), system('e')]

  assert.deepEqual(safetySummary(nodes, { b: 1, c: 2 }), {
    rejected: [{ id: 'c', step: 'Old' }], missing: [], needsConsent: 1, doubts: 3,
  })
})

test('every mark says its words as well as its icon, and a clean flow says nothing', () => {
  assert.deepEqual(summaryMarks({ rejected: [], missing: [], needsConsent: 0, doubts: 0 }), [])
  const marks = summaryMarks({ rejected: [{ id: 'c', step: 'Old' }], missing: [{ id: 'z', step: 'x' }], needsConsent: 2, doubts: 1 })

  assert.deepEqual(marks.map((m) => m[1]), ['1 rejected step', '1 step not taught yet', '2 steps need consent', '1 doubt'])
  assert.ok(marks.every(([icon, words]) => icon && words))
})

test('a flow with a rejected step says which one will not let it start', () => {
  assert.equal(whyNotRunnable({ rejected: [], missing: [] }), '')
  assert.match(whyNotRunnable({ rejected: [{ id: 'c', step: 'Old' }], missing: [] }), /'Old' is rejected/)
  assert.match(whyNotRunnable({ rejected: [{ id: 'c', step: 'Old' }, { id: 'd', step: 'Odd' }], missing: [] }), /'Old', 'Odd' are rejected/)
})

test('a flow with a recipe hole nobody filled says which hole and cannot start', () => {
  const missing = [{ id: 'b', step: 'send-message-compose', hole: { recipe: 'send-message', hole: 'compose' } }]
  const words = whyNotRunnable({ rejected: [], missing })

  assert.match(words, /hole 'compose' of the recipe 'send-message'/)
  assert.match(whyNotRunnable({ rejected: [], missing: [{ id: 'q', step: 'Lonely' }] }), /'Lonely' has no step for this app/)
})
