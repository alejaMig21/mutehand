import assert from 'node:assert/strict'
import test from 'node:test'
import { autoLayout, boxNumbers, chainLoose, fromFlowJson, joinBoxes, nextNodeId, toFlowJson, withBranch } from './flowjson.js'

test('a flow survives the trip from API JSON to the canvas and back', () => {
  const flow = {
    nodes: [
      { id: 'n1', step: 'open-menu', inputs: [['text', 'str']], exclusive_input: true },
      { id: 'n3', step: 'save-file', inputs: [], exclusive_input: false },
    ],
    edges: [['n1', 'n3']],
  }
  const { nodes, edges } = fromFlowJson(flow)
  const { positions, ...stored } = toFlowJson(nodes, edges)

  assert.deepEqual(stored, flow)
  assert.deepEqual(Object.keys(positions), ['n1', 'n3'])
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
    { id: 'i', type: 'card', position: { x: 0, y: 0 }, data: { node: { id: 'i', kind: 'if', fields: {} } } },
    { id: 'a', type: 'card', position: { x: 300, y: 0 }, data: { node: { id: 'a', step: 's' } } },
    { id: 'b', type: 'card', position: { x: 600, y: 0 }, data: { node: { id: 'b', step: 't' } } },
  ]
  const stored = toFlowJson(nodes, [{ source: 'i', target: 'b' }, { source: 'i', target: 'a' }])

  assert.equal(stored.nodes[0].then, 'b')
  assert.equal(stored.nodes[0].otherwise, 'a')
  const again = fromFlowJson(stored)
  assert.deepEqual(again.edges.map((e) => [e.source, e.target]), [['i', 'b'], ['i', 'a']])
})

test('the first node a for each connects to becomes its body, and that wire is not stored as an edge', () => {
  const nodes = [
    { id: 'e', type: 'card', position: { x: 0, y: 0 }, data: { node: { id: 'e', kind: 'foreach', fields: {} } } },
    { id: 'x', type: 'card', position: { x: 300, y: 0 }, data: { node: { id: 'x', step: 's' } } },
    { id: 'z', type: 'card', position: { x: 600, y: 0 }, data: { node: { id: 'z', step: 't' } } },
  ]
  const stored = toFlowJson(nodes, [{ source: 'e', target: 'x' }, { source: 'e', target: 'z' }])

  assert.equal(stored.nodes[0].body, 'x')
  assert.deepEqual(stored.edges, [['e', 'z']])
})

const card = (id, node) => ({ id, type: 'card', position: { x: 0, y: 0 }, data: { node: { id, ...node } } })
const wire = (nodes, edges, source, target) => [...edges, withBranch(nodes, edges, { source, target })]

test('deleting the true target of an if never turns its false path into the true one', () => {
  const nodes = [card('i', { kind: 'if', fields: {} }), card('a', { step: 's' }), card('b', { step: 't' }), card('c', { step: 'u' })]
  let edges = wire(nodes, [], 'i', 'a')
  edges = wire(nodes, edges, 'i', 'b')
  assert.deepEqual(edges.map((e) => e.label), ['yes', 'no'])

  edges = edges.filter((e) => e.target !== 'a')
  const stored = toFlowJson(nodes.filter((n) => n.id !== 'a'), edges).nodes[0]
  assert.deepEqual([stored.then, stored.otherwise], [null, 'b'])

  const rewired = toFlowJson(nodes, wire(nodes, edges, 'i', 'c')).nodes[0] // the next wire takes the free path
  assert.deepEqual([rewired.then, rewired.otherwise], ['c', 'b'])
  const reopened = fromFlowJson({ nodes: [stored, { id: 'b', step: 't' }], edges: [['i', 'b']] })
  assert.deepEqual(reopened.edges.map((e) => e.label), ['no'])
})

test('deleting the body of a for each never promotes the next wire to body', () => {
  const nodes = [card('e', { kind: 'foreach', fields: {} }), card('x', { step: 's' }), card('z', { step: 't' })]
  let edges = wire(nodes, [], 'e', 'x')
  edges = wire(nodes, edges, 'e', 'z')

  const stored = toFlowJson(nodes.filter((n) => n.id !== 'x'), edges.filter((e) => e.target !== 'x'))

  assert.deepEqual([stored.nodes[0].body, stored.edges], [null, [['e', 'z']]])
})

test('where the person put each node is stored and used again', () => {
  const nodes = [{ ...card('a', { step: 's' }), position: { x: 520.4, y: 240 } }]
  const stored = toFlowJson(nodes, [])

  assert.deepEqual(stored.positions, { a: { x: 520, y: 240 } })
  assert.deepEqual(fromFlowJson(stored).nodes[0].position, { x: 520, y: 240 })
})

test('a new node id never reuses one that is on the canvas', () => {
  assert.equal(nextNodeId([]), 'n1')
  assert.equal(nextNodeId([{ id: 'n1' }, { id: 'n3' }]), 'n4')
  assert.equal(nextNodeId([{ id: 'custom' }, { id: 'n2' }]), 'n3')
})

test('a stored flow is laid out top to bottom by distance from the start, each box under what leads to it', () => {
  const at = autoLayout(['a', 'b', 'c'], [['a', 'b'], ['b', 'c']])

  assert.ok(at.a.y < at.b.y && at.b.y < at.c.y)
  assert.ok(at.a.x === at.b.x && at.b.x === at.c.x)
})

test('the two paths of a decision sit side by side under it, the first on the left, and meet below it', () => {
  const at = autoLayout(['d', 'no', 'yes', 'end'], [['d', 'yes'], ['d', 'no'], ['yes', 'end'], ['no', 'end']])

  assert.equal(at.yes.y, at.no.y)
  assert.ok(at.yes.x < at.d.x && at.d.x < at.no.x)
  assert.ok(at.no.x - at.yes.x >= 260) // wider than a box: they never overlap
  assert.equal(at.end.x, at.d.x)
  assert.ok(at.end.y > at.yes.y)
})

test('boxes that nothing leads to start side by side at the top', () => {
  const at = autoLayout(['a', 'b'], [])

  assert.equal(at.a.y, at.b.y)
  assert.ok(Math.abs(at.a.x - at.b.x) >= 260)
})

test('a wire drawn in a loop does not hang the layout', () => {
  const at = autoLayout(['a', 'b'], [['a', 'b'], ['b', 'a']])

  assert.equal(Object.keys(at).length, 2)
})

const bare = (id, kind) => ({ id, data: { node: { id, kind } } })
const wires = (edges) => edges.map((e) => [e.source, e.target, e.data?.branch ?? null])

test('connecting in order wires after the for each, never out of its body', () => {
  const nodes = [bare('n1', 'foreach'), bare('n2'), bare('n3')]
  const body = withBranch(nodes, [], { source: 'n1', target: 'n2' })
  assert.deepEqual(wires(chainLoose(nodes, [body])), [['n1', 'n2', 'body'], ['n1', 'n3', 'next']])
})

test('connecting in order wires into the for each, never into its body', () => {
  const nodes = [bare('n1'), bare('n2'), bare('n3', 'foreach')]
  const body = withBranch(nodes, [], { source: 'n3', target: 'n2' })
  assert.deepEqual(wires(chainLoose(nodes, [body])), [['n3', 'n2', 'body'], ['n1', 'n3', null]])
})

// a canvas built only by adding boxes, as the panel does
const built = (...adds) => adds.reduce((canvas, [id, kind, options]) => joinBoxes(canvas.nodes, canvas.edges,
  [{ id, type: 'card', data: { node: { id, kind } } }], options), { nodes: [], edges: [] })
const at = (canvas, id) => canvas.nodes.find((n) => n.id === id).position
const joined = (canvas) => wires(canvas.edges).sort()

test('a new box joins after the last one and sits under it', () => {
  const canvas = built(['a'], ['b'], ['c'])

  assert.deepEqual(joined(canvas), [['a', 'b', null], ['b', 'c', null]])
  assert.ok(at(canvas, 'a').y < at(canvas, 'b').y && at(canvas, 'b').y < at(canvas, 'c').y)
  assert.equal(at(canvas, 'a').x, at(canvas, 'c').x)
})

test('a new box joins after the chosen one, before what followed it, and what followed moves down', () => {
  const canvas = built(['a'], ['b'], ['c'], ['x', 'step', { after: 'a' }])

  assert.deepEqual(joined(canvas), [['a', 'x', null], ['b', 'c', null], ['x', 'b', null]])
  assert.ok(at(canvas, 'a').y < at(canvas, 'x').y && at(canvas, 'x').y < at(canvas, 'b').y && at(canvas, 'b').y < at(canvas, 'c').y)
  assert.equal(at(canvas, 'x').x, at(canvas, 'a').x)
})

test('a decision takes yes then no, and a third box goes into the yes path', () => {
  const two = built(['d', 'if'], ['y'], ['n', 'step', { after: 'd' }])
  assert.deepEqual(joined(two), [['d', 'n', 'otherwise'], ['d', 'y', 'then']])
  assert.ok(at(two, 'y').x < at(two, 'd').x && at(two, 'd').x < at(two, 'n').x)

  const three = joinBoxes(two.nodes, two.edges, [{ id: 'z', data: { node: { id: 'z' } } }], { after: 'd' })
  assert.deepEqual(joined(three), [['d', 'n', 'otherwise'], ['d', 'z', 'then'], ['z', 'y', null]])
})

test('a repeat takes the next action as what it repeats, and the one after that follows the repeat', () => {
  const canvas = built(['r', 'foreach'], ['body'], ['after'])

  assert.deepEqual(joined(canvas), [['r', 'after', 'next'], ['r', 'body', 'body']])
  // choosing the repeated action stands for its repeat: it takes no lines of its own
  const more = joinBoxes(canvas.nodes, canvas.edges, [{ id: 'x', data: { node: { id: 'x' } } }], { after: 'body' })
  assert.deepEqual(joined(more), [['r', 'body', 'body'], ['r', 'x', 'next'], ['x', 'after', null]])
})

test('only an action becomes what a repeat repeats, and never one that already has lines', () => {
  assert.deepEqual(joined(built(['r', 'foreach'], ['w', 'wait'])), [['r', 'w', 'next']])
  const inserted = built(['a'], ['b'], ['r', 'foreach', { after: 'a' }])
  assert.deepEqual(joined(inserted), [['a', 'r', null], ['r', 'b', 'next']])
})

test('a start box is joined before the first box, never after the last one', () => {
  const canvas = built(['a'], ['b'], ['t', 'trigger'])

  assert.deepEqual(joined(canvas), [['a', 'b', null], ['t', 'a', null]])
  assert.ok(at(canvas, 't').y < at(canvas, 'a').y)
  const next = joinBoxes(canvas.nodes, canvas.edges, [{ id: 'c', data: { node: { id: 'c' } } }])
  assert.ok(joined(next).some(([source, target]) => source === 'b' && target === 'c'))
})

test('a dropped box stays where it was dropped and still joins', () => {
  const canvas = built(['a'], ['b', 'step', { at: { x: 900, y: 20 } }])

  assert.deepEqual(at(canvas, 'b'), { x: 900, y: 20 })
  assert.deepEqual(joined(canvas), [['a', 'b', null]])
})

test('several boxes added at once join as one chain', () => {
  const start = built(['a'])
  const canvas = joinBoxes(start.nodes, start.edges, ['h1', 'h2'].map((id) => ({ id, data: { node: { id } } })))

  assert.deepEqual(joined(canvas), [['a', 'h1', null], ['h1', 'h2', null]])
  assert.ok(at(canvas, 'h1').y < at(canvas, 'h2').y)
})

test('a decision never gets a third line, and a repeated box none of its own', () => {
  const canvas = built(['d', 'if'], ['y'], ['n', 'step', { after: 'd' }], ['r', 'foreach', { after: 'n' }], ['b'])
  const extra = [...canvas.nodes, { id: 'e', data: { node: { id: 'e' } } }]

  assert.equal(withBranch(extra, canvas.edges, { source: 'd', target: 'e' }), null)
  assert.equal(withBranch(extra, canvas.edges, { source: 'e', target: 'b' }), null)
  assert.equal(withBranch(extra, canvas.edges, { source: 'b', target: 'e' }), null)
})

test('boxes are numbered in the order they are read, and the start box is not counted', () => {
  const canvas = built(['t', 'trigger'], ['a'], ['d', 'if'], ['y'], ['n', 'step', { after: 'd' }])

  assert.deepEqual(boxNumbers(canvas.nodes, canvas.edges), { a: 1, d: 2, y: 3, n: 4 })
})
