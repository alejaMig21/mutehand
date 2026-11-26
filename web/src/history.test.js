import assert from 'node:assert/strict'
import test from 'node:test'
import { historyWords } from './history.js'

const NOW = new Date(2026, 10, 26, 12, 0)
const at = (day, hour) => new Date(2026, 10, day, hour, 5).toISOString()
const node = (node_id, status, extra = {}) => ({ node_id, status, reason: null, effect: null, step: null, kind: 'step', op: null, ...extra })

test('a run reads in words, a box by the name it had when it ran, and never as a code', () => {
  const [run] = historyWords([{
    id: 9, status: 'stopped', started_at: at(26, 7), stopped_node: 'n2',
    nodes: [node('n1', 'done', { step: 'open-menu', effect: 'closed_dialog' }), node('n2', 'blocked', { kind: 'wait', reason: 'control_not_found' }),
      node('n3', 'skipped', { kind: 'data', op: 'compare' }), node('n4', 'skipped', { kind: 'trigger' })],
  }], NOW)

  assert.equal(run.id, 9)
  assert.match(run.title, /^Stopped today at 07:05$/)
  assert.deepEqual(run.boxes.map((b) => b.words), [
    'open-menu: done (a dialog closed)',
    'Wait a while: stopped. The button or field this step uses is not on the screen.',
    'Compare: skipped',
    'Start: skipped',
  ])
  assert.deepEqual(run.boxes.map((b) => b.tone), ['ok', 'bad', 'muted', 'muted'])
  assert.doesNotMatch(run.boxes.map((b) => b.words).join(' '), /\bn[1-4]\b|control_not_found/)
})

test('a run recorded before boxes kept their kind is named by its step, else by a plain "Box"', () => {
  const [run] = historyWords([{ id: 1, status: 'finished', started_at: at(25, 9), stopped_node: null,
    nodes: [node('n1', 'done', { step: 'save', kind: null }), node('n2', 'done', { kind: null })] }], NOW)

  assert.deepEqual(run.boxes.map((b) => b.words), ['save: done', 'A box: done'])
  assert.match(run.title, /^Worked yesterday at 09:05$/)
})

test('a failed box that carried on, and a run with no boxes, still read well', () => {
  const [run] = historyWords([{ id: 2, status: 'error', started_at: at(1, 8), stopped_node: null,
    nodes: [node('n1', 'continued', { step: 'a' })] }], NOW)
  assert.equal(run.boxes[0].words, 'a: failed, carried on')
  assert.equal(run.boxes[0].tone, 'warn')
  assert.deepEqual(historyWords([], NOW), [])
})
