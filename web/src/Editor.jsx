import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import { ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Panel, useEdgesState, useNodesState, useReactFlow } from '@xyflow/react'
import { api, encode, loadAppNames, UNREACHABLE } from './api.js'
import { boxNumbers, chainLoose, fromFlowJson, joinBoxes, looseNodes, nextNodeId, toFlowJson, withBranch } from './flowjson.js'
import { Icon } from './icons.jsx'
import { refOptions } from './bindings.js'
import { appKey, appLabel, SYSTEM_NODES, taughtApp, titleOf } from './catalog.js'
import NodeCard from './NodeCard.jsx'
import NodeDetail from './NodeDetail.jsx'
import NodePanel from './NodePanel.jsx'
import RunLog from './RunLog.jsx'
import SearchPanel, { DRAG_TYPE } from './SearchPanel.jsx'
import { safetySummary, summaryMarks, whyNotRunnable } from './safety.js'
import { boxState, flowTitle, freshTitle, reasonWords, runWords } from './words.js'

const NODE_TYPES = { card: NodeCard }
const EDGE_LOOK = { labelBgPadding: [10, 4], labelBgBorderRadius: 999 } // yes and no on a pill
const metaOf = (step) => ({ app: step.app, sensitive: step.sensitive, origin: step.origin, action: step.action,
  state: step.state, private: step.private, consent: step.consent, adapted_from: step.adapted_from })
// the whole flow in sight, clear of the notices over the top of the canvas and of the zoom buttons at its foot; a narrow
// window has no room to spare
const fit = () => {
  const covered = document.querySelector('.notices')?.offsetHeight ?? 0
  const edge = window.innerWidth > 860 ? 40 : 16
  return { maxZoom: 1, padding: { top: `${covered + edge}px`, left: `${edge}px`, bottom: '76px', right: `${edge}px` } }
}
// after something is gone from the screen, the keyboard focus goes to what is left
const focusSoon = (...testIds) => setTimeout(() => {
  testIds.map((id) => document.querySelector(`[data-testid=${id}]`)).find(Boolean)?.focus()
}, 0)
const EMPTY_FLOW = JSON.stringify(toFlowJson([], []))
const flowUrl = (id) => `/api/flows/${encode(id)}`
const FIRST_TITLE = freshTitle([])

export default function Editor(props) {
  return <ReactFlowProvider><EditorScreen {...props} /></ReactFlowProvider>
}

function EditorScreen({ ref, active, onOpen, onBack, onUnsaved, following }) {
  const { fitView, screenToFlowPosition, zoomIn, zoomOut } = useReactFlow()
  const [steps, setSteps] = useState([])
  const [recipes, setRecipes] = useState([])
  const [flows, setFlows] = useState([])
  const [flowId, setFlowId] = useState(null) // null: a new flow, which gets its identifier when it is first saved
  const [title, setTitle] = useState(FIRST_TITLE)
  const [revision, setRevision] = useState(null) // of the stored flow on screen, as it was read
  const [saved, setSaved] = useState({ json: EMPTY_FLOW, title: FIRST_TITLE, app: '' })
  const [appName, setAppName] = useState('')
  const [context, setContext] = useState('{}')
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedId, setSelectedId] = useState(null)
  const [error, setError] = useState('')
  const [menu, setMenu] = useState(null) // 'flows' | 'data': one popover at a time
  const [detailOpen, setDetailOpen] = useState(false)
  const [nodeData, setNodeData] = useState({})
  const [showValues, setShowValues] = useState(false)
  const [doubts, setDoubts] = useState([]) // the open ones (the tutor answers them, not the editor)
  const [view, setView] = useState(0) // bumped when another flow is shown, so the canvas fits it
  const [starting, setStarting] = useState(false)
  const [opening, setOpening] = useState(false)
  const [tested, setTested] = useState(0)
  const [said, say] = useState('') // for people who cannot see the canvas change
  const [framed, setFramed] = useState(false) // a stored flow is fitted to the window; a drawn one stays where it is put
  const busy = useRef({ saving: false, starting: false, ticket: 0, named: false })
  const { runs, offline, settled, follow, attach, forget, patch } = following

  const body = useMemo(() => toFlowJson(nodes, edges), [nodes, edges])
  const invalid = useMemo(() => nodes.flatMap((n) => Object.values(n.data.drafts ?? {}).filter(Boolean)
    .map((draft) => ({ ...draft, node: titleOf(n.data.node) }))), [nodes])
  const isStored = flowId !== null
  const apps = useMemo(() => [...new Set(steps.map((s) => s.app))], [steps])
  const runsOn = taughtApp(appName, apps)
  // choosing an app on a new flow is not work to lose; on a stored one it is a change to keep
  const dirty = JSON.stringify(body) !== saved.json || title !== saved.title || invalid.length > 0
    || (isStored && runsOn !== taughtApp(saved.app, apps)) // both as taught: the steps may arrive after the flow

  const refresh = useCallback(() => {
    const fail = (e) => setError(e.message)
    loadAppNames() // a run just seen may have told the name of its app
    api('/api/steps').then((found) => {
      setSteps(found)
      setAppName((current) => current || found[0]?.app || '')
    }).catch(fail)
    api('/api/recipes').then(setRecipes).catch(fail)
    api('/api/flows').then((found) => {
      setFlows(found)
      if (busy.current.named) return
      busy.current.named = true // a first flow must not start with the name of a stored one
      const fresh = freshTitle(found)
      setTitle((current) => (current === FIRST_TITLE ? fresh : current))
      setSaved((current) => (current.title === FIRST_TITLE ? { ...current, title: fresh } : current))
    }).catch(fail)
    api('/api/doubts?status=open').then(setDoubts).catch(() => setDoubts([]))
  }, [])

  // what the other screens, a run or another window changed is read again when the person comes back
  useEffect(() => {
    if (!active) return undefined
    refresh()
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [active, settled, tested, refresh])

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
    if (flowId === null) { setNodeData({}); return } // an unsaved flow has none yet
    try {
      setNodeData(await api(`${flowUrl(flowId)}/data${values ? '?values=1' : ''}`))
    } catch {
      setNodeData({})
    }
  }, [flowId])
  useEffect(() => { if (settled || tested) loadData(showValues) }, [settled, tested]) // eslint-disable-line react-hooks/exhaustive-deps

  // after a reload, the flow the person had open comes back
  useEffect(() => {
    if (busy.current.restored || !steps.length || !flows.length) return
    busy.current.restored = true
    const last = sessionStorage.getItem('wf-flow')
    if (nodes.length === 0 && flows.some((f) => f.id === last)) show(last).catch((e) => setError(e.message))
  }, [steps, flows]) // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = useCallback((connection) => {
    if (edges.some((e) => e.source === connection.source && e.target === connection.target)) return
    const wire = withBranch(nodes, edges, connection)
    if (wire) setEdges([...edges, wire])
    else setError('Those two cannot be joined: a decision has only two paths, yes and no, and a repeated box takes no lines of its own.')
  }, [nodes, edges, setEdges])

  const changeNodes = useCallback((changes) => { // selecting with the keyboard is selecting too
    onNodesChange(changes)
    for (const change of changes) {
      if (change.type === 'remove') { say('Node deleted'); focusSoon('search') }
      if (change.type !== 'select') continue
      if (change.selected) setSelectedId(change.id)
      else setSelectedId((current) => (current === change.id ? null : current))
    }
  }, [onNodesChange])

  const refit = () => setTimeout(() => fitView({ ...fit(), duration: 200 }), 60) // once the new node is on the canvas

  // New boxes join after the chosen box, or after the last one. With a box chosen the new one takes its place as the
  // chosen one, so the next goes after it: the order is the order of the presses. A dropped box stays where it fell.
  const join = (added, dropped) => {
    const joined = joinBoxes(nodes, edges, added, { after: selectedId, at: dropped })
    const chosen = nodes.some((n) => n.id === selectedId) ? added[added.length - 1].id : null
    setNodes(joined.nodes.map((n) => ({ ...n, selected: n.id === chosen })))
    setEdges(joined.edges)
    setSelectedId(chosen)
    if (!dropped) refit()
  }

  const addNode = (node, dropped) => {
    const id = nextNodeId(nodes)
    join([{ id, type: 'card', data: { node: { ...node, id, inputs: [], exclusive_input: false } } }], dropped)
    say(`Added ${titleOf(node)}`)
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
    let list = [...nodes]
    const added = recipe.holes.map((hole) => {
      const id = nextNodeId(list)
      const node = { id, step: bound[hole.hole] ?? `${recipe.name}-${hole.hole}`, inputs: [], exclusive_input: false }
      const card = { id, type: 'card', data: { node, hole: { recipe: recipe.name, hole: hole.hole } } }
      list = [...list, card]
      return card
    })
    join(added)
  }
  const addSystem = (entry) => addNode(structuredClone(entry.node))

  const updateNode = (id, change) => setNodes((current) => current.map((n) => (n.id === id ? { ...n, data: change(n.data) } : n)))
  const updateSelected = (change) => updateNode(selectedId, (data) => ({ ...data, node: { ...data.node, ...change } }))
  const draftSelected = (field, draft) => updateNode(selectedId, (data) => ({ ...data, drafts: { ...data.drafts, [field]: draft } }))

  function deleteSelected() {
    const gone = nodes.find((n) => n.id === selectedId)
    if (gone) say(`Deleted ${titleOf(gone.data.node)}`)
    focusSoon('search')
    setNodes((current) => current.filter((n) => n.id !== selectedId))
    setEdges((current) => current.filter((e) => e.source !== selectedId && e.target !== selectedId))
    setSelectedId(null)
  }

  const mayLeave = () => !dirty || window.confirm(`“${title.trim() || saved.title}” has changes that are not saved. Discard them?`)

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
      setRevision(stored.revision)
      setTitle(stored.title)
      if (stored.app) setAppName(stored.app)
      setSaved({ json: JSON.stringify(toFlowJson(loaded.nodes, loaded.edges)), title: stored.title,
        app: stored.app || runsOn })
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

  async function load(id) {
    setError('')
    await show(id).catch((e) => setError(e.message))
    focusSoon('open-flows')
  }

  function openFlow(id) {
    setMenu(null)
    if (mayLeave()) load(id)
  }

  // false: the person keeps the changes on screen
  function newFlow() {
    setMenu(null)
    if (!mayLeave()) return false
    busy.current.ticket += 1
    setOpening(false)
    setError('')
    setNodes([])
    setEdges([])
    const fresh = freshTitle(flows)
    setFlowId(null)
    setRevision(null)
    setTitle(fresh)
    setSaved({ json: EMPTY_FLOW, title: fresh, app: '' })
    setContext('{}')
    setSelectedId(null)
    setNodeData({})
    sessionStorage.removeItem('wf-flow')
    setFramed(false)
    setView((v) => v + 1)
    focusSoon('open-flows')
    return true
  }

  // What Home asks of this screen. Each answers whether to show it. A flow asked for replaces the one the person had open
  // before a reload.
  useImperativeHandle(ref, () => ({
    create() {
      const shown = newFlow()
      busy.current.restored ||= shown
      return shown
    },
    open(id) {
      if (id !== flowId || !dirty) { // the flow on screen with unsaved changes is shown as it was left
        if (!mayLeave()) return false
        load(id)
      }
      busy.current.restored = true
      setMenu(null)
      return true
    },
  }))

  // A factory template is read-only: a copy in the user layer is what the person edits.
  async function duplicate(id) {
    setMenu(null)
    if (!mayLeave()) return
    setError('')
    const source = flows.find((flow) => flow.id === id).title.slice(0, 90) // room for " copy" in a name
    try {
      const copy = await api(`${flowUrl(id)}/duplicate`, { method: 'POST', body: { title: freshTitle(flows, `${source} copy`) } })
      refresh()
      await show(copy.id)
    } catch (e) {
      setError(e.message)
    }
  }

  // Save what is on screen. A new flow is created beside the others, whatever it is called; a stored one changed
  // somewhere else is never replaced without asking. The flow's identifier when stored, else null.
  async function save() {
    setError('')
    if (invalid.length) {
      setError(`Fix “${invalid[0].label}” in ${invalid[0].node} before saving: ${invalid[0].error}.`)
      return null
    }
    if (busy.current.saving) return null
    busy.current.saving = true
    const ticket = busy.current.ticket
    const sent = toFlowJson(nodes, edges)
    const flow = { ...sent, title, app: runsOn }
    const put = (extra) => api(flowUrl(flowId), { method: 'PUT', body: { ...flow, ...extra } })
    try {
      let stored
      try {
        stored = isStored ? await put({ base: revision }) : await api('/api/flows', { method: 'POST', body: flow })
      } catch (e) {
        if (e.status !== 409) throw e
        if (!window.confirm(`${e.message}. Replace it with what is on the screen?`)) return null
        stored = await put({})
      }
      refresh()
      if (ticket !== busy.current.ticket) return null // another flow is on the screen by now
      setFlowId(stored.id)
      setRevision(stored.revision)
      setSaved({ json: JSON.stringify(sent), title: stored.title, app: runsOn })
      setTitle((current) => (current === title ? stored.title : current))
      patch(stored.id, { acknowledged: true }) // the badge now speaks about the save, not the last run
      sessionStorage.setItem('wf-flow', stored.id)
      return stored.id
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      busy.current.saving = false
    }
  }

  // Before a run or a test: what is stored must be what is on the screen. The identifier to run, else null.
  async function ensureStored() {
    if (dirty || !isStored) return save()
    const now = await api(flowUrl(flowId))
    if (now.revision === revision) return flowId
    await show(flowId)
    setError('This flow was changed somewhere else. It is shown as it is now: check it and try again.')
    return null
  }

  async function run() {
    if (busy.current.starting) return
    busy.current.starting = true
    setStarting(true)
    setError('')
    try {
      let values
      try { values = JSON.parse(context || '{}') } catch { throw new Error('Run data is not valid JSON.') }
      const id = await ensureStored()
      if (!id) return
      forget(id)
      const { run_id } = await api(`${flowUrl(id)}/run`, { method: 'POST', body: { app: runsOn, context: values } })
      follow(id, run_id)
    } catch (e) {
      setError(e.message)
      attach() // the answer may be all that was lost, or it runs already: show it, with its Stop button
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
  // a run puts a notice over the canvas and a log under it: the whole flow comes back into sight as it goes and ends
  // (a canvas that is not on screen has no size to fit into: that waits until it is shown again)
  useEffect(() => { if (active && shownRun) refit() }, [active, shownRun?.runId, shownRun?.status]) // eslint-disable-line react-hooks/exhaustive-deps
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
  const numbers = useMemo(() => boxNumbers(nodes, edges), [nodes, edges])
  const shownNodes = useMemo(
    () => viewNodes.map((n) => {
      const state = boxState(shownRun, n.id)
      return {
        ...n, className: `status-${state ?? 'pending'}`,
        data: { ...n.data, number: numbers[n.id], runStatus: state, doubts: doubtCounts[n.id] ?? 0, onDoubts: () => onOpen('queue') },
      }
    }),
    [viewNodes, numbers, shownRun, doubtCounts, onOpen],
  )
  const safety = useMemo(() => safetySummary(viewNodes, doubtCounts), [viewNodes, doubtCounts])
  const blocked = whyNotRunnable(safety, appName ? appLabel(appName) : undefined)
  const paused = running && Object.values(shownRun.nodes).includes('paused')
  const loose = looseNodes(nodes, edges)
  // the lines the run went down: out of a box that got through, into a box it reached
  const went = (e) => ['done', 'continued'].includes(boxState(shownRun, e.source))
    && !['unreached', undefined].includes(boxState(shownRun, e.target))
  const shownEdges = edges.map((e) => ({ ...e, ...EDGE_LOOK, className: went(e) ? 'on' : '',
    ariaLabel: `Wire from ${nameOf(e.source)} to ${nameOf(e.target)}` }))
  const outcome = shownRun && !running && {
    waiting: 'This flow did not run: it still has an open question from an earlier run.',
    stopped: `Stopped at “${nameOf(shownRun.stopped)}”. ${flowDoubts.filter((d) => d.node_id === shownRun.stopped)
      .map((d) => reasonWords(d.detail ?? d.reason))[0] ?? ''}`,
    emergency: 'You stopped this run. Run it again to continue where it stopped.',
    error: `The run failed (${shownRun.error ?? 'unknown error'}).`,
    busy: 'This flow is already running somewhere else.',
  }[shownRun.status]

  return (
    <div className="editor">
      <header className="topbar">
        <button className="ghost" data-testid="back-home" onClick={() => onBack(flowId)}><Icon name="back" size={16} /> Home</button>
        <input className="flow-name" aria-label="Flow name" data-testid="flow-title" value={title} maxLength={100}
          onChange={(e) => setTitle(e.target.value)} />
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
                    <span>{flowTitle(flow.id, flows)}</span> <small>{flow.origin}</small>
                  </button>
                  {flow.origin === 'factory' && (
                    <button className="ghost small" data-testid={`duplicate-${flow.id}`}
                      aria-label={`Duplicate template ${flowTitle(flow.id, flows)}`} onClick={() => duplicate(flow.id)}>
                      Duplicate to edit
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="spacer" />

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
            title={nodes.length === 0 ? 'Add a box first' : blocked}>
            <Icon name="play" size={16} /> {starting ? 'Starting…' : 'Run flow'}
          </button>
        )}
      </header>
      <div className="workspace">
      <div className="canvas" role="region" aria-label="Boxes of this chore" onDrop={drop} onDragOver={(e) => e.preventDefault()}
        onKeyDownCapture={(e) => {
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
            <span><b>{flowTitle(name, flows)}</b> is running now.</span>
            <button className="small" onClick={() => openFlow(name)}>Show it</button>
            <button className="danger small" disabled={!r.armed} onClick={() => stop(r.runId)}>Stop it</button>
          </div>
        ))}
        {loose.length > 0 && (
          <div className="notice" data-testid="unwired" role="status">
            <span>{loose.length === 1 ? '1 box is' : `${loose.length} boxes are`} not connected: what is not connected runs at the same time, in no set order.</span>
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
          <Panel position="bottom-left" className="zoom">
            <button aria-label="Zoom in" onClick={() => zoomIn()}><Icon name="plus" size={20} /></button>
            <button aria-label="Zoom out" onClick={() => zoomOut()}><Icon name="minus" size={20} /></button>
            <button onClick={() => fitView({ ...fit(), duration: 200 })}>Show everything</button>
          </Panel>
        </ReactFlow>

        {nodes.length === 0 && (
          <div className="empty-canvas">
            <p>Add your first box with “Add a box”.</p>
          </div>
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
            appName={runsOn}
            context={context}
            ensureSaved={async () => {
              const id = await ensureStored()
              if (!id) throw new Error('the flow was not saved, so nothing was tested')
              return id
            }}
            onTested={() => setTested((n) => n + 1)}
          />
        )}

      </div>
        {/* over the foot of the canvas; between it and the panel in a narrow window */}
        {selected && !detailOpen && (
          <NodePanel node={selected} nodes={viewNodes} edges={edges} onConnect={onConnect}
            onDisconnect={(edge) => setEdges((current) => current.filter((e) => e.id !== edge.id))}
            onOpen={() => openDetail(selected.id)} onDelete={deleteSelected} />
        )}
        <SearchPanel steps={steps} recipes={recipes} apps={apps} app={runsOn} onApp={setAppName} onAddSystem={addSystem}
          onAddStep={addStep} onAddRecipe={addRecipe} />
        {opening && <div className="opening" role="status">Opening…</div>}
      </div>
      {shownRun && !shownRun.logClosed && (
        <RunLog log={shownRun.log} nodes={viewNodes} running={running}
          onClose={() => { patch(flowId, { logClosed: true }); focusSoon('run') }} />
      )}
    </div>
  )
}
