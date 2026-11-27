import { useState } from 'react'
import { StoppedActions } from './Attention.jsx'
import { api, encode } from './api.js'
import { appLabel, titleOf } from './catalog.js'
import { fieldsOf } from './bindings.js'
import { Icon } from './icons.jsx'
import { sentenceOf, workedWords } from './sentences.js'
import { stoppedWords } from './stopped.js'
import { reasonWords, runWords } from './words.js'

// What a box asks before a test: the ones that move the mouse or press keys. A data box and a read touch no control.
const touchesTheScreen = (node, meta) => (!node.kind || node.kind === 'step') && meta?.action !== 'read_value'
const testable = (node) => node.kind === 'data' || !node.kind || node.kind === 'step'
// Settings exist for a step (failure setting, inputs), a data box and any box with a field of its own.
const hasSettings = (node, meta) => !node.kind || node.kind === 'step' || node.kind === 'data' || fieldsOf(node, meta).length > 0

// Under the canvas, always, so that choosing a box never moves the canvas: what the chosen box does, how often it has worked,
// and what can be done with it. Keyed by the box, so a test result never outlives the choice. The wires stay reachable here
// without a mouse.
export default function ExplanationStrip(props) {
  const { node } = props
  if (!node) {
    return (
      <section className="strip" aria-label="About the chosen box" data-testid="strip">
        <p className="strip-says">Choose a box to see what it does.</p>
      </section>
    )
  }
  return <ChosenBox key={node.id} {...props} />
}

function ChosenBox({ node, meta, nodes, edges, appName, context, ensureSaved, onTested, onConnect, onDisconnect,
  onSettings, onRemove, stopped, onTry, onChanged, trying }) {
  const [asking, setAsking] = useState(false)
  const [test, setTest] = useState({ state: 'idle' })
  const box = node.data.node
  const [before, name, after] = sentenceOf(box, meta, appName)
  const worked = !box.kind || box.kind === 'step' ? workedWords(meta) : ''

  const out = edges.filter((e) => e.source === node.id)
  const nameOf = (id) => {
    const found = nodes.find((n) => n.id === id)
    return found ? `${titleOf(found.data.node)} (${id})` : id
  }
  const free = nodes.filter((n) => n.id !== node.id && !out.some((e) => e.target === n.id))

  async function runTest() {
    setAsking(false)
    setTest({ state: 'running' })
    try {
      const values = JSON.parse(context || '{}')
      const flowId = await ensureSaved() // a flow never saved before gets its identifier here
      const { run_id } = await api(`/api/flows/${encode(flowId)}/nodes/${box.id}/test`, { method: 'POST', body: { context: values } })
      for (;;) {
        const view = await api(`/api/runs/${run_id}`).catch((e) => {
          if (e.status) throw e
          return { status: 'running', lost: true } // a lost request: ask again
        })
        if (view.status === 'running') setTest({ state: 'running', lost: view.lost })
        if (view.status !== 'running') {
          setTest({ state: view.status === 'finished' ? 'ok' : 'failed', status: view.status })
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 250))
      }
      onTested()
    } catch (e) {
      setTest({ state: 'failed', error: e.message })
    }
  }

  return (
    <section className="strip" aria-label="About the chosen box" data-testid="strip">
      <h2>{titleOf(box)}</h2>
      <p className="strip-says" data-testid="strip-says">
        {before}{name && <strong>{name}</strong>}{after}
        {worked && <> <span data-testid="strip-worked">{worked}</span></>}
      </p>
      {stopped && (
        <p className="strip-reason tone-bad" data-testid="strip-reason">
          <Icon name="alert" size={18} /> <span><b>Stopped here.</b> {reasonWords(stopped.reason)} <span className="muted">{stoppedWords(stopped).hint}</span></span>
        </p>
      )}
      <div className="strip-actions">
        {stopped && <StoppedActions item={stopped} prefix="strip" onTry={onTry} onChanged={onChanged} trying={trying} />}
        {testable(box) && (
          <button className="primary" data-testid="test-node" disabled={test.state === 'running' || asking}
            onClick={() => (touchesTheScreen(box, meta) ? setAsking(true) : runTest())}>
            <Icon name="flask" size={15} /> Test this box
          </button>
        )}
        {hasSettings(box, meta) && <button data-testid="open-detail" onClick={onSettings}>Settings</button>}
        <button className="quiet-danger" data-testid="delete-node" onClick={onRemove}><Icon name="trash" size={15} /> Remove box</button>
        <span className="test-result" role="status" data-testid="test-result">
          {test.state === 'running' && (test.lost ? 'Testing… the editor cannot reach the server, still trying.' : 'Testing…')}
          {test.state === 'ok' && 'Test finished'}
          {test.state === 'failed' && `Test did not finish: ${test.error ?? runWords(test.status)}`}
        </span>
      </div>
      {asking && (
        <div className="warning" role="alertdialog" aria-label="Before the test" aria-describedby="test-warning-words" data-testid="test-warning">
          <p id="test-warning-words"><b>This will use your mouse and keyboard</b> on {meta?.app ? appLabel(meta.app) : 'the app'}. Keep your hands off them until the test ends.</p>
          <div className="row">
            <button className="small" onClick={() => setAsking(false)}>Cancel</button>
            <button className="primary small" data-testid="confirm-test" autoFocus onClick={runTest}>Start the test</button>
          </div>
        </div>
      )}
      {(out.length > 0 || free.length > 0) && (
        <div className="strip-wires">
          {out.length > 0 && (
            <ul className="wires" aria-label="Goes to">
              {out.map((edge) => (
                <li key={edge.id}>
                  <span>{edge.label ? `${edge.label}: ` : 'then: '}{nameOf(edge.target)}</span>
                  <button className="icon-button" aria-label={`Remove the wire to ${nameOf(edge.target)}`} onClick={() => onDisconnect(edge)}>
                    <Icon name="close" size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {free.length > 0 && (
            <select aria-label="Connect this node to" data-testid="connect-to" value=""
              onChange={(e) => onConnect({ source: node.id, target: e.target.value })}>
              <option value="" disabled>Connect to…</option>
              {free.map((n) => <option key={n.id} value={n.id}>{nameOf(n.id)}</option>)}
            </select>
          )}
        </div>
      )}
    </section>
  )
}
