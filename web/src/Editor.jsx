import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import { ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Panel, useEdgesState, useNodesState, useReactFlow } from '@xyflow/react'
import { TriedResults } from './Attention.jsx'
import { api, encode, loadAppNames, UNREACHABLE } from './api.js'
import { nodeNumbers, chainLoose, fromFlowJson, joinNodes, looseNodes, nextNodeId, toFlowJson, unfinished, withBranch } from './flowjson.js'
import { changeDaily, DailyForm } from './Daily.jsx'
import { Icon } from './icons.jsx'
import { refOptions } from './bindings.js'
import { appKey, SYSTEM_NODES, technologiesOf, titleOf } from './catalog.js'
import NodeCard from './NodeCard.jsx'
import NodeDetail from './NodeDetail.jsx'
import ExplanationStrip from './ExplanationStrip.jsx'
import RunLog from './RunLog.jsx'
import SearchPanel, { DRAG_TYPE } from './SearchPanel.jsx'
import { safetySummary, summaryMarks, whyNotRunnable } from './safety.js'
import { nodeState, flowTitle, freshTitle, PAUSED_WORDS, reasonWords, runWords } from './words.js'

const NODE_TYPES = { card: NodeCard }
const EDGE_LOOK = { labelBgPadding: [10, 4], labelBgBorderRadius: 999 } // yes and no on a pill
const metaOf = (step) => ({ app: step.app, sensitive: step.sensitive, origin: step.origin, action: step.action, locator: step.locator,
  state: step.state, private: step.private, consent: step.consent, adapted_from: step.adapted_from,
  successes: step.successes, failures: step.failures, counted: step.counted })
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
const isDaily = (n) => n.data.node.kind === 'trigger' && n.data.node.fields?.mode?.value === 'daily'

export default function Editor(props) {
  return <ReactFlowProvider><EditorScreen {...props} /></ReactFlowProvider>
}

function EditorScreen({ ref, active, onOpen, onBack, onUnsaved, following, tried }) {
  const { fitView, screenToFlowPosition, zoomIn, zoomOut } = useReactFlow()
  const [steps, setSteps] = useState([])
  const [recipes, setRecipes] = useState([])
  const [flows, setFlows] = useState([])
  const [flowId, setFlowId] = useState(null) // null: a new flow, which gets its identifier when it is first saved
  const [title, setTitle] = useState(FIRST_TITLE)
  const [saved, setSaved] = useState({ json: EMPTY_FLOW, title: FIRST_TITLE })
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
  const [needs, setNeeds] = useState([]) // what stopped and waits for the person, as the server lists it
  const [view, setView] = useState(0) // bumped when another flow is shown, so the canvas fits it
  const [starting, setStarting] = useState(false)
  const [opening, setOpening] = useState(false)
  const [tested, setTested] = useState(0)
  const [said, say] = useState('') // for people who cannot see the canvas change
  const [daily, setDaily] = useState(null) // {at, node_at} as the server says: the Windows task, and the node
  const dailyNow = useRef(null) // what `daily` holds, for a save that finishes later
  const [settingDaily, setSettingDaily] = useState(false)
  const [focusStart, setFocusStart] = useState(0)
  const [framed, setFramed] = useState(false) // a stored flow is fitted to the window; a drawn one stays where it is put
  const [problem, setProblem] = useState('') // what the server said when it would not keep the flow
  const [conflict, setConflict] = useState('') // the flow was changed somewhere else: the person chooses
  const [retry, setRetry] = useState(0)
  const [undoable, setUndoable] = useState(0) // how many changes can be taken back
  const [removed, setRemoved] = useState('') // the node just removed, for the notice that offers Undo
  const busy = useRef({ starting: false, ticket: 0, named: false })
  const stored = useRef({ id: null, revision: null }) // the flow on screen as the server last had it: saves carry it forward
  const queue = useRef(Promise.resolve()) // one save at a time, each on top of the last
  const history = useRef({ past: [], key: '', at: 0 })
  const now = useRef({ nodes: [], edges: [] })
  const { runs, offline, settled, follow, attach, forget, patch } = following

  now.current = { nodes, edges }
  const body = useMemo(() => toFlowJson(nodes, edges), [nodes, edges])
  const invalid = useMemo(() => nodes.flatMap((n) => Object.values(n.data.drafts ?? {}).filter(Boolean)
    .map((draft) => ({ ...draft, node: titleOf(n.data.node) }))), [nodes])
  const isStored = flowId !== null
  const template = flows.some((f) => f.id === flowId && f.origin === 'factory') // read-only: a copy is what is edited
  const dirty = JSON.stringify(body) !== saved.json || title !== saved.title || invalid.length > 0
  // changes the server has not got: a flow with no node yet is not stored, so its name alone is nothing to lose
  const unkept = dirty && (isStored || nodes.length > 0)
  // what keeps the flow from being stored, in the person's words (the node says it too)
  const held = invalid.length ? `Fix “${invalid[0].label}” in ${invalid[0].node}: ${invalid[0].error}.` : unfinished(body.nodes, nodeNumbers(nodes, edges))

  const refresh = useCallback(() => {
    const fail = (e) => setError(e.message)
    loadAppNames() // a run just seen may have told the name of its app
    api('/api/steps').then(setSteps).catch(fail)
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
    api('/api/attention').then(setNeeds).catch(() => setNeeds([]))
  }, [])

  // what the other screens, a run or another window changed is read again when the person comes back
  useEffect(() => {
    if (!active) return undefined
    refresh()
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [active, settled, tested, refresh])

  useEffect(() => { onUnsaved(unkept) }, [unkept, onUnsaved])
  useEffect(() => { dailyNow.current = daily }, [daily])
  useEffect(() => {
    if (!unkept) return undefined
    const warn = (event) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [unkept])

  // Every change is kept a moment after it is made: no button. Held back while the flow cannot be stored, while it was
  // changed somewhere else (the person chooses first) and for a read-only template.
  useEffect(() => {
    if (!unkept || held || conflict || opening || template) return undefined
    setProblem('')
    const timer = setTimeout(() => save(), 400)
    return () => clearTimeout(timer)
  }, [unkept, held, conflict, opening, template, body, title, retry]) // eslint-disable-line react-hooks/exhaustive-deps

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

  // Undo: the canvas as it was before each change, newest last. A change made again and again (typing in one field) is one step.
  const record = (key = '') => {
    const h = history.current
    setRemoved('')
    if (key && key === h.key && Date.now() - h.at < 1000) { h.at = Date.now(); return }
    h.past.push(now.current)
    if (h.past.length > 100) h.past.shift()
    Object.assign(h, { key, at: Date.now() })
    setUndoable(h.past.length)
  }
  const clearHistory = () => { history.current = { past: [], key: '', at: 0 }; setUndoable(0); setRemoved('') }
  function undo() {
    const h = history.current
    const shown = JSON.stringify(toFlowJson(now.current.nodes, now.current.edges))
    let back
    do back = h.past.pop(); while (back && JSON.stringify(toFlowJson(back.nodes, back.edges)) === shown) // a step that changed nothing is skipped
    h.key = ''
    setUndoable(h.past.length)
    setRemoved('')
    if (!back) return
    setNodes(back.nodes.map((n) => ({ ...n, selected: false })))
    setEdges(back.edges)
    setSelectedId(null)
    say('Undone')
  }
  useEffect(() => { // Ctrl+Z outside a text field; inside one, the field's own undo is the person's
    if (!active) return undefined
    const key = (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.shiftKey || event.key.toLowerCase() !== 'z') return
      if (event.target.closest?.('input, textarea, select, [contenteditable], [role=dialog]')) return
      event.preventDefault()
      undo()
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [active]) // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = useCallback((connection) => {
    if (edges.some((e) => e.source === connection.source && e.target === connection.target)) return
    const wire = withBranch(nodes, edges, connection)
    if (wire) { record(); setEdges([...edges, wire]) }
    else setError('Those two cannot be joined: a decision has only two paths, yes and no, and a repeated node takes no lines of its own.')
  }, [nodes, edges, setEdges]) // eslint-disable-line react-hooks/exhaustive-deps

  const changeNodes = useCallback((changes) => { // selecting with the keyboard is selecting too
    onNodesChange(changes)
    for (const change of changes) {
      if (change.type === 'remove') {
        const gone = now.current.nodes.find((n) => n.id === change.id)
        say('Node deleted. Undo is in the top bar.')
        if (gone) setRemoved(titleOf(gone.data.node))
        focusSoon('search')
      }
      if (change.type !== 'select') continue
      if (change.selected) setSelectedId(change.id)
      else setSelectedId((current) => (current === change.id ? null : current))
    }
  }, [onNodesChange])

  // once the new node is on the canvas; one that has left the screen by then has no size to fit into
  const refit = () => setTimeout(() => {
    if (document.querySelector('.canvas')?.offsetWidth) fitView({ ...fit(), duration: 200 })
  }, 60)

  // New nodes join after the chosen node, or after the last one. With a node chosen the new one takes its place as the
  // chosen one, so the next goes after it: the order is the order of the presses. A dropped node stays where it fell.
  const join = (added, dropped) => {
    record()
    const joined = joinNodes(nodes, edges, added, { after: selectedId, at: dropped })
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
    addNode({ step: step.name, technology: step.app }, dropped)
  }

  function drop(event) {
    const raw = event.dataTransfer.getData(DRAG_TYPE)
    if (!raw) return
    event.preventDefault()
    const entry = JSON.parse(raw)
    const at = screenToFlowPosition({ x: event.clientX, y: event.clientY })
    const system = SYSTEM_NODES.find((n) => n.key === entry.system)
    const step = steps.find((s) => s.name === entry.step && appKey(s.app) === appKey(entry.app))
    if (system) addNode(structuredClone(system.node), at)
    else if (step) addStep(step, at)
  }

  // Drop a recipe: one connected node per hole, each on the step that fills the hole for one program: the one the flow
  // acts on last if the recipe knows it, else the first the recipe was applied to.
  // A hole nobody filled for this program gets the name its step will have, and the node says it is not filled.
  const addRecipe = (recipe) => {
    const known = Object.keys(recipe.apps)
    const last = nodes.map((n) => n.data.node.technology).filter(Boolean).at(-1)
    const runsOn = known.find((app) => last && appKey(app) === appKey(last)) ?? known[0] ?? ''
    const bound = recipe.apps[runsOn] ?? {}
    let list = [...nodes]
    const added = recipe.holes.map((hole) => {
      const id = nextNodeId(list)
      const node = { id, step: bound[hole.hole] ?? `${recipe.name}-${hole.hole}`, technology: runsOn, inputs: [], exclusive_input: false }
      const card = { id, type: 'card', data: { node, hole: { recipe: recipe.name, hole: hole.hole } } }
      list = [...list, card]
      return card
    })
    join(added)
  }
  const addSystem = (entry) => addNode(structuredClone(entry.node))

  const updateNode = (id, change) => setNodes((current) => current.map((n) => (n.id === id ? { ...n, data: change(n.data) } : n)))
  const updateSelected = (change) => { record(`settings:${selectedId}`); updateNode(selectedId, (data) => ({ ...data, node: { ...data.node, ...change } })) }
  const draftSelected = (field, draft) => updateNode(selectedId, (data) => ({ ...data, drafts: { ...data.drafts, [field]: draft } }))

  function deleteSelected() {
    const gone = nodes.find((n) => n.id === selectedId)
    record()
    if (gone) { say(`Deleted ${titleOf(gone.data.node)}. Undo is in the top bar.`); setRemoved(titleOf(gone.data.node)) }
    focusSoon('search')
    setNodes((current) => current.filter((n) => n.id !== selectedId))
    setEdges((current) => current.filter((e) => e.source !== selectedId && e.target !== selectedId))
    setSelectedId(null)
  }

  // Changes that can be kept are kept by themselves: only what cannot be kept asks before it goes.
  const mayLeave = () => {
    if (!unkept) return true
    if (!held && !conflict && !template && !problem) { save(); return true }
    return window.confirm(`“${title.trim() || saved.title}” has changes that are not saved. Discard them?`)
  }

  // what the server has of the flow on screen: what the next save is built on; a new flow or another one starts clean
  function keep(id, revision) {
    stored.current = { id, revision }
    setProblem('')
    setConflict('')
    clearHistory()
  }

  // Put a stored flow on the canvas. Only the latest request wins.
  async function show(id) {
    const ticket = ++busy.current.ticket
    setOpening(true)
    try {
      const time = await api(`${flowUrl(id)}/daily`).catch(() => null) // reading only says what Windows has; it never changes the canvas
      const read = await api(flowUrl(id))
      if (ticket !== busy.current.ticket) return
      setDaily(time)
      setSettingDaily(false)
      const loaded = fromFlowJson(read)
      setNodes(loaded.nodes)
      setEdges(loaded.edges)
      setFlowId(id)
      keep(id, read.revision)
      setTitle(read.title)
      setSaved({ json: JSON.stringify(toFlowJson(loaded.nodes, loaded.edges)), title: read.title })
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
    keep(null, null)
    setDaily(null)
    setSettingDaily(false)
    setTitle(fresh)
    setSaved({ json: EMPTY_FLOW, title: fresh })
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
      if (id !== flowId || !unkept) { // the flow on screen with changes not kept is shown as it was left
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

  // Keep what is on screen, one save after another, each carrying the revision the last one got. A new flow is created
  // beside the others, whatever it is called; a stored one changed somewhere else is never replaced unless the person says so
  // (`force`). The flow's identifier when stored, else null.
  function save(force = false) {
    if (template) {
      setError('This is a template, so it is not changed. Use “Duplicate to edit”, then change the copy.')
      return Promise.resolve(null)
    }
    if (held) {
      setError(`${held} Nothing was kept since.`)
      return Promise.resolve(null)
    }
    const snap = { nodes, edges, title, ticket: busy.current.ticket, was: { ...stored.current } }
    const done = queue.current.then(() => store(snap, force))
    queue.current = done
    return done
  }

  async function store(snap, force) {
    const here = () => snap.ticket === busy.current.ticket // false: another flow is on the screen by now
    const was = here() ? stored.current : snap.was
    const sent = toFlowJson(snap.nodes, snap.edges)
    const flow = { ...sent, title: snap.title }
    try {
      let kept
      try {
        kept = was.id
          ? await api(flowUrl(was.id), { method: 'PUT', body: force ? flow : { ...flow, base: was.revision } })
          : await api('/api/flows', { method: 'POST', body: flow })
      } catch (e) {
        if (e.status !== 409 || !was.id) throw e
        if (here()) setConflict(e.message)
        return null
      }
      refresh()
      if (!here()) return kept.id
      const nodeAt = sent.nodes.find((n) => n.kind === 'trigger' && n.fields?.mode?.value === 'daily')?.fields.at?.value ?? null
      if (nodeAt !== (dailyNow.current?.node_at ?? null)) { // the save moved the Windows task with the node: say what it is now
        api(`${flowUrl(kept.id)}/daily`).then((time) => { if (here()) setDaily(time) }).catch(() => {})
      }
      stored.current = { id: kept.id, revision: kept.revision }
      setFlowId(kept.id)
      setSaved({ json: JSON.stringify(sent), title: kept.title })
      setTitle((current) => (current === snap.title ? kept.title : current))
      setProblem('')
      setConflict('')
      patch(kept.id, { acknowledged: true }) // the badge now speaks about the save, not the last run
      sessionStorage.setItem('wf-flow', kept.id)
      return kept.id
    } catch (e) {
      if (here()) {
        setProblem(e.message)
        if (!e.status) setTimeout(() => setRetry((n) => n + 1), 3000) // the server could not be reached: try again
      }
      return null
    }
  }

  const keepMine = () => { setConflict(''); save(true) }
  const showTheirs = () => { setConflict(''); load(flowId) }

  // The daily time lives on the stored flow and in Windows: save first, change both, and show the first node as it is now.
  async function submitDaily(at) {
    const id = await ensureStored()
    if (!id) throw new Error('The flow could not be saved first, so its daily time was not changed.')
    await changeDaily(id, at)
    await show(id)
    refresh()
    setFocusStart((n) => n + 1) // the form is gone and the first node is new: the focus goes to its button once it is drawn
  }
  useEffect(() => { // the canvas draws its nodes a moment after it has them: wait for the button
    if (!focusStart) return undefined
    const want = daily?.at ? 'daily-change' : 'daily-add'
    let tries = 40
    const timer = setInterval(() => {
      const button = document.querySelector(`[data-testid=${want}]`)
      button?.focus()
      if (button || --tries === 0) clearInterval(timer)
    }, 50)
    return () => clearInterval(timer)
  }, [focusStart]) // eslint-disable-line react-hooks/exhaustive-deps
  const closeDaily = (changed) => {
    setSettingDaily(false)
    if (!changed) focusSoon('daily-change', 'daily-add', 'flow-title')
  }

  // Before a run or a test: what is stored must be what is on the screen. The identifier to run, else null.
  async function ensureStored() {
    if (conflict) { setError(`${conflict}. Choose what to do about it above, then try again.`); return null }
    if (unkept || !isStored) return save()
    const current = await api(flowUrl(flowId))
    if (current.revision === stored.current.revision) return flowId
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
      const { run_id } = await api(`${flowUrl(id)}/run`, { method: 'POST', body: { context: values } })
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
  const status = running ? 'running' : conflict ? 'conflict' : unkept && template ? 'template'
    : unkept && (held || problem) ? 'problem' : unkept ? 'saving' : lastRun ?? (isStored ? 'saved' : 'draft')
  const statusWords = { conflict: 'Changed elsewhere', template: 'Not kept', problem: 'Not saved', saving: 'Saving…', saved: 'Saved',
    draft: 'Not saved yet' }[status] ?? runWords(status)
  // a run puts a notice over the canvas and a log under it: the whole flow comes back into sight as it goes and ends
  // (a canvas that is not on screen has no size to fit into: that waits until it is shown again)
  useEffect(() => { if (active && shownRun) refit() }, [active, shownRun?.runId, shownRun?.status]) // eslint-disable-line react-hooks/exhaustive-deps
  const flowDoubts = useMemo(() => doubts.filter((d) => isStored && d.flow_id === flowId), [doubts, flowId, isStored])
  const stoppedHere = isStored ? needs.find((item) => item.kind === 'stopped' && item.flow === flowId) : undefined
  // a flow that stopped opens with its stopped node chosen, so that the strip says why and offers Try again; once for each stop
  useEffect(() => {
    if (!stoppedHere || opening || busy.current.chosen === `${view}:${stoppedHere.doubt}`) return
    if (!nodes.some((n) => n.id === stoppedHere.node)) return
    busy.current.chosen = `${view}:${stoppedHere.doubt}`
    setSelectedId(stoppedHere.node)
    setNodes((current) => current.map((n) => ({ ...n, selected: n.id === stoppedHere.node })))
  }, [stoppedHere, opening, view, nodes, setNodes])
  // what the stop adds (a notice's button, the reason under the canvas) takes room: the whole flow comes back into sight
  useEffect(() => { if (active && stoppedHere) refit() }, [active, stoppedHere?.doubt]) // eslint-disable-line react-hooks/exhaustive-deps
  const tryAgain = (item) => tried.tryAgain(item, async () => {
    if (!(await ensureStored())) throw new Error('The flow on screen could not be kept first, so it was not tried again.')
  })

  // What is known about each step, for the app the flow runs on: how far it is trusted, where it was adapted from, or
  // that nobody taught it for this app (a recipe hole left open).
  const viewNodes = useMemo(() => nodes.map((n) => {
    const node = n.data.node
    if (node.kind && node.kind !== 'step') return n
    const step = steps.find((s) => s.name === node.step && appKey(s.app) === appKey(node.technology))
    return { ...n, data: { ...n.data, meta: step ? { ...metaOf(step), hole: n.data.hole } : { missing: true, hole: n.data.hole } } }
  }), [nodes, steps])

  const selected = viewNodes.find((n) => n.id === selectedId)
  const selectedNode = selected?.data.node
  const nameOf = (id) => {
    const node = viewNodes.find((n) => n.id === id)
    return node ? titleOf(node.data.node) : id
  }
  const runKeys = useMemo(() => {
    try { return Object.keys(JSON.parse(context || '{}')) } catch { return [] }
  }, [context])
  const choose = (id) => { // the node on the canvas and the one the strip speaks about are one
    setSelectedId(id)
    setNodes((current) => current.map((n) => ({ ...n, selected: n.id === id })))
  }
  const openDetail = (id) => { setSelectedId(id); setDetailOpen(true); loadData(showValues) }
  const closeDetail = () => {
    const id = selectedId
    setDetailOpen(false)
    setTimeout(() => document.querySelector(`.react-flow__node[data-id="${id}"]`)?.focus(), 0)
  }
  const toggleValues = (on) => { setShowValues(on); loadData(on) }
  const numbers = useMemo(() => nodeNumbers(nodes, edges), [nodes, edges])
  const shownNodes = useMemo(
    () => viewNodes.map((n) => {
      const state = nodeState(shownRun, n.id) ?? (n.id === stoppedHere?.node ? 'blocked' : undefined) // a stop from earlier is red too
      return {
        ...n, className: `status-${state ?? 'pending'}`,
        data: { ...n.data, number: numbers[n.id], runStatus: state,
          onDaily: () => setSettingDaily((open) => !open), scheduled: Boolean(daily?.at) },
      }
    }),
    [viewNodes, numbers, shownRun, daily, stoppedHere],
  )
  const safety = useMemo(() => safetySummary(viewNodes), [viewNodes])
  const blocked = whyNotRunnable(safety)
  const paused = running && Object.values(shownRun.nodes).includes('paused')
  const loose = looseNodes(nodes, edges)
  // the lines the run went down: out of a node that got through, into a node it reached
  const went = (e) => ['done', 'continued'].includes(nodeState(shownRun, e.source))
    && !['unreached', undefined].includes(nodeState(shownRun, e.target))
  const shownEdges = edges.map((e) => ({ ...e, ...EDGE_LOOK, className: went(e) ? 'on' : '',
    ariaLabel: `Wire from ${nameOf(e.source)} to ${nameOf(e.target)}` }))
  const outcome = shownRun && !running && {
    waiting: 'This flow did not run: it stopped earlier and is waiting. Try again, or ask for help.',
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

        {!nodes.some(isDaily) && ( // a flow with no start node starts when Run is pressed: this gives it a time
          <button className="ghost daily-button" data-testid="daily-add" aria-expanded={settingDaily}
            title={daily?.at ? 'Windows runs this flow every day; it has no start node yet' : 'This flow starts when you press Run now'}
            onClick={() => setSettingDaily((open) => !open)}>
            <Icon name="clock" size={16} /> {daily?.at ? `Every day at ${daily.at}` : 'Run every day'}
          </button>
        )}

        <div className="spacer" />

        <div className="menu-anchor">
          <button className="ghost" data-testid="run-data" aria-expanded={menu === 'data'} onClick={() => setMenu(menu === 'data' ? null : 'data')}>
            Run data
          </button>
          {menu === 'data' && (
            <div className="menu wide">
              <label htmlFor="run-context">Starting values for this run, optional. Only nodes that read “Run data” use them.</label>
              <small data-testid="context-hint">{'{}'} means nothing: leave it so if the flow needs no starting values.</small>
              <textarea id="run-context" data-testid="context" value={context} rows={4} onChange={(e) => setContext(e.target.value)} />
            </div>
          )}
        </div>
        <button className="ghost" data-testid="undo" disabled={undoable === 0} onClick={undo}><Icon name="undo" size={16} /> Undo</button>
        {running ? (
          <button className="danger" data-testid="stop" disabled={!shownRun.armed} onClick={() => stop(shownRun.runId)}>
            <Icon name="stop" size={16} /> Stop
          </button>
        ) : (
          <button className="primary" data-testid="run" onClick={run} disabled={starting || nodes.length === 0 || Boolean(blocked)}
            title={nodes.length === 0 ? 'Add a node first' : blocked}>
            <Icon name="play" size={16} /> {starting ? 'Starting…' : 'Run now'}
          </button>
        )}
      </header>
      {settingDaily && ( // above the canvas, not over it: nothing on the canvas is covered
        <div className="start-strip">
          <DailyForm at={daily?.at} initial={daily?.node_at} submit={submitDaily} onDone={closeDaily} />
        </div>
      )}
      <div className="workspace">
      <div className="stage">
      <div className="canvas" role="region" aria-label="Nodes of this flow" onDrop={drop} onDragOver={(e) => e.preventDefault()}
        onKeyDownCapture={(e) => {
          if (e.key !== 'Enter' || !e.target.classList.contains('react-flow__node')) return
          e.preventDefault()
          e.stopPropagation()
          openDetail(e.target.dataset.id)
        }}>
        <div className="notices">
        {conflict && (
          <div className="notice notice-waiting" data-testid="changed-elsewhere" role="status">
            <span>{conflict}. Your changes are not kept yet.</span>
            <button className="small" onClick={keepMine}>Keep what I see</button>
            <button className="small" onClick={showTheirs}>Show the other version</button>
          </div>
        )}
        {unkept && template && (
          <div className="notice notice-waiting" data-testid="template-notice" role="status">
            <span>This is a template, so changes to it are not kept.</span>
            <button className="small" onClick={() => duplicate(flowId)}>Duplicate to edit</button>
          </div>
        )}
        {unkept && !template && !conflict && (held || problem) && (
          <div className="notice notice-waiting" data-testid="not-saved" role="status">
            <Icon name="alert" size={16} /> <span>Not saved: {held || problem}</span>
          </div>
        )}
        {removed && (
          <div className="notice" data-testid="removed-notice" role="status">
            <span>Removed “{removed}”.</span>
            <button className="small" onClick={undo}>Undo</button>
          </div>
        )}
        {blocked && (
          <div className="notice" role="status">
            <span data-testid="cannot-start">{blocked}</span>
            {safety.rejected.length > 0 && <button className="small" onClick={() => onOpen('apps')}>Open Apps</button>}
          </div>
        )}
        {outcome && (
          <div className={`notice notice-${shownRun.status}`} data-testid="run-outcome" role="status">
            <Icon name="alert" size={16} /> <span>{outcome}</span>
            {['waiting', 'stopped'].includes(shownRun.status) && stoppedHere && (
              <button className="small" data-testid="show-stopped" onClick={() => choose(stoppedHere.node)}>Show the stopped node</button>
            )}
          </div>
        )}
        {tried.tries[flowId] && <TriedResults tries={{ [flowId]: tried.tries[flowId] }} hide={tried.hide} />}
        {elsewhere.map(([name, r]) => (
          <div key={name} className="notice" data-testid="running-elsewhere" role="status">
            <span><b>{flowTitle(name, flows)}</b> is running now.{Object.values(r.nodes).includes('paused') && ` ${PAUSED_WORDS}`}</span>
            <button className="small" onClick={() => openFlow(name)}>Show it</button>
            <button className="danger small" disabled={!r.armed} onClick={() => stop(r.runId)}>Stop it</button>
          </div>
        ))}
        {loose.length > 0 && (
          <div className="notice" data-testid="unwired" role="status">
            <span>{loose.length === 1 ? '1 node is' : `${loose.length} nodes are`} not connected: what is not connected runs at the same time, in no set order.</span>
            <button className="small" onClick={() => { record(); setEdges(chainLoose(nodes, edges)) }}>Connect them in order</button>
          </div>
        )}
        <p className="sr-only" data-testid="editor-announce" role="status">{said}</p>
        {paused && (
          <div className="notice" data-testid="paused" role="status">
            <Icon name="pause" size={15} /> {PAUSED_WORDS}
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
          onNodeDragStart={() => record()}
          onBeforeDelete={async () => { record(); return true }}
          onNodeClick={(_, node) => setSelectedId(node.id)}
          onNodeDoubleClick={(_, node) => openDetail(node.id)}
          onPaneClick={() => setSelectedId(null)}
          deleteKeyCode={['Backspace', 'Delete']}
          colorMode="dark"
          fitView={framed}
          fitViewOptions={fit()}
          zoomOnDoubleClick={false}
          minZoom={0.15}
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="#26384C" />
          <Panel position="bottom-left" className="zoom">
            <button aria-label="Zoom in" onClick={() => zoomIn()}><Icon name="plus" size={20} /></button>
            <button aria-label="Zoom out" onClick={() => zoomOut()}><Icon name="minus" size={20} /></button>
            <button onClick={() => fitView({ ...fit(), duration: 200 })}>Show everything</button>
          </Panel>
        </ReactFlow>

        {shownRun && !shownRun.logClosed && (
          <RunLog log={shownRun.log} nodes={viewNodes} running={running}
            steps={viewNodes.map((n) => ({ id: n.id, number: numbers[n.id], state: nodeState(shownRun, n.id) ?? 'unreached' }))
              .sort((a, b) => (a.number ?? 1e9) - (b.number ?? 1e9))}
            onClose={() => { patch(flowId, { logClosed: true }); focusSoon('run') }} />
        )}

        {nodes.length === 0 && (
          <div className="empty-canvas">
            <p>Add your first node with “Add a node”.</p>
          </div>
        )}

        {selected && detailOpen && (
          <NodeDetail
            key={selected.id}
            node={selectedNode}
            meta={selected.data.meta}
            technologies={technologiesOf(steps, selectedNode.step)}
            drafts={selected.data.drafts}
            onDraft={draftSelected}
            refs={refOptions(viewNodes, selected.id, runKeys, (n) => titleOf(n.data.node))}
            data={nodeData[selected.id]}
            showValues={showValues}
            onShowValues={toggleValues}
            onChange={updateSelected}
            onClose={closeDetail}
          />
        )}

      </div>
          <ExplanationStrip node={selected} meta={selected?.data.meta} nodes={viewNodes} edges={edges}
            stopped={stoppedHere && selected?.id === stoppedHere.node ? stoppedHere : null} onTry={tryAgain} onChanged={refresh}
            trying={running || Boolean(tried.tries[flowId] && !tried.tries[flowId].result)}
            appName={selectedNode?.technology} context={context} onConnect={onConnect} onSettings={() => openDetail(selected.id)} onRemove={deleteSelected}
            onDisconnect={(edge) => { record(); setEdges((current) => current.filter((e) => e.id !== edge.id)) }}
            ensureSaved={async () => {
              const id = await ensureStored()
              if (!id) throw new Error('the flow was not saved, so nothing was tested')
              return id
            }}
            onTested={() => setTested((n) => n + 1)} />
      </div>
        <SearchPanel steps={steps} recipes={recipes} onAddSystem={addSystem}
          onAddStep={addStep} onAddRecipe={addRecipe} />
        {opening && <div className="opening" role="status">Opening…</div>}
      </div>
    </div>
  )
}
