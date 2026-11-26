import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, useEdgesState, useNodesState, useReactFlow } from '@xyflow/react'
import { api, encode, UNREACHABLE } from './api.js'
import { chainLoose, fromFlowJson, layout, looseNodes, nextNodeId, toFlowJson, withBranch } from './flowjson.js'
import { Icon } from './icons.jsx'
import { refOptions } from './bindings.js'
import { appKey, appLabel, guessApp, SYSTEM_NODES, titleOf } from './catalog.js'
import NodeCard from './NodeCard.jsx'
import NodeDetail from './NodeDetail.jsx'
import NodePanel from './NodePanel.jsx'
import RunLog from './RunLog.jsx'
import SearchPanel, { DRAG_TYPE } from './SearchPanel.jsx'
import { useRuns } from './useRuns.js'
import { safetySummary, summaryMarks, whyNotRunnable } from './safety.js'
import { freshName, nameProblem, reasonWords, runWords } from './words.js'

const NODE_TYPES = { card: NodeCard }
const metaOf = (step) => ({ app: step.app, sensitive: step.sensitive, origin: step.origin, action: step.action,
  state: step.state, private: step.private, consent: step.consent, adapted_from: step.adapted_from })
// the search panel floats over the right edge, so the nodes are fitted into what is left; a narrow window needs it all
const fit = () => ({ maxZoom: 1, padding: window.innerWidth > 860
  ? { top: '60px', left: '60px', bottom: '60px', right: '440px' } : { top: '16px', left: '16px', bottom: '16px', right: '16px' } })
// after something is gone from the screen, the keyboard focus goes to what is left
const focusSoon = (...testIds) => setTimeout(() => {
  testIds.map((id) => document.querySelector(`[data-testid=${id}]`)).find(Boolean)?.focus()
}, 0)
const EMPTY_FLOW = JSON.stringify(toFlowJson([], []))
const flowUrl = (name) => `/api/flows/${encode(name)}`

export default function Editor(props) {
  return <ReactFlowProvider><EditorScreen {...props} /></ReactFlowProvider>
}

function EditorScreen({ active, onOpen, onUnsaved }) {
  const { fitView, screenToFlowPosition } = useReactFlow()
  const [steps, setSteps] = useState([])
  const [recipes, setRecipes] = useState([])
  const [flows, setFlows] = useState([])
  const [flowId, setFlowId] = useState('my-flow')
  const [origin, setOrigin] = useState({ name: null, revision: null }) // the stored flow on screen, as it was read
  const [savedJson, setSavedJson] = useState(EMPTY_FLOW)
  const [appName, setAppName] = useState('')
  const [context, setContext] = useState('{}')
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedId, setSelectedId] = useState(null)
  const [error, setError] = useState('')
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth > 860) // in a narrow window it would hide the canvas
  const [menu, setMenu] = useState(null) // 'flows' | 'data': one popover at a time
  const [detailOpen, setDetailOpen] = useState(false)
  const [nodeData, setNodeData] = useState({})
  const [showValues, setShowValues] = useState(false)
  const [doubts, setDoubts] = useState([]) // the open ones (the tutor answers them, not the editor)
  const [view, setView] = useState(0) // bumped when another flow is shown, so the canvas fits it
  const [starting, setStarting] = useState(false)
  const [opening, setOpening] = useState(false)
  const [settled, setSettled] = useState(0)
  const [said, say] = useState('') // for people who cannot see the canvas change
  const [framed, setFramed] = useState(false) // a stored flow is fitted to the window; a drawn one stays where it is put
  const busy = useRef({ saving: false, starting: false, ticket: 0, named: false })
  const { runs, offline, follow, attach, forget, patch } = useRuns(() => setSettled((n) => n + 1))

  const body = useMemo(() => toFlowJson(nodes, edges), [nodes, edges])
  const invalid = useMemo(() => nodes.flatMap((n) => Object.values(n.data.drafts ?? {}).filter(Boolean)
    .map((draft) => ({ ...draft, node: titleOf(n.data.node) }))), [nodes])
  const isStored = origin.name === flowId
  const dirty = JSON.stringify(body) !== savedJson || invalid.length > 0 || (origin.name !== null && !isStored)

  const refresh = useCallback(() => {
    const fail = (e) => setError(e.message)
    api('/api/steps').then((found) => {
      setSteps(found)
      setAppName((current) => current || found[0]?.app || '')
    }).catch(fail)
    api('/api/recipes').then(setRecipes).catch(fail)
    api('/api/flows').then((found) => {
      setFlows(found)
      if (busy.current.named) return
      busy.current.named = true // a first flow must not start with the name of a stored one
      setFlowId((current) => (current === 'my-flow' ? freshName(found.map((f) => f.id)) : current))
    }).catch(fail)
    api('/api/doubts?status=open').then(setDoubts).catch(() => setDoubts([]))
  }, [])

  // what the other screens, a run or another window changed is read again when the person comes back
  useEffect(() => {
    if (!active) return undefined
    refresh()
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [active, settled, refresh])

  useEffect(() => { onUnsaved(dirty) }, [dirty, onUnsaved])
  useEffect(() => {
    if (!dirty) return undefined
    const warn = (event) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  useEffect(() => { // popovers close with Escape or a click elsewhere
    if (!menu) return undefined
    const key = (event) => {
      if (event.key !== 'Escape') return
      setMenu(null)
      document.querySelector(`[data-testid=${menu === 'flows' ? 'open-flows' : 'run-data'}]`)?.focus()
    }
    const outside = (event) => { if (!event.target.closest('.menu-anchor')) setMenu(null) }
    window.addEventListener('keydown', key)
    window.addEventListener('pointerdown', outside)
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('pointerdown', outside) }
  }, [menu])

  // The Data of the last run (or test) of each node. Only shapes unless the person asked to see the values.
  const loadData = useCallback(async (values) => {
    try {
      setNodeData(await api(`${flowUrl(flowId)}/data${values ? '?values=1' : ''}`))
    } catch {
      setNodeData({}) // an unsaved flow has none yet
    }
  }, [flowId])
  useEffect(() => { if (settled) loadData(showValues) }, [settled]) // eslint-disable-line react-hooks/exhaustive-deps

  // after a reload, the flow the person had open comes back
  useEffect(() => {
    if (busy.current.restored || !steps.length || !flows.length) return
    busy.current.restored = true
    const last = sessionStorage.getItem('wf-flow')
    if (nodes.length === 0 && flows.some((f) => f.id === last)) show(last).catch((e) => setError(e.message))
  }, [steps, flows]) // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = useCallback((connection) => {
    setEdges((current) => (current.some((e) => e.source === connection.source && e.target === connection.target)
      ? current : [...current, withBranch(nodes, current, connection)]))
  }, [nodes, setEdges])

  const changeNodes = useCallback((changes) => { // selecting with the keyboard is selecting too
    onNodesChange(changes)
    for (const change of changes) {
      if (change.type === 'remove') { say('Node deleted'); focusSoon('search', 'open-panel') }
      if (change.type !== 'select') continue
      if (change.selected) setSelectedId(change.id)
      else setSelectedId((current) => (current === change.id ? null : current))
    }
  }, [onNodesChange])

  const refit = () => setTimeout(() => fitView({ ...fit(), duration: 200 }), 60) // once the new node is on the canvas
  const unselected = (list) => list.map((n) => ({ ...n, selected: false }))

  // Like n8n: a node added while another is selected goes to its right and is wired after it. A dropped node stays where
  // it was dropped.
  const addNode = (node, dropped) => {
    const id = nextNodeId(nodes)
    const after = dropped ? undefined : nodes.find((n) => n.id === selectedId)
    const position = dropped ?? (after ? { x: after.position.x + 250, y: after.position.y } : layout(nodes.length))
    const card = { id, type: 'card', position, data: { node: { ...node, id, inputs: [], exclusive_input: false } } }
    setNodes((current) => [...unselected(current), card])
    if (after) setEdges((current) => [...current, withBranch(nodes, current, { source: after.id, target: id })])
    setSelectedId(null)
    say(`Added ${titleOf(node)}`)
    if (!dropped) refit()
  }

  const addStep = (step, dropped) => {
    if (nodes.length === 0) setAppName(step.app) // a flow runs on one app: the first step says which
    addNode({ step: step.name }, dropped)
  }

  function drop(event) {
    const raw = event.dataTransfer.getData(DRAG_TYPE)
    if (!raw) return
    event.preventDefault()
    const entry = JSON.parse(raw)
    const at = screenToFlowPosition({ x: event.clientX, y: event.clientY })
    const system = SYSTEM_NODES.find((n) => n.key === entry.system)
    const step = steps.find((s) => s.name === entry.step && s.app === entry.app)
    if (system) addNode(structuredClone(system.node), at)
    else if (step) addStep(step, at)
  }

  // Drop a recipe: one connected node per hole, each on the step that fills the hole for the app to run on.
  // A hole nobody filled for this app gets the name its step will have, and the node says it is not filled.
  const addRecipe = (recipe) => {
    const bound = Object.entries(recipe.apps).find(([app]) => appKey(app) === appKey(appName))?.[1] ?? {}
    const after = nodes.find((n) => n.id === selectedId)
    const start = after ? { x: after.position.x + 250, y: after.position.y } : layout(nodes.length)
    let list = [...nodes]
    const added = recipe.holes.map((hole, i) => {
      const id = nextNodeId(list)
      const node = { id, step: bound[hole.hole] ?? `${recipe.name}-${hole.hole}`, inputs: [], exclusive_input: false }
      const card = { id, type: 'card', position: { x: start.x + i * 250, y: start.y }, data: { node, hole: { recipe: recipe.name, hole: hole.hole } } }
      list = [...list, card]
      return card
    })
    setNodes(unselected(list))
    setEdges((current) => {
      let wired = current
      const links = [...(after ? [[after.id, added[0].id]] : []), ...added.slice(1).map((n, i) => [added[i].id, n.id])]
      for (const [source, target] of links) wired = [...wired, withBranch(list, wired, { source, target })]
      return wired
    })
    setSelectedId(null)
    refit()
  }
  const addSystem = (entry) => addNode(structuredClone(entry.node))

  const updateNode = (id, change) => setNodes((current) => current.map((n) => (n.id === id ? { ...n, data: change(n.data) } : n)))
  const updateSelected = (change) => updateNode(selectedId, (data) => ({ ...data, node: { ...data.node, ...change } }))
  const draftSelected = (field, draft) => updateNode(selectedId, (data) => ({ ...data, drafts: { ...data.drafts, [field]: draft } }))

  function deleteSelected() {
    const gone = nodes.find((n) => n.id === selectedId)
    if (gone) say(`Deleted ${titleOf(gone.data.node)}`)
    focusSoon('search', 'open-panel')
    setNodes((current) => current.filter((n) => n.id !== selectedId))
    setEdges((current) => current.filter((e) => e.source !== selectedId && e.target !== selectedId))
    setSelectedId(null)
  }

  const mayLeave = () => !dirty || window.confirm(`“${flowId}” has changes that are not saved. Discard them?`)

  // Put a stored flow on the canvas. Only the latest request wins.
  async function show(id) {
    const ticket = ++busy.current.ticket
    setOpening(true)
    try {
      const stored = await api(flowUrl(id))
      if (ticket !== busy.current.ticket) return
      const loaded = fromFlowJson(stored)
      setNodes(loaded.nodes)
      setEdges(loaded.edges)
      setFlowId(id)
      setOrigin({ name: id, revision: stored.revision })
      setSavedJson(JSON.stringify(toFlowJson(loaded.nodes, loaded.edges)))
      const names = loaded.nodes.map((n) => n.data.node.step).filter(Boolean)
      const app = guessApp(names, steps)
      if (app && !names.some((name) => steps.some((s) => s.name === name && appKey(s.app) === appKey(appName)))) setAppName(app)
      setSelectedId(null)
      setNodeData({})
      if (id !== flowId) setContext('{}') // starting values belong to one flow
      forget(id) // no colours from an old run
      sessionStorage.setItem('wf-flow', id)
      setFramed(true)
      setView((v) => v + 1)
    } finally {
      if (ticket === busy.current.ticket) setOpening(false)
    }
  }

  async function openFlow(id) {
    setMenu(null)
    if (!mayLeave()) return
    setError('')
    await show(id).catch((e) => setError(e.message))
    focusSoon('open-flows')
  }

  function newFlow() {
    setMenu(null)
    if (!mayLeave()) return
    busy.current.ticket += 1
    setOpening(false)
    setError('')
    setNodes([])
    setEdges([])
    setFlowId(freshName(flows.map((f) => f.id)))
    setOrigin({ name: null, revision: null })
    setSavedJson(EMPTY_FLOW)
    setContext('{}')
    setSelectedId(null)
    setNodeData({})
    sessionStorage.removeItem('wf-flow')
    setFramed(false)
    setView((v) => v + 1)
    focusSoon('open-flows')
  }

  // A factory template is read-only: a copy in the user layer is what the person edits.
  async function duplicate(id) {
    setMenu(null)
    if (!mayLeave()) return
    setError('')
    const copyId = freshName(flows.map((flow) => flow.id), `${id}-copy`)
    try {
      await api(`${flowUrl(id)}/duplicate`, { method: 'POST', body: { new_id: copyId } })
      refresh()
      await show(copyId)
    } catch (e) {
      setError(e.message)
    }
  }

  // Save what is on screen. Never replaces a flow this screen has not seen without asking. True when stored.
  async function save() {
    setError('')
    const problem = invalid.length
      ? `Fix “${invalid[0].label}” in ${invalid[0].node} before saving: ${invalid[0].error}.` : nameProblem(flowId)
    if (problem) { setError(problem); return false }
    if (busy.current.saving) return false
    busy.current.saving = true
    const sent = toFlowJson(nodes, edges)
    const put = (extra) => api(flowUrl(flowId), { method: 'PUT', body: { ...sent, ...extra } })
    try {
      let stored
      try {
        stored = await put({ base: isStored ? origin.revision : null })
      } catch (e) {
        if (e.status !== 409) throw e
        if (!window.confirm(`${e.message}. Replace it with what is on the screen?`)) return false
        stored = await put({})
      }
      setOrigin({ name: flowId, revision: stored.revision })
      setSavedJson(JSON.stringify(sent))
      patch(flowId, { acknowledged: true }) // the badge now speaks about the save, not the last run
      sessionStorage.setItem('wf-flow', flowId)
      refresh()
      return true
    } catch (e) {
      setError(e.message)
      return false
    } finally {
      busy.current.saving = false
    }
  }

  // Before a run or a test: what is stored must be what is on the screen.
  async function ensureStored() {
    if (dirty || !isStored) return save()
    const now = await api(flowUrl(flowId))
    if (now.revision === origin.revision) return true
    await show(flowId)
    setError('This flow was changed somewhere else. It is shown as it is now: check it and try again.')
    return false
  }

  async function run() {
    if (busy.current.starting) return
    busy.current.starting = true
    setStarting(true)
    setError('')
    const name = flowId
    try {
      let values
      try { values = JSON.parse(context || '{}') } catch { throw new Error('Run data is not valid JSON.') }
      if (!(await ensureStored())) return
      forget(name)
      const { run_id } = await api(`${flowUrl(name)}/run`, { method: 'POST', body: { app: appName, context: values } })
      follow(name, run_id)
    } catch (e) {
      setError(e.message)
      if (e.status === 409) attach() // it is running already: show it, with its Stop button
    } finally {
      busy.current.starting = false
      setStarting(false)
    }
  }

  async function stop(runId) { // one mouse and keyboard: this ends every run at once
    try {
      await api(`/api/runs/${runId}/stop`, { method: 'POST' })
    } catch (e) {
      if (e.status !== 409) setError(e.message) // 409: it had just ended
    }
  }

  const shownRun = isStored ? runs[flowId] : undefined
  const running = shownRun?.status === 'running'
  const elsewhere = Object.entries(runs).filter(([name, r]) => r.status === 'running' && !(running && name === flowId))
  const lastRun = shownRun?.acknowledged ? undefined : shownRun?.status
  const status = running ? 'running' : dirty ? 'unsaved' : lastRun ?? (isStored ? 'saved' : 'draft')
  const statusWords = { unsaved: 'Unsaved changes', saved: 'Saved', draft: 'Draft' }[status] ?? runWords(status)
  const flowDoubts = useMemo(() => doubts.filter((d) => isStored && d.flow_id === flowId), [doubts, flowId, isStored])
  const doubtCounts = useMemo(() => {
    const counts = {}
    for (const d of flowDoubts) counts[d.node_id] = (counts[d.node_id] ?? 0) + 1
    return counts
  }, [flowDoubts])

  // What is known about each step, for the app the flow runs on: how far it is trusted, where it was adapted from, or
  // that nobody taught it for this app (a recipe hole left open).
  const viewNodes = useMemo(() => nodes.map((n) => {
    const node = n.data.node
    if (node.kind && node.kind !== 'step') return n
    const step = steps.find((s) => s.name === node.step && appKey(s.app) === appKey(appName))
    return { ...n, data: { ...n.data, meta: step ? { ...metaOf(step), hole: n.data.hole } : { missing: true, hole: n.data.hole } } }
  }), [nodes, steps, appName])

  const selected = viewNodes.find((n) => n.id === selectedId)
  const selectedNode = selected?.data.node
  const nameOf = (id) => {
    const node = viewNodes.find((n) => n.id === id)
    return node ? titleOf(node.data.node) : id
  }
  const runKeys = useMemo(() => {
    try { return Object.keys(JSON.parse(context || '{}')) } catch { return [] }
  }, [context])
  const openDetail = (id) => { setSelectedId(id); setDetailOpen(true); loadData(showValues) }
  const closeDetail = () => {
    const id = selectedId
    setDetailOpen(false)
    setTimeout(() => document.querySelector(`.react-flow__node[data-id="${id}"]`)?.focus(), 0)
  }
  const toggleValues = (on) => { setShowValues(on); loadData(on) }
  const shownNodes = useMemo(
    () => viewNodes.map((n) => ({
      ...n, className: `status-${shownRun?.nodes[n.id] ?? 'pending'}`,
      data: { ...n.data, runStatus: shownRun?.nodes[n.id], doubts: doubtCounts[n.id] ?? 0, onDoubts: () => onOpen('queue') },
    })),
    [viewNodes, shownRun, doubtCounts, onOpen],
  )
  const safety = useMemo(() => safetySummary(viewNodes, doubtCounts), [viewNodes, doubtCounts])
  const blocked = whyNotRunnable(safety, appName)
  const paused = running && Object.values(shownRun.nodes).includes('paused')
  const apps = [...new Set(steps.map((s) => s.app))]
  const loose = looseNodes(nodes, edges)
  const shownEdges = edges.map((e) => ({ ...e, ariaLabel: `Wire from ${nameOf(e.source)} to ${nameOf(e.target)}` }))
  const outcome = shownRun && !running && {
    waiting: 'This flow did not run: it still has an open question from an earlier run.',
    stopped: `Stopped at “${nameOf(shownRun.stopped)}”. ${flowDoubts.filter((d) => d.node_id === shownRun.stopped)
      .map((d) => reasonWords(d.reason))[0] ?? ''}`,
    emergency: 'You stopped this run. Run it again to continue where it stopped.',
    error: `The run failed (${shownRun.error ?? 'unknown error'}).`,
    busy: 'This flow is already running somewhere else.',
  }[shownRun.status]

  return (
    <div className="editor">
      <header className="topbar">
        <input className="flow-name" aria-label="Flow name" data-testid="flow-id" value={flowId}
          onChange={(e) => setFlowId(e.target.value)} />
        <span className={`pill pill-${status}`} data-testid="run-status" role="status">{statusWords}</span>
        <ul className="summary" aria-label="Safety of this flow" data-testid="safety-summary">
          {summaryMarks(safety).map(([glyph, words, tone]) => (
            <li key={words} className={`tone-${tone}`}><Icon name={glyph} size={15} /> {words}</li>
          ))}
        </ul>

        <div className="menu-anchor">
          <button className="ghost" data-testid="open-flows" aria-expanded={menu === 'flows'} onClick={() => setMenu(menu === 'flows' ? null : 'flows')}>
            <Icon name="folder" /> Flows
          </button>
          {menu === 'flows' && (
            <div className="menu" aria-label="Flows">
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
          <input aria-label="App to run on" data-testid="app-name" list="editor-apps" value={appName} onChange={(e) => setAppName(e.target.value)} />
          <datalist id="editor-apps">{apps.map((a) => <option key={a} value={a}>{appLabel(a)}</option>)}</datalist>
        </label>
        <div className="menu-anchor">
          <button className="ghost" data-testid="run-data" aria-expanded={menu === 'data'} onClick={() => setMenu(menu === 'data' ? null : 'data')}>
            Run data
          </button>
          {menu === 'data' && (
            <div className="menu wide">
              <label htmlFor="run-context">Starting values, optional (JSON). Only nodes that read “Run data” use them.</label>
              <textarea id="run-context" data-testid="context" value={context} rows={4} onChange={(e) => setContext(e.target.value)} />
            </div>
          )}
        </div>
        <button className={dirty ? 'ghost wants-save' : 'ghost'} data-testid="save" onClick={save}>Save</button>
        {running ? (
          <button className="danger" data-testid="stop" disabled={!shownRun.armed} onClick={() => stop(shownRun.runId)}>
            <Icon name="stop" size={16} /> Stop
          </button>
        ) : (
          <button className="primary" data-testid="run" onClick={run} disabled={starting || nodes.length === 0 || Boolean(blocked)}
            title={nodes.length === 0 ? 'Add a node first' : blocked}>
            <Icon name="play" size={16} /> {starting ? 'Starting…' : 'Run flow'}
          </button>
        )}
      </header>
      <div className="canvas" onDrop={drop} onDragOver={(e) => e.preventDefault()} onKeyDownCapture={(e) => {
        if (e.key !== 'Enter' || !e.target.classList.contains('react-flow__node')) return
        e.preventDefault()
        e.stopPropagation()
        openDetail(e.target.dataset.id)
      }}>
        <div className="notices">
        {blocked && (
          <div className="notice" role="status">
            <span data-testid="cannot-start">{blocked}</span>
            {safety.rejected.length > 0 && <button className="small" onClick={() => onOpen('library')}>Open Steps</button>}
          </div>
        )}
        {outcome && (
          <div className={`notice notice-${shownRun.status}`} data-testid="run-outcome" role="status">
            <Icon name="alert" size={16} /> <span>{outcome}</span>
            {['waiting', 'stopped'].includes(shownRun.status) && <button className="small" onClick={() => onOpen('queue')}>Open Tutor queue</button>}
          </div>
        )}
        {elsewhere.map(([name, r]) => (
          <div key={name} className="notice" data-testid="running-elsewhere" role="status">
            <span><b>{name}</b> is running now.</span>
            <button className="small" onClick={() => openFlow(name)}>Show it</button>
            <button className="danger small" disabled={!r.armed} onClick={() => stop(r.runId)}>Stop it</button>
          </div>
        ))}
        {loose.length > 0 && (
          <div className="notice" data-testid="unwired" role="status">
            <span>{loose.length === 1 ? '1 node is' : `${loose.length} nodes are`} not connected: what is not connected runs at the same time, in no set order.</span>
            <button className="small" onClick={() => setEdges(chainLoose(nodes, edges))}>Connect them in order</button>
          </div>
        )}
        <p className="sr-only" data-testid="editor-announce" role="status">{said}</p>
        {paused && (
          <div className="notice" data-testid="paused" role="status">
            <Icon name="pause" size={15} /> Paused: you moved the mouse. It resumes when you stop using the PC.
          </div>
        )}
        {offline && <div className="notice" role="status">{UNREACHABLE} Trying again…</div>}
        {error && (
          <div className="error" role="alert" data-testid="error">
            <span>{error}</span>
            <button className="icon-button" aria-label="Close the message" onClick={() => setError('')}><Icon name="close" /></button>
          </div>
        )}

        </div>
        <ReactFlow
          key={view}
          nodes={shownNodes}
          edges={shownEdges}
          edgesFocusable={false}
          nodeTypes={NODE_TYPES}
          onNodesChange={changeNodes}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedId(node.id)}
          onNodeDoubleClick={(_, node) => openDetail(node.id)}
          onPaneClick={() => setSelectedId(null)}
          deleteKeyCode={['Backspace', 'Delete']}
          colorMode="dark"
          fitView={framed}
          fitViewOptions={fit()}
          zoomOnDoubleClick={false}
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
          <NodePanel node={selected} nodes={viewNodes} edges={edges} onConnect={onConnect}
            onDisconnect={(edge) => setEdges((current) => current.filter((e) => e.id !== edge.id))}
            onOpen={() => openDetail(selected.id)} onDelete={deleteSelected} />
        )}

        {selected && detailOpen && (
          <NodeDetail
            key={selected.id}
            node={selectedNode}
            meta={selected.data.meta}
            drafts={selected.data.drafts}
            onDraft={draftSelected}
            refs={refOptions(viewNodes, selected.id, runKeys, (n) => titleOf(n.data.node))}
            data={nodeData[selected.id]}
            showValues={showValues}
            onShowValues={toggleValues}
            onChange={updateSelected}
            onClose={closeDetail}
            onDelete={() => { deleteSelected(); setDetailOpen(false) }}
            flowId={flowId}
            appName={appName}
            context={context}
            ensureSaved={async () => {
              if (!(await ensureStored())) throw new Error('the flow was not saved, so nothing was tested')
            }}
            onTested={() => setSettled((n) => n + 1)}
          />
        )}

        {panelOpen
          ? <SearchPanel steps={steps} recipes={recipes} onAddSystem={addSystem} onAddStep={addStep} onAddRecipe={addRecipe}
              onClose={() => { setPanelOpen(false); focusSoon('open-panel') }} />
          : (
            <button className="open-panel" data-testid="open-panel" aria-label="Add a node"
              onClick={() => { setPanelOpen(true); focusSoon('search') }}>
              <Icon name="plus" size={20} />
            </button>
          )}
        {opening && <div className="opening" role="status">Opening…</div>}
      </div>
      {shownRun && !shownRun.logClosed && (
        <RunLog log={shownRun.log} nodes={viewNodes} running={running}
          onClose={() => { patch(flowId, { logClosed: true }); focusSoon('run') }} />
      )}
    </div>
  )
}
