// Pure helpers (no browser APIs), so node's test runner can check them.
//
// The canvas keeps, for every node, the whole node the API stores in `data.node`. Saving writes it back untouched except for
// what the wires say: each wire out of an `if` is its yes or no path, and one wire out of a `for each` is its body (a body
// is owned by its for each, so that wire is not stored as an edge). A wire keeps its meaning in `data.branch`, so deleting
// another wire or node never changes it.

// The canvas reads top to bottom: one row per node in a chain, columns for what runs side by side.
const CARD_WIDTH = 260 // as in styles.css
const X_STEP = 330
const Y_STEP = 160
const START = 60
const mean = (numbers) => numbers.reduce((sum, n) => sum + n, 0) / numbers.length

// A stored flow may have no positions: lay the nodes out in rows by how far they are from the start, so the wires run
// top to bottom. A node sits under what leads to it; those that would share a place spread around it, in wire order.
export function autoLayout(ids, edges) {
  const depth = Object.fromEntries(ids.map((id) => [id, 0]))
  for (let pass = 0; pass < ids.length; pass++) { // bounded: a wire drawn in a loop cannot spin forever
    let moved = false
    for (const [source, target] of edges) {
      if (depth[source] + 1 > depth[target] && depth[source] + 1 < ids.length) { depth[target] = depth[source] + 1; moved = true }
    }
    if (!moved) break
  }
  const at = {}
  for (let level = 0; level < ids.length; level++) {
    const row = ids.filter((id) => depth[id] === level).map((id) => {
      const above = edges.map(([source, target], order) => ({ source, target, order }))
        .filter((e) => e.target === id && at[e.source])
      return { id, want: above.length ? mean(above.map((e) => at[e.source].x)) : START,
        order: above.length ? above[0].order : ids.indexOf(id) }
    }).sort((a, b) => a.want - b.want || a.order - b.order)
    if (!row.length) continue
    let last = -Infinity
    const places = row.map((node) => { last = Math.max(node.want, last + X_STEP); return last })
    const shift = mean(row.map((node) => node.want)) - mean(places)
    row.forEach((node, i) => { at[node.id] = { x: Math.round(places[i] + shift), y: START + level * Y_STEP } })
  }
  return at
}

// n1, n3 -> n4: never reuse an id that is already on the canvas.
export function nextNodeId(nodes) {
  const numbers = nodes.map((n) => Number(n.id.replace(/^n/, ''))).filter(Number.isFinite)
  return `n${Math.max(0, ...numbers) + 1}`
}

const BRANCHES = { if: ['then', 'otherwise'], foreach: ['body'] }
const LABELS = { then: 'yes', otherwise: 'no', body: 'each item' }

const marked = (edge, branch) => ({ ...edge, data: { ...edge.data, branch }, ...(LABELS[branch] ? { label: LABELS[branch] } : {}) })

const kindOf = (node) => node?.data.node.kind ?? 'step'
// repeated node -> the repeat that owns it
const bodiesOf = (edges) => new Map(edges.filter((e) => e.data?.branch === 'body').map((e) => [e.target, e.source]))

// A new wire takes the first meaning its source still has free: yes then no for a decision, and for a repeat the step
// it repeats (one with no wires of its own), then 'next', an ordinary wire. null when the wire cannot be drawn: a third
// path out of a decision would never run, and a repeated node has no wires of its own.
export function withBranch(nodes, edges, connection) {
  const { source, target } = connection
  const bodies = bodiesOf(edges)
  if (bodies.has(source) || bodies.has(target)) return null
  const edge = { id: `${source}-${target}`, ...connection }
  const kind = kindOf(nodes.find((n) => n.id === source))
  if (!BRANCHES[kind]) return edge
  const taken = new Set(edges.filter((e) => e.source === source).map((e) => e.data?.branch))
  const repeatable = () => kindOf(nodes.find((n) => n.id === target)) === 'step'
    && !edges.some((e) => e.source === target || e.target === target)
  const free = BRANCHES[kind].find((branch) => !taken.has(branch) && (branch !== 'body' || repeatable()))
  if (free) return marked(edge, free)
  return kind === 'if' ? null : marked(edge, 'next')
}

// Nodes with no wire at all, when there is more than one node and something to run: they would all run at the same time.
export function looseNodes(nodes, edges) {
  const wired = new Set(edges.flatMap((e) => [e.source, e.target]))
  const some = nodes.length > 1 && nodes.some((n) => kindOf(n) !== 'trigger') // start nodes alone have nothing to join
  return some ? nodes.filter((n) => !wired.has(n.id)) : []
}

// Wire each loose node after the nearest one added before it that can take a wire. A start node counts as added first:
// it is wired from, never into.
export function chainLoose(nodes, edges) {
  const loose = new Set(looseNodes(nodes, edges).map((n) => n.id))
  const isStart = (n) => kindOf(n) === 'trigger'
  const ordered = [...nodes.filter(isStart), ...nodes.filter((n) => !isStart(n))]
  let wired = edges
  ordered.forEach((node, i) => {
    if (!loose.has(node.id)) return
    const owner = bodiesOf(wired) // a body takes no wires of its own: its for each stands in for it
    const pairs = i > 0 && !isStart(node) ? ordered.slice(0, i).reverse().map((n) => [n.id, node.id])
      : ordered.filter((n) => n !== node && !isStart(n)).map((n) => [node.id, n.id])
    for (const pair of pairs) {
      const [source, target] = pair.map((id) => owner.get(id) ?? id)
      if (source === target) continue
      if (wired.some((e) => e.source === source && e.target === target)) return
      const wire = withBranch(nodes, wired, { source, target })
      if (wire) { wired = [...wired, wire]; return }
    }
  })
  return wired
}

// The node a new one goes after when none is chosen: the lowest that nothing follows, the newest on a tie.
function lastNode(nodes, edges) {
  const bodies = bodiesOf(edges)
  const followed = new Set(edges.filter((e) => e.data?.branch !== 'body').map((e) => e.source))
  return nodes.filter((n) => !bodies.has(n.id) && !followed.has(n.id))
    .reduce((lowest, n) => (!lowest || n.position.y >= lowest.position.y ? n : lowest), undefined)
}

// The place asked for, moved to the right while a node is already there.
function freeSpot(nodes, { x, y }) {
  let right = x
  while (nodes.some((n) => Math.abs(n.position.x - right) < CARD_WIDTH && Math.abs(n.position.y - y) < Y_STEP / 2)) right += X_STEP
  return { x: right, y }
}

// A flow starts at a start node: it goes above, and leads to every node that nothing but a start leads to.
function joinStart(nodes, edges, start, at) {
  const bodies = bodiesOf(edges)
  const starts = (id) => kindOf(nodes.find((n) => n.id === id)) === 'trigger'
  const first = nodes.filter((n) => kindOf(n) !== 'trigger' && !bodies.has(n.id)
    && edges.every((e) => e.target !== n.id || starts(e.source)))
  const above = first.length ? { x: first[0].position.x, y: first[0].position.y - Y_STEP } : { x: START, y: START }
  return {
    nodes: [...nodes, { ...start, position: at ?? freeSpot(nodes, above) }],
    edges: [...edges, ...first.map((n) => ({ id: `${start.id}-${n.id}`, source: start.id, target: n.id }))],
  }
}

// New nodes (one, or a chain) join after the chosen node, or after the last one: what followed it now follows them and
// moves down to make room. `at` is where the person dropped the first of them; a dropped node moves nothing.
export function joinNodes(nodes, edges, added, { after, at } = {}) {
  if (kindOf(added[0]) === 'trigger') return joinStart(nodes, edges, added[0], at)
  const byId = (id) => nodes.find((n) => n.id === id)
  let anchor = byId(after) ?? lastNode(nodes, edges)
  const owner = bodiesOf(edges)
  if (anchor && owner.has(anchor.id)) anchor = byId(owner.get(anchor.id))
  const all = [...nodes, ...added]
  let wired = edges
  for (let i = 1; i < added.length; i++) {
    wired = [...wired, withBranch(all, wired, { source: added[i - 1].id, target: added[i].id })]
  }
  let followers = []
  if (anchor) {
    const [head, end] = [added[0].id, added[added.length - 1]]
    let first = withBranch(all, wired, { source: anchor.id, target: head })
    if (!first) { // a decision with both paths taken: the new nodes go into its yes path
      followers = [wired.find((e) => e.source === anchor.id && e.data?.branch === 'then').target]
      first = marked({ id: `${anchor.id}-${head}`, source: anchor.id, target: head }, 'then')
    } else if (kindOf(anchor) !== 'if' && first.data?.branch !== 'body') {
      followers = wired.filter((e) => e.source === anchor.id && e.data?.branch !== 'body').map((e) => e.target)
    }
    const moved = wired.filter((e) => e.source === anchor.id && followers.includes(e.target))
    wired = [...wired.filter((e) => !moved.includes(e)), first]
    for (const old of moved) {
      const link = { id: `${end.id}-${old.target}`, source: end.id, target: old.target }
      // what followed a node is never what a repeat repeats; a decision with no path left leaves the wire where it was
      wired = [...wired, (kindOf(end) === 'foreach' ? marked(link, 'next') : withBranch(all, wired, link)) ?? old]
    }
    if (kindOf(anchor) === 'trigger') { // other start nodes that lead nowhere yet lead here too
      const idle = nodes.filter((n) => kindOf(n) === 'trigger' && !wired.some((e) => e.source === n.id))
      wired = [...wired, ...idle.map((n) => ({ id: `${n.id}-${head}`, source: n.id, target: head }))]
    }
  }
  let placed = nodes
  if (followers.length && !at) {
    const room = anchor.position.y + (added.length + 1) * Y_STEP - Math.min(...followers.map((id) => byId(id).position.y))
    const below = new Set(followers)
    for (const id of below) for (const e of edges) if (e.source === id) below.add(e.target) // the set grows as it is walked
    if (room > 0) {
      placed = nodes.map((n) => (below.has(n.id) ? { ...n, position: { x: n.position.x, y: n.position.y + room } } : n))
    }
  }
  const aside = anchor && BRANCHES[kindOf(anchor)] ? X_STEP / 2 : 0
  const start = at ?? (anchor ? { x: anchor.position.x - aside, y: anchor.position.y + Y_STEP } : { x: START, y: START })
  added.forEach((node, i) => {
    const spot = { x: start.x, y: start.y + i * Y_STEP }
    placed = [...placed, { ...node, position: at && i === 0 ? at : freeSpot(placed, spot) }]
  })
  return { nodes: placed, edges: wired }
}

// The number each node carries, in the order the canvas is read: after what leads to it, higher and further left first.
// Start nodes are not counted.
export function nodeNumbers(nodes, edges) {
  const left = [...nodes]
  const numbers = {}
  let next = 1
  while (left.length) {
    const ready = left.filter((n) => !edges.some((e) => e.target === n.id && left.some((other) => other.id === e.source)))
    const [node] = [...(ready.length ? ready : left)].sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x)
    left.splice(left.indexOf(node), 1)
    if (kindOf(node) !== 'trigger') numbers[node.id] = next++
  }
  return numbers
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

// What keeps stored nodes (as toFlowJson gives them) from being kept yet, in words; '' when nothing does. The server refuses a
// choice with no yes path and a repeat with nothing to repeat, and a node added a moment ago is exactly that. `numbers` is
// what nodeNumbers gives: the node is named by the number the person sees on it.
export function unfinished(stored, numbers = {}) {
  for (const node of stored) {
    const which = numbers[node.id] ? `Node ${numbers[node.id]}: ` : ''
    if (node.kind === 'if' && !node.then) return `${which}A two-paths node needs a line to its yes path.`
    if (node.kind === 'foreach' && !node.body) return `${which}A repeat node needs the step it repeats: connect it to one.`
  }
  return ''
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
