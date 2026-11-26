import assert from 'node:assert/strict'
import test from 'node:test'
import { autoLayout, fromFlowJson, layout, nextNodeId, toFlowJson } from './flowjson.js'

test('a flow survives the trip from API JSON to the canvas and back', () => {
  const flow = {
    nodes: [
      { id: 'n1', step: 'open-menu', inputs: [['text', 'str']], exclusive_input: true },
      { id: 'n3', step: 'save-file', inputs: [], exclusive_input: false },
    ],
    edges: [['n1', 'n3']],
  }
  const { nodes, edges } = fromFlowJson(flow)

  assert.deepEqual(toFlowJson(nodes, edges), flow)
})

test('every stored field of a node comes back, even one the canvas does not know', () => {
  const node = { id: 'w', kind: 'wait', fields: { seconds: { value: 5 } }, on_failure: 'retry', retries: 2, inputs: [], exclusive_input: false }
  const { nodes, edges } = fromFlowJson({ nodes: [node], edges: [] })

  assert.deepEqual(toFlowJson(nodes, edges).nodes, [node])
})

test('a flow without stored edges is drawn one node after another, leaving out the body of a for each', () => {
  const { edges } = fromFlowJson({ nodes: [{ id: 'a', step: 's' }, { id: 'b', step: 't' }, { id: 'c', step: 'u' }] })
  assert.deepEqual(edges.map((e) => [e.source, e.target]), [['a', 'b'], ['b', 'c']])

  const withBody = fromFlowJson({
    nodes: [{ id: 'a', step: 's' }, { id: 'e', kind: 'foreach', body: 'x', fields: {} }, { id: 'x', step: 't' }, { id: 'z', step: 'u' }],
  })
  assert.deepEqual(withBody.edges.map((e) => [e.source, e.target]), [['e', 'x'], ['a', 'e'], ['e', 'z']])
})

test('the first two wires out of an if are its then and its otherwise', () => {
  const nodes = [
    { id: 'i', type: 'card', position: layout(0), data: { node: { id: 'i', kind: 'if', fields: {} } } },
    { id: 'a', type: 'card', position: layout(1), data: { node: { id: 'a', step: 's' } } },
    { id: 'b', type: 'card', position: layout(2), data: { node: { id: 'b', step: 't' } } },
  ]
  const stored = toFlowJson(nodes, [{ source: 'i', target: 'b' }, { source: 'i', target: 'a' }])

  assert.equal(stored.nodes[0].then, 'b')
  assert.equal(stored.nodes[0].otherwise, 'a')
  const again = fromFlowJson(stored)
  assert.deepEqual(again.edges.map((e) => [e.source, e.target]), [['i', 'b'], ['i', 'a']])
})

test('the first node a for each connects to becomes its body, and that wire is not stored as an edge', () => {
  const nodes = [
    { id: 'e', type: 'card', position: layout(0), data: { node: { id: 'e', kind: 'foreach', fields: {} } } },
    { id: 'x', type: 'card', position: layout(1), data: { node: { id: 'x', step: 's' } } },
    { id: 'z', type: 'card', position: layout(2), data: { node: { id: 'z', step: 't' } } },
  ]
  const stored = toFlowJson(nodes, [{ source: 'e', target: 'x' }, { source: 'e', target: 'z' }])

  assert.equal(stored.nodes[0].body, 'x')
  assert.deepEqual(stored.edges, [['e', 'z']])
})

test('a new node id never reuses one that is on the canvas', () => {
  assert.equal(nextNodeId([]), 'n1')
  assert.equal(nextNodeId([{ id: 'n1' }, { id: 'n3' }]), 'n4')
  assert.equal(nextNodeId([{ id: 'custom' }, { id: 'n2' }]), 'n3')
})

test('nodes are laid out on a four column grid', () => {
  assert.deepEqual(layout(0), { x: 60, y: 60 })
  assert.deepEqual(layout(4), { x: 60, y: 210 })
  assert.deepEqual(layout(1), { x: 290, y: 60 })
})

test('a stored flow is laid out in columns by distance from the start, wires running left to right', () => {
  const at = autoLayout(['a', 'b', 'c', 'd'], [['a', 'b'], ['b', 'c'], ['a', 'd']])

  assert.ok(at.a.x < at.b.x && at.b.x < at.c.x)
  assert.equal(at.d.x, at.b.x) // a and d are one wire apart, like a and b
  assert.notEqual(at.d.y, at.b.y) // but not on top of each other
})

test('a wire drawn in a loop does not hang the layout', () => {
  const at = autoLayout(['a', 'b'], [['a', 'b'], ['b', 'a']])

  assert.equal(Object.keys(at).length, 2)
})
