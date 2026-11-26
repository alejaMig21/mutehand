// Pure helpers (no browser APIs), so node's test runner can check them.
//
// The canvas keeps, for every node, the whole node the API stores in `data.node`. Saving writes it back untouched except for
// what the wires say: each wire out of an `if` is its true or false path, and one wire out of a `for each` is its body (a body
// is owned by its for each, so that wire is not stored as an edge). A wire keeps its meaning in `data.branch`, so deleting
// another wire or node never changes it.

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

const BRANCHES = { if: ['then', 'otherwise'], foreach: ['body'] }
const LABELS = { then: 'true', otherwise: 'false', body: 'each item' }

const marked = (edge, branch) => ({ ...edge, data: { ...edge.data, branch }, ...(LABELS[branch] ? { label: LABELS[branch] } : {}) })

// A new wire takes the first meaning its source still has free; 'next' is an ordinary wire.
export function withBranch(nodes, edges, connection) {
  const edge = { id: `${connection.source}-${connection.target}`, ...connection }
  const kind = nodes.find((n) => n.id === connection.source)?.data.node.kind
  if (!BRANCHES[kind]) return edge
  const taken = new Set(edges.filter((e) => e.source === connection.source).map((e) => e.data?.branch))
  return marked(edge, BRANCHES[kind].find((branch) => !taken.has(branch)) ?? 'next')
}

// Nodes with no wire at all, when there is more than one node: they would all run at the same time.
export function looseNodes(nodes, edges) {
  const wired = new Set(edges.flatMap((e) => [e.source, e.target]))
  return nodes.length > 1 ? nodes.filter((n) => !wired.has(n.id)) : []
}

// Wire each loose node after the one added before it.
export function chainLoose(nodes, edges) {
  const loose = new Set(looseNodes(nodes, edges).map((n) => n.id))
  let wired = edges
  nodes.forEach((node, i) => {
    if (!loose.has(node.id)) return
    // a body takes no wires of its own: its for each stands in for it
    const owner = new Map(wired.filter((e) => e.data?.branch === 'body').map((e) => [e.target, e.source]))
    const [source, target] = (i > 0 ? [nodes[i - 1].id, node.id] : [node.id, nodes[1].id]).map((id) => owner.get(id) ?? id)
    if (source !== target && !wired.some((e) => e.source === source && e.target === target)) {
      wired = [...wired, withBranch(nodes, wired, { source, target })]
    }
  })
  return wired
}

// The target of each meaningful wire of one node; wires that carry no mark yet fill the free places in order.
function pathsOf(id, kind, edges) {
  const paths = {}
  const out = edges.filter((e) => e.source === id)
  for (const e of out) if (e.data?.branch && e.data.branch !== 'next') paths[e.data.branch] = e.target
  const unmarked = out.filter((e) => !e.data?.branch)
  for (const branch of BRANCHES[kind]) if (!(branch in paths) && unmarked.length) paths[branch] = unmarked.shift().target
  return paths
}

// The graph the editor edits -> the flow JSON the API stores.
export function toFlowJson(nodes, edges) {
  const bodies = new Set()
  const stored = nodes.map((n) => {
    const node = { ...n.data.node }
    if (!BRANCHES[node.kind]) return node
    const paths = pathsOf(n.id, node.kind, edges)
    for (const branch of BRANCHES[node.kind]) node[branch] = paths[branch] ?? null
    if (node.body) bodies.add(`${n.id}>${node.body}`)
    return node
  })
  return {
    nodes: stored,
    edges: edges.filter((e) => !bodies.has(`${e.source}>${e.target}`)).map((e) => [e.source, e.target]),
    positions: Object.fromEntries(nodes.map((n) => [n.id, { x: Math.round(n.position.x), y: Math.round(n.position.y) }])),
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
  const positions = { ...autoLayout(flow.nodes.map((n) => n.id), pairs), ...flow.positions }
  const nodes = flow.nodes.map((n) => {
    const node = { ...n, inputs: n.inputs ?? [], exclusive_input: Boolean(n.exclusive_input) }
    return { id: n.id, type: 'card', position: positions[n.id], data: { node, meta: lookup(n.step) } }
  })
  const seen = new Set()
  const meaning = (source, target) => {
    const node = flow.nodes.find((n) => n.id === source)
    return BRANCHES[node?.kind]?.find((branch) => node[branch] === target) ?? (BRANCHES[node?.kind] ? 'next' : null)
  }
  const edges = pairs.filter(([s, t]) => !seen.has(`${s}>${t}`) && seen.add(`${s}>${t}`))
    .map(([source, target]) => {
      const edge = { id: `${source}-${target}`, source, target }
      const branch = meaning(source, target)
      return branch ? marked(edge, branch) : edge
    })
  return { nodes, edges }
}
