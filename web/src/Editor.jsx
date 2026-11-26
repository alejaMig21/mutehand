import { useCallback, useEffect, useMemo, useState } from 'react'
import { ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, addEdge, useEdgesState, useNodesState, useReactFlow } from '@xyflow/react'
import { api } from './api.js'
import { fromFlowJson, layout, nextNodeId, toFlowJson } from './flowjson.js'
import { Icon } from './icons.jsx'
import { refOptions } from './bindings.js'
import { titleOf } from './catalog.js'
import NodeCard from './NodeCard.jsx'
import NodeDetail from './NodeDetail.jsx'
import SearchPanel from './SearchPanel.jsx'

const NODE_TYPES = { card: NodeCard }
// the search panel floats over the right edge, so the nodes are fitted into what is left
const FIT = { maxZoom: 1, padding: { top: '60px', left: '60px', bottom: '60px', right: '440px' } }

export default function Editor() {
  return <ReactFlowProvider><EditorScreen /></ReactFlowProvider>
}

function EditorScreen() {
  const { fitView } = useReactFlow()
  const [steps, setSteps] = useState([])
  const [flows, setFlows] = useState([])
  const [flowId, setFlowId] = useState('my-flow')
  const [appName, setAppName] = useState('mspaint.exe')
  const [context, setContext] = useState('{}')
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedId, setSelectedId] = useState(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [statuses, setStatuses] = useState({})
  const [running, setRunning] = useState(false)
  const [panelOpen, setPanelOpen] = useState(true)
  const [flowsOpen, setFlowsOpen] = useState(false)
  const [runDataOpen, setRunDataOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [nodeData, setNodeData] = useState({})
  const [showValues, setShowValues] = useState(false)
  const [view, setView] = useState(0) // bumped when another flow is shown, so the canvas fits it

  const refreshFlows = useCallback(() => api('/api/flows').then(setFlows).catch((e) => setError(e.message)), [])

  useEffect(() => {
    api('/api/steps').then(setSteps).catch((e) => setError(e.message))
    refreshFlows()
  }, [refreshFlows])

  // The Data of the last run (or test) of each node. Only shapes unless the person asked to see the values.
  const loadData = useCallback(async (values) => {
    try {
      setNodeData(await api(`/api/flows/${flowId}/data${values ? '?values=1' : ''}`))
    } catch {
      setNodeData({}) // an unsaved flow has none yet
    }
  }, [flowId])

  const onConnect = useCallback((connection) => setEdges((current) => addEdge(connection, current)), [setEdges])

  // Like n8n: a node added while another is selected goes to its right and is wired after it.
  const addNode = (node, meta = {}) => {
    const id = nextNodeId(nodes)
    const after = nodes.find((n) => n.id === selectedId)
    const position = after ? { x: after.position.x + 250, y: after.position.y } : layout(nodes.length)
    setNodes((current) => [...current, {
      id, type: 'card', position, data: { node: { ...node, id, inputs: [], exclusive_input: false }, meta },
    }])
    if (after) setEdges((current) => addEdge({ source: after.id, target: id }, current))
    setSelectedId(null)
    setTimeout(() => fitView({ ...FIT, duration: 200 }), 60) // once the new node is on the canvas
  }

  const addStep = (step) => addNode({ step: step.name }, { app: step.app, sensitive: step.sensitive, origin: step.origin, action: step.action })
  const addSystem = (entry) => addNode(structuredClone(entry.node))

  function updateSelected(patch) {
    setNodes((current) => current.map((n) => (n.id === selectedId
      ? { ...n, data: { ...n.data, node: { ...n.data.node, ...patch } } } : n)))
  }

  function deleteSelected() {
    setNodes((current) => current.filter((n) => n.id !== selectedId))
    setEdges((current) => current.filter((e) => e.source !== selectedId && e.target !== selectedId))
    setSelectedId(null)
  }

  const lookup = (name) => {
    const step = steps.find((s) => s.name === name)
    return step ? { app: step.app, sensitive: step.sensitive, origin: step.origin, action: step.action } : {}
  }

  async function openFlow(id) {
    setError('')
    try {
      const loaded = fromFlowJson(await api(`/api/flows/${id}`), lookup)
      setNodes(loaded.nodes)
      setEdges(loaded.edges)
      setFlowId(id)
      setSelectedId(null)
      setStatuses({})
      setStatus('saved') // what is stored is what is shown
      setFlowsOpen(false)
      setView((v) => v + 1)
    } catch (e) {
      setError(e.message)
    }
  }

  function newFlow() {
    setNodes([])
    setEdges([])
    setSelectedId(null)
    setStatuses({})
    setStatus('')
    setFlowsOpen(false)
    setView((v) => v + 1)
  }

  // A factory template is read-only: a copy in the user layer is what the person edits.
  async function duplicate(id) {
    setError('')
    const taken = new Set(flows.map((flow) => flow.id))
    let copyId = `${id}-copy`
    for (let n = 2; taken.has(copyId); n++) copyId = `${id}-copy-${n}`
    try {
      await api(`/api/flows/${id}/duplicate`, { method: 'POST', body: { new_id: copyId } })
      await refreshFlows()
      await openFlow(copyId)
    } catch (e) {
      setError(e.message)
    }
  }

  async function save() {
    setError('')
    try {
      await api(`/api/flows/${flowId}`, { method: 'PUT', body: toFlowJson(nodes, edges) })
      setStatus('saved')
      refreshFlows()
    } catch (e) {
      setError(e.message)
    }
  }

  async function run() {
    if (running) return
    setError('')
    setStatuses({})
    setRunning(true)
    try {
      const values = JSON.parse(context || '{}')
      const { run_id } = await api(`/api/flows/${flowId}/run`, { method: 'POST', body: { app: appName, context: values } })
      setStatus('running')
      for (;;) {
        const view = await api(`/api/runs/${run_id}`)
        setStatuses(view.nodes)
        if (view.status !== 'running') {
          setStatus(view.status)
          loadData(showValues)
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 250))
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const selected = nodes.find((n) => n.id === selectedId)
  const selectedNode = selected?.data.node
  const runKeys = useMemo(() => {
    try { return Object.keys(JSON.parse(context || '{}')) } catch { return [] }
  }, [context])
  const openDetail = (id) => { setSelectedId(id); setDetailOpen(true); loadData(showValues) }
  const toggleValues = (on) => { setShowValues(on); loadData(on) }
  async function ensureSaved() { // a test works on the stored flow
    await api(`/api/flows/${flowId}`, { method: 'PUT', body: toFlowJson(nodes, edges) })
    refreshFlows()
  }
  const shownNodes = useMemo(
    () => nodes.map((n) => ({ ...n, className: `status-${statuses[n.id] ?? 'pending'}` })),
    [nodes, statuses],
  )

  return (
    <div className="editor">
      <header className="topbar">
        <span className="logo" aria-hidden="true"><Icon name="layers" size={20} /></span>
        <input className="flow-name" aria-label="Flow name" data-testid="flow-id" value={flowId}
          onChange={(e) => setFlowId(e.target.value)} />
        <span className={`pill pill-${status || 'none'}`} data-testid="run-status" role="status">{status || 'draft'}</span>

        <div className="menu-anchor">
          <button className="ghost" data-testid="open-flows" aria-expanded={flowsOpen} onClick={() => setFlowsOpen(!flowsOpen)}>
            <Icon name="folder" /> Flows
          </button>
          {flowsOpen && (
            <div className="menu" role="menu">
              <button className="menu-item" data-testid="new-flow" onClick={newFlow}><Icon name="plus" /> New flow</button>
              {flows.map((flow) => (
                <div className="menu-row" key={flow.id}>
                  <button className="menu-item" data-testid={`flow-${flow.id}`} onClick={() => openFlow(flow.id)}>
                    {flow.id} <small>{flow.origin}</small>
                  </button>
                  {flow.origin === 'factory' && (
                    <button className="ghost small" data-testid={`duplicate-${flow.id}`}
                      aria-label={`Duplicate template ${flow.id}`} onClick={() => duplicate(flow.id)}>
                      Duplicate to edit
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="spacer" />

        <label className="field-inline">App
          <input aria-label="App to run on" data-testid="app-name" value={appName} onChange={(e) => setAppName(e.target.value)} />
        </label>
        <div className="menu-anchor">
          <button className="ghost" data-testid="run-data" aria-expanded={runDataOpen} onClick={() => setRunDataOpen(!runDataOpen)}>
            Run data
          </button>
          {runDataOpen && (
            <div className="menu wide">
              <label htmlFor="run-context">Values the run starts with (JSON)</label>
              <textarea id="run-context" data-testid="context" value={context} rows={4} onChange={(e) => setContext(e.target.value)} />
            </div>
          )}
        </div>
        <button className="ghost" data-testid="save" onClick={save}>Save</button>
        <button className="primary" data-testid="run" onClick={run} disabled={running}>
          <Icon name="play" size={16} /> Run flow
        </button>
      </header>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}

      <div className="canvas">
        <ReactFlow
          key={view}
          nodes={shownNodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedId(node.id)}
          onNodeDoubleClick={(_, node) => openDetail(node.id)}
          onPaneClick={() => setSelectedId(null)}
          deleteKeyCode={['Backspace', 'Delete']}
          colorMode="dark"
          fitView
          fitViewOptions={FIT}
          minZoom={0.3}
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="#26384C" />
          <Controls showInteractive={false} position="bottom-center" orientation="horizontal" />
        </ReactFlow>

        {nodes.length === 0 && (
          <div className="empty-canvas">
            <p>Add your first node from the panel on the right.</p>
          </div>
        )}

        {selected && !detailOpen && (
          <section className="settings" aria-label="Selected node">
            <h2>{titleOf(selectedNode)}</h2>
            <button className="ghost small" data-testid="open-detail" onClick={() => openDetail(selected.id)}>Open details</button>
            <button className="danger small" data-testid="delete-node" onClick={deleteSelected}>
              <Icon name="trash" size={15} /> Delete node
            </button>
          </section>
        )}

        {selected && detailOpen && (
          <NodeDetail
            key={selected.id}
            node={selectedNode}
            meta={selected.data.meta}
            refs={refOptions(nodes, selected.id, runKeys, (n) => titleOf(n.data.node))}
            data={nodeData[selected.id]}
            showValues={showValues}
            onShowValues={toggleValues}
            onChange={updateSelected}
            onClose={() => setDetailOpen(false)}
            onDelete={() => { deleteSelected(); setDetailOpen(false) }}
            flowId={flowId}
            appName={appName}
            context={context}
            ensureSaved={ensureSaved}
            onTested={() => loadData(showValues)}
          />
        )}

        {panelOpen
          ? <SearchPanel steps={steps} onAddSystem={addSystem} onAddStep={addStep} onClose={() => setPanelOpen(false)} />
          : (
            <button className="open-panel" data-testid="open-panel" aria-label="Add a node" onClick={() => setPanelOpen(true)}>
              <Icon name="plus" size={20} />
            </button>
          )}
      </div>
    </div>
  )
}
