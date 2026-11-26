import { Handle, Position } from '@xyflow/react'
import { appLabel, chipFor, systemEntryFor, titleOf } from './catalog.js'
import { Icon } from './icons.jsx'

// What a node is called and drawn as: a system node by its kind (and operation), a step by its app.
function describe(node, meta) {
  if (node.kind && node.kind !== 'step') {
    const known = systemEntryFor(node)
    return { title: titleOf(node), subtitle: known?.group ?? 'System node', icon: known?.icon ?? 'braces' }
  }
  const app = meta?.app
  return { title: node.step, subtitle: app ? appLabel(app) : 'Step', chip: app ? chipFor(app) : null }
}

export default function NodeCard({ id, data, selected }) {
  const { node, meta } = data
  const { title, subtitle, icon, chip } = describe(node, meta)
  return (
    <div className={`card${selected ? ' selected' : ''}`} data-testid={`node-${id}`}>
      <Handle type="target" position={Position.Left} />
      <div className="card-head">
        {chip
          ? <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
          : <span className="chip system" aria-hidden="true"><Icon name={icon} /></span>}
        <div className="card-text">
          <div className="card-title">{title}</div>
          <div className="card-sub">{subtitle}</div>
        </div>
      </div>
      {meta?.sensitive && <div className="card-mark"><Icon name="lock" size={14} /> Needs consent</div>}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
