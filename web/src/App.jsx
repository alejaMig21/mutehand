import { useCallback, useEffect, useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, addEdge, useEdgesState, useNodesState } from '@xyflow/react'
import { api } from './api.js'
import { fromFlowJson, layout, nextNodeId, toFlowJson } from './flowjson.js'

const INPUT_TYPES = ['str', 'int', 'float', 'bool']

export default function App() {
  const [lessons, setLessons] = useState([])
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

  const refreshFlows = useCallback(() => api('/api/flows').then(setFlows).catch((e) => setError(e.message)), [])

  useEffect(() => {
    api('/api/lessons').then(setLessons).catch((e) => setError(e.message))
    refreshFlows()
  }, [refreshFlows])

  const onConnect = useCallback((connection) => setEdges((current) => addEdge(connection, current)), [setEdges])

  function addLesson(lesson) {
    setNodes((current) => [
      ...current,
      {
        id: nextNodeId(current),
        position: layout(current.length),
        data: { label: lesson.name, lesson: lesson.name, inputs: [], exclusive_input: false },
      },
    ])
  }

  function updateSelected(patch) {
    setNodes((current) =>
      current.map((n) => (n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n)),
    )
  }

  async function openFlow(id) {
    setError('')
    try {
      const loaded = fromFlowJson(await api(`/api/flows/${id}`))
      setNodes(loaded.nodes)
      setEdges(loaded.edges)
      setFlowId(id)
      setSelectedId(null)
      setStatuses({})
      setStatus('')
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
  const shownNodes = useMemo(
    () => nodes.map((n) => ({ ...n, className: `status-${statuses[n.id] ?? 'pending'}` })),
    [nodes, statuses],
  )

  return (
    <div className="app">
      <div className="panel">
        <h2>Lessons</h2>
        {lessons.map((lesson) => (
          <button
            key={`${lesson.app}/${lesson.name}`}
            className={`palette-item${lesson.sensitive ? ' sensitive' : ''}`}
            data-testid={`palette-${lesson.name}`}
            onClick={() => addLesson(lesson)}
          >
            {lesson.name}{' '}
            <small>
              {lesson.app} · {lesson.origin}
              {lesson.sensitive ? ' · needs consent' : ''}
            </small>
          </button>
        ))}
        <h2>Flows</h2>
        {flows.map((flow) => (
          <button key={flow.id} className="palette-item" data-testid={`flow-${flow.id}`} onClick={() => openFlow(flow.id)}>
            {flow.id} <small>{flow.origin}</small>
          </button>
        ))}
      </div>

      <div className="canvas">
        <ReactFlow
          nodes={shownNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedId(node.id)}
          onPaneClick={() => setSelectedId(null)}
          fitView
        >
          <Background />
          <Controls />
        </ReactFlow>
      </div>

      <div className="panel right">
        <h2>Flow</h2>
        <div className="row"><input aria-label="flow id" data-testid="flow-id" value={flowId} onChange={(e) => setFlowId(e.target.value)} /></div>
        <div className="row"><input aria-label="app" data-testid="app-name" value={appName} onChange={(e) => setAppName(e.target.value)} /></div>
        <div className="row"><textarea aria-label="run context" data-testid="context" value={context} onChange={(e) => setContext(e.target.value)} rows={3} style={{ flex: 1 }} /></div>
        <div className="row">
          <button data-testid="save" onClick={save}>Save</button>
          <button data-testid="run" onClick={run} disabled={running}>Run</button>
        </div>
        <div className="status-line" data-testid="run-status">{status}</div>
        {error && <div className="error" data-testid="error">{error}</div>}

        {selected && (
          <>
            <h2>Node {selected.id}</h2>
            <div>Lesson: <b>{selected.data.lesson}</b></div>
            <label>
              <input type="checkbox" data-testid="exclusive" checked={selected.data.exclusive_input}
                onChange={(e) => updateSelected({ exclusive_input: e.target.checked })} />
              needs the mouse or keyboard
            </label>
            <h2>Typed inputs</h2>
            {selected.data.inputs.map(([name, type], i) => (
              <div className="row" key={i}>
                <input aria-label="input name" value={name} onChange={(e) =>
                  updateSelected({ inputs: selected.data.inputs.map((p, j) => (j === i ? [e.target.value, p[1]] : p)) })} />
                <select aria-label="input type" value={type} onChange={(e) =>
                  updateSelected({ inputs: selected.data.inputs.map((p, j) => (j === i ? [p[0], e.target.value] : p)) })}>
                  {INPUT_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
            ))}
            <button data-testid="add-input" onClick={() => updateSelected({ inputs: [...selected.data.inputs, ['value', 'str']] })}>
              Add input
            </button>
          </>
        )}
      </div>
    </div>
  )
}
