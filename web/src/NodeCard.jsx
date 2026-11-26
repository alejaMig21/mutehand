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

// Every mark is an icon and a word, never colour alone.
const RUN_MARKS = {
  running: ['spinner', 'Running', 'info'], done: ['checkcircle', 'Done', 'ok'], blocked: ['alert', 'Stopped', 'bad'],
  skipped: ['skip', 'Skipped', 'muted'], continued: ['skip', 'Carried on', 'warn'], paused: ['pause', 'Paused for you', 'warn'],
}
const TRUST_MARKS = {
  trusted: ['checkcircle', 'Trusted', 'ok'], suspect: ['half', 'On trial', 'warn'], rejected: ['xcircle', 'Rejected', 'bad'],
  to_revalidate: ['half', 'Needs a re-check', 'warn'],
}

export function marksFor(node, meta, runStatus, doubts) {
  const marks = []
  if (RUN_MARKS[runStatus]) marks.push(RUN_MARKS[runStatus])
  if (!node.kind || node.kind === 'step') {
    if (meta?.missing) marks.push(['alert', meta.hole ? `Hole not filled: ${meta.hole.hole}` : 'Not taught for this app', 'bad'])
    if (meta?.adapted_from) marks.push(['arrow', `Adapted from ${appLabel(meta.adapted_from)}`, 'info'])
    if (TRUST_MARKS[meta?.state]) marks.push(TRUST_MARKS[meta.state])
    if (meta?.consent === 'given') marks.push(['lock', 'Consent given', 'muted'])
    if (meta?.consent === 'missing') marks.push(['lock', 'Needs consent', 'warn'])
    if (meta?.private) marks.push(['eyeoff', 'Private app', 'muted'])
  }
  if (doubts > 0) marks.push(['help', doubts === 1 ? '1 doubt' : `${doubts} doubts`, 'warn'])
  return marks
}

export default function NodeCard({ id, data, selected }) {
  const { node, meta, runStatus, doubts } = data
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
      {marksFor(node, meta, runStatus, doubts).map(([glyph, word, tone]) => (
        <div key={word} className={`card-mark tone-${tone}`}><Icon name={glyph} size={14} /> {word}</div>
      ))}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
