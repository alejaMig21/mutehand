import { useEffect, useState } from 'react'
import { api, encode } from './api.js'
import { titleOf } from './catalog.js'
import Screen from './Screen.jsx'
import { useLoad } from './useLoad.js'
import { effectWords, flowWords, reasonWords, runWords, whenWords } from './words.js'

const TONES = { finished: 'ok', stopped: 'bad', error: 'bad', emergency: 'warn' }
const NODE_WORDS = { done: 'done', blocked: 'stopped', skipped: 'skipped', continued: 'failed, carried on' }

// The history stores node ids; the flows say what each node is called.
function useNames(runs) {
  const [names, setNames] = useState({})
  const ids = [...new Set(runs.map((run) => run.flow_id.split('#')[0]))].join('|')
  useEffect(() => {
    for (const id of ids.split('|').filter(Boolean)) {
      api(`/api/flows/${encode(id)}`)
        .then((flow) => setNames((all) => ({ ...all, [id]: Object.fromEntries(flow.nodes.map((n) => [n.id, titleOf(n)])) })))
        .catch(() => {}) // a flow that is gone keeps its node ids
    }
  }, [ids])
  return (flowId, nodeId) => names[flowId.split('#')[0]]?.[nodeId] ?? nodeId
}

// What each run did and what stopped it. Data values are never recorded, so there is nothing to hide.
export default function History() {
  const load = useLoad('/api/history')
  const nameOf = useNames(load.data)
  // a node is called by the step it ran; the flow only names what ran no step
  const called = (run, id) => run.nodes.find((n) => n.node_id === id)?.step || nameOf(run.flow_id, id)

  return (
    <Screen title="Run history" help="What each run did, newest first." load={load} isEmpty={load.data.length === 0} emptyId="no-runs"
      empty="No runs yet. Open a flow and press Run flow." tools={<button className="small" onClick={load.reload}>Refresh</button>}>
      <ul className="cards">
        {load.data.map((run) => (
          <li key={run.id} data-testid={`run-${run.id}`}>
            <div className="card-body">
              <h2>
                {flowWords(run.flow_id)}{' '}
                <span className={`badge tone-${TONES[run.status] ?? 'muted'}`} data-testid={`run-status-${run.id}`}>{runWords(run.status)}</span>
              </h2>
              <small>{whenWords(run.started_at)}{run.stopped_node ? ` · stopped at ${called(run, run.stopped_node)}` : ''}</small>
              <ol>
                {run.nodes.map((node) => (
                  <li key={node.node_id}>
                    <b>{called(run, node.node_id)}</b>: {NODE_WORDS[node.status] ?? node.status}
                    {node.reason ? <span className="tone-bad"> — {reasonWords(node.reason)}</span> : null}
                    {node.effect ? <small> ({effectWords(node.effect)})</small> : null}
                  </li>
                ))}
              </ol>
            </div>
          </li>
        ))}
      </ul>
    </Screen>
  )
}
