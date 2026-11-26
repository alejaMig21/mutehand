// Pure helpers (no browser APIs), so node's test runner can check them.
//
// The canvas keeps, for every node, the whole node the API stores in `data.node`. Saving writes it back untouched except for
// what the wires say: the targets of an `if` become its then / otherwise, and the first node a `for each` connects to
// becomes its body (a body is owned by its for each, so that wire is not stored as an edge).

// Where the i-th node sits on the canvas when nothing else says: a grid of four columns.
export const layout = (i) => ({ x: 60 + (i % 4) * 230, y: 60 + Math.floor(i / 4) * 150 })

// A stored flow has no positions: lay the nodes out in columns by how far they are from the start, so the wires run left to right.
export function autoLayout(ids, edges) {
  const depth = Object.fromEntries(ids.map((id) => [id, 0]))
  for (let pass = 0; pass < ids.length; pass++) { // bounded: a wire drawn in a loop cannot spin forever
    let moved = false
    for (const [source, target] of edges) {
      if (depth[source] + 1 > depth[target] && depth[source] + 1 < ids.length) { depth[target] = depth[source] + 1; moved = true }
    }
    if (!moved) break
  }
  const rows = {}
  return Object.fromEntries(ids.map((id) => {
    const row = rows[depth[id]] ?? 0
    rows[depth[id]] = row + 1
    return [id, { x: 60 + depth[id] * 250, y: 60 + row * 140 }]
  }))
}

// n1, n3 -> n4: never reuse an id that is already on the canvas.
export function nextNodeId(nodes) {
  const numbers = nodes.map((n) => Number(n.id.replace(/^n/, ''))).filter(Number.isFinite)
  return `n${Math.max(0, ...numbers) + 1}`
}

const targetsOf = (edges) => {
  const out = new Map()
  for (const e of edges) out.set(e.source, [...(out.get(e.source) ?? []), e.target])
  return out
}

// The graph the editor edits -> the flow JSON the API stores.
export function toFlowJson(nodes, edges) {
  const out = targetsOf(edges)
  const bodies = new Set()
  const stored = nodes.map((n) => {
    const node = { ...n.data.node }
    const targets = out.get(n.id) ?? []
    if (node.kind === 'if') {
      node.then = targets[0] ?? null
      node.otherwise = targets[1] ?? null
    }
    if (node.kind === 'foreach') {
      node.body = targets[0] ?? null
      if (targets[0]) bodies.add(`${n.id}>${targets[0]}`)
    }
    return node
  })
  return {
    nodes: stored,
    edges: edges.filter((e) => !bodies.has(`${e.source}>${e.target}`)).map((e) => [e.source, e.target]),
  }
}

// What the API stores -> the graph the editor edits. `lookup(step)` may give extra facts about a step (app, sensitive).
export function fromFlowJson(flow, lookup = () => ({})) {
  const owned = new Set(flow.nodes.filter((n) => n.kind === 'foreach' && n.body).map((n) => n.body))
  // no stored edges means "one after another" (a body only runs inside its for each)
  const chain = flow.nodes.filter((n) => !owned.has(n.id))
  const stored = flow.edges ?? chain.slice(1).map((n, i) => [chain[i].id, n.id])
  const front = [] // the wires that mean something by their order come first
  for (const n of flow.nodes) {
    if (n.kind === 'foreach' && n.body) front.push([n.id, n.body])
    if (n.kind === 'if') for (const target of [n.then, n.otherwise]) if (target) front.push([n.id, target])
  }
  const pairs = [...front, ...stored]
  const positions = autoLayout(flow.nodes.map((n) => n.id), pairs)
  const nodes = flow.nodes.map((n) => {
    const node = { ...n, inputs: n.inputs ?? [], exclusive_input: Boolean(n.exclusive_input) }
    return { id: n.id, type: 'card', position: positions[n.id], data: { node, meta: lookup(n.step) } }
  })
  const seen = new Set()
  const edges = pairs.filter(([s, t]) => !seen.has(`${s}>${t}`) && seen.add(`${s}>${t}`))
    .map(([source, target]) => ({ id: `${source}-${target}`, source, target }))
  return { nodes, edges }
}
