import { titleOf } from './catalog.js'
import { Icon } from './icons.jsx'

// What can be done with the selected node without a mouse: open it, wire it, remove a wire, delete it.
export default function NodePanel({ node, nodes, edges, onConnect, onDisconnect, onOpen, onDelete }) {
  const out = edges.filter((e) => e.source === node.id)
  const nameOf = (id) => {
    const found = nodes.find((n) => n.id === id)
    return found ? `${titleOf(found.data.node)} (${id})` : id
  }
  const free = nodes.filter((n) => n.id !== node.id && !out.some((e) => e.target === n.id))

  return (
    <section className="settings" aria-label="Selected node">
      <h2>{titleOf(node.data.node)}</h2>
      <button className="ghost small" data-testid="open-detail" onClick={onOpen}>Open details</button>
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
      <button className="ghost small quiet-danger" data-testid="delete-node" onClick={onDelete}>
        <Icon name="trash" size={15} /> Delete node
      </button>
    </section>
  )
}
