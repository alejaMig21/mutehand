import assert from 'node:assert/strict'
import test from 'node:test'
import { fromFlowJson, layout, nextNodeId, toFlowJson } from './flowjson.js'

test('a flow survives the trip from API JSON to the canvas and back', () => {
  const flow = {
    nodes: [
      { id: 'n1', step: 'open-menu', inputs: [['text', 'str']], exclusive_input: true },
      { id: 'n3', step: 'save-file' },
    ],
    edges: [['n1', 'n3']],
  }
  const { nodes, edges } = fromFlowJson(flow)

  assert.deepEqual(toFlowJson(nodes, edges), {
    nodes: [
      { id: 'n1', step: 'open-menu', inputs: [['text', 'str']], exclusive_input: true },
      { id: 'n3', step: 'save-file', inputs: [], exclusive_input: false },
    ],
    edges: [['n1', 'n3']],
  })
})

test('a new node id never reuses one that is on the canvas', () => {
  assert.equal(nextNodeId([]), 'n1')
  assert.equal(nextNodeId([{ id: 'n1' }, { id: 'n3' }]), 'n4')
  assert.equal(nextNodeId([{ id: 'custom' }, { id: 'n2' }]), 'n3')
})

test('nodes are laid out on a four column grid', () => {
  assert.deepEqual(layout(0), { x: 60, y: 60 })
  assert.deepEqual(layout(4), { x: 60, y: 180 })
})
