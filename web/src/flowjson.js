// Pure helpers (no browser APIs), so node's test runner can check them.

// Where the i-th node sits on the canvas: a grid of four columns.
export const layout = (i) => ({ x: 60 + (i % 4) * 220, y: 60 + Math.floor(i / 4) * 120 })

// n1, n3 -> n4: never reuse an id that is already on the canvas.
export function nextNodeId(nodes) {
  const numbers = nodes.map((n) => Number(n.id.replace(/^n/, ''))).filter(Number.isFinite)
  return `n${Math.max(0, ...numbers) + 1}`
}

// The graph the editor edits <-> the flow JSON the API stores.
export function toFlowJson(nodes, edges) {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      step: n.data.step,
      inputs: n.data.inputs,
      exclusive_input: n.data.exclusive_input,
    })),
    edges: edges.map((e) => [e.source, e.target]),
  }
}

export function fromFlowJson(flow) {
  const nodes = flow.nodes.map((n, i) => ({
    id: n.id,
    position: layout(i),
    data: {
      label: n.step,
      step: n.step,
      inputs: n.inputs ?? [],
      exclusive_input: Boolean(n.exclusive_input),
    },
  }))
  return { nodes, edges: (flow.edges ?? []).map(([source, target]) => ({ id: `${source}-${target}`, source, target })) }
}
