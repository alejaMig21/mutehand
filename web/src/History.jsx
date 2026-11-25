import { useLoad } from './useLoad.js'

// What each run did and what stopped it. Data values are never recorded, so there is nothing to hide.
export default function History() {
  const { data: runs, error, reload } = useLoad('/api/history')

  return (
    <section>
      <h1>Run history</h1>
      <button onClick={reload}>Refresh</button>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}
      {runs.length === 0 && <p data-testid="no-runs">No runs yet.</p>}
      {runs.map((run) => (
        <div key={run.id} data-testid={`run-${run.id}`} className="run">
          <h2>{run.flow_id} <small data-testid={`run-status-${run.id}`}>{run.status}</small></h2>
          <div>{run.started_at}{run.stopped_node ? ` · stopped at ${run.stopped_node}` : ''}</div>
          <ul>
            {run.nodes.map((node) => (
              <li key={node.node_id}>
                {node.node_id}: {node.status}{node.reason ? ` (${node.reason})` : ''}{node.effect ? ` · effect ${node.effect}` : ''}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
