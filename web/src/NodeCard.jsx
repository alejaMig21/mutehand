import { Handle, Position } from '@xyflow/react'
import { appLabel, chipFor, systemEntryFor, titleOf } from './catalog.js'
import { Icon } from './icons.jsx'

// What a node is called and drawn as: a system node by its kind (and operation), a step by its app.
function describe(node, meta) {
  if (node.kind === 'trigger' && node.fields?.mode?.value === 'daily') {
    return { title: `Start: every day at ${node.fields.at?.value ?? '?'}`, icon: 'clock' } // the first node says when the flow runs
  }
  if (node.kind && node.kind !== 'step') return { title: titleOf(node), icon: systemEntryFor(node)?.icon ?? 'braces' }
  const app = node.technology || meta?.app
  return { title: node.step, subtitle: app ? appLabel(app) : '', chip: app ? chipFor(app) : null }
}

// Every mark is an icon and a word, never colour alone.
export const RUN_MARKS = {
  running: ['spinner', 'Running', 'info'], done: ['check', 'Done', 'ok'], blocked: ['alert', 'Stopped here', 'bad'],
  unreached: ['clock', 'Not reached', 'muted'], continued: ['skip', 'Carried on', 'warn'], paused: ['pause', 'Paused: you moved the mouse', 'warn'],
}
// A rejected step blocks the flow, so it is said on its node; how far a step is trusted is not.
const REJECTED = ['xcircle', 'Blocked', 'bad']

export function marksFor(node, meta, runStatus) {
  const marks = []
  if (RUN_MARKS[runStatus]) marks.push(RUN_MARKS[runStatus])
  if (!node.kind || node.kind === 'step') {
    if (meta?.missing) marks.push(['alert', meta.hole ? `Hole not filled: ${meta.hole.hole}` : 'Not taught for this app', 'bad'])
    if (meta?.adapted_from) marks.push(['arrow', `Adapted from ${appLabel(meta.adapted_from)}`, 'info'])
    if (meta?.state === 'rejected') marks.push(REJECTED)
    if (meta?.consent === 'given') marks.push(['lock', 'Consent given', 'muted'])
    if (meta?.consent === 'missing') marks.push(['lock', 'Needs consent', 'warn'])
    if (meta?.private) marks.push(['eyeoff', 'Private app', 'muted'])
  }
  return marks
}

export default function NodeCard({ id, data, selected }) {
  const { node, meta, number, runStatus } = data
  const { title, subtitle, icon, chip } = describe(node, meta)
  const marks = marksFor(node, meta, runStatus)
  const daily = node.kind === 'trigger' && node.fields?.mode?.value === 'daily'
  if (daily && !data.scheduled) marks.push(['alert', 'Not set up in Windows yet', 'warn'])
  if (Object.values(data.drafts ?? {}).some(Boolean)) marks.push(['alert', 'Not saved: a value is not valid yet', 'bad'])
  return (
    <div className={`card${selected ? ' selected' : ''}`} data-testid={`node-${id}`}>
      <Handle type="target" position={Position.Top} />
      <div className="card-head">
        {chip
          ? <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
          : <span className="chip system" aria-hidden="true"><Icon name={icon} /></span>}
        <div className="card-text">
          <div className="card-title">{number ? `${number}. ${title}` : title}</div>
          {subtitle && <div className="card-sub">{subtitle}</div>}
        </div>
      </div>
      {marks.length > 0 && (
        <div className="card-marks">
          {marks.map(([glyph, word, tone]) => (
            <div key={word} className={`card-mark tone-${tone}`}>
              <Icon name={glyph} size={14} /> {word}
            </div>
          ))}
        </div>
      )}
      {daily && (
        <button type="button" className="daily-button nodrag" data-testid="daily-change" onClick={data.onDaily}>
          {data.scheduled ? 'Change the time' : 'Set up the daily run'}
        </button>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
