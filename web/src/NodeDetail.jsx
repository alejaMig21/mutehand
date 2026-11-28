import { useEffect, useRef } from 'react'
import { fieldsOf, showValue } from './bindings.js'
import { appLabel, chipFor, systemEntryFor, titleOf } from './catalog.js'
import AppSelect from './AppSelect.jsx'
import FieldEditor from './FieldEditor.jsx'
import { Icon } from './icons.jsx'

const INPUT_TYPES = ['str', 'int', 'float', 'bool']
const POLICIES = [['stop', 'Stop and ask the tutor'], ['retry', 'Retry'], ['continue', 'Carry on without it']]

// The window over the dimmed canvas: what went in (Data in), the settings, what came out (Data out).
export default function NodeDetail({ node, meta, technologies, drafts, onDraft, refs, data, showValues, onShowValues, onChange, onClose }) {
  const system = node.kind && node.kind !== 'step'
  const entry = system && systemEntryFor(node)
  const app = node.technology || meta?.app
  const chip = !system && app ? chipFor(app) : null
  const title = titleOf(node)
  const subtitle = system ? entry?.hint ?? '' : app ? appLabel(app) : ''
  const dialog = useRef(null)

  useEffect(() => { dialog.current?.focus() }, [])

  // a modal window keeps the keyboard until it is closed
  function onKeys(event) {
    if (event.key === 'Escape') {
      onClose()
      return
    }
    if (event.key !== 'Tab') return
    const inside = [...dialog.current.querySelectorAll('button, input, select, textarea, [tabindex="0"]')].filter((el) => !el.disabled)
    const [first, last] = [inside[0], inside[inside.length - 1]]
    const at = document.activeElement
    if (event.shiftKey && (at === first || at === dialog.current)) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && at === last) { event.preventDefault(); first.focus() }
  }

  const fields = fieldsOf(node, meta)
  const policy = node.on_failure ?? 'stop'

  return (
    <div className="scrim" onClick={onClose}>
      <div className="detail" role="dialog" aria-modal="true" aria-label={`${title} details`} data-testid="detail" tabIndex={-1}
        ref={dialog} onClick={(e) => e.stopPropagation()} onKeyDown={onKeys}>
        <header className="detail-head">
          {chip
            ? <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
            : <span className="chip system" aria-hidden="true"><Icon name={entry?.icon ?? 'braces'} /></span>}
          <div><h2>{title}</h2><div className="card-sub">{subtitle}</div></div>
          <button className="icon-button close" data-testid="close-detail" aria-label="Close the details" onClick={onClose}><Icon name="close" /></button>
        </header>

        <div className="panes">
          <section aria-label="Data in" className="pane">
            <h3>Data in</h3>
            <DataRows rows={data?.in} showValues={showValues} />
          </section>

          <section aria-label="Settings" className="pane settings-pane">
            <h3>Settings</h3>
            {fields.map((spec) => (
              <FieldEditor key={`${node.id}-${spec.name}`} spec={spec} binding={node.fields?.[spec.name]} refs={refs}
                draft={drafts?.[spec.name]} onDraft={(draft) => onDraft(spec.name, draft)}
                onChange={(binding) => onChange({ fields: { ...node.fields, [spec.name]: binding } })} />
            ))}
            {fields.length === 0 && system && <p className="empty">Nothing to set on this node.</p>}

            {!system && (
              <>
                <div className="field">
                  <label htmlFor="node-technology" className="field-label">Runs on</label>
                  <AppSelect id="node-technology" data-testid="node-technology" apps={technologies ?? []} value={node.technology ?? ''}
                    onChange={(technology) => onChange({ technology })} />
                </div>
                <label className="check">
                  <input type="checkbox" data-testid="exclusive" checked={Boolean(node.exclusive_input)}
                    onChange={(e) => onChange({ exclusive_input: e.target.checked })} />
                  Needs the mouse or keyboard
                </label>
                <h4>Typed inputs</h4>
                {node.inputs.map(([name, type], i) => (
                  <div className="row" key={i}>
                    <input aria-label="input name" value={name} onChange={(e) =>
                      onChange({ inputs: node.inputs.map((p, j) => (j === i ? [e.target.value, p[1]] : p)) })} />
                    <select aria-label="input type" value={type} onChange={(e) =>
                      onChange({ inputs: node.inputs.map((p, j) => (j === i ? [p[0], e.target.value] : p)) })}>
                      {INPUT_TYPES.map((t) => <option key={t}>{t}</option>)}
                    </select>
                  </div>
                ))}
                <button className="ghost small" data-testid="add-input" onClick={() => onChange({ inputs: [...node.inputs, ['value', 'str']] })}>
                  Add input
                </button>
              </>
            )}

            {(!system || node.kind === 'data') && (
              <div className="field">
                <label htmlFor="on-failure" className="field-label">If this node fails</label>
                <div className="field-row">
                  <select id="on-failure" data-testid="on-failure" value={policy} onChange={(e) => onChange({ on_failure: e.target.value })}>
                    {POLICIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                  {policy === 'retry' && (
                    <input type="number" min="1" max="10" aria-label="How many retries" data-testid="retries" value={node.retries ?? 3}
                      onChange={(e) => onChange({ retries: Math.min(10, Math.max(1, Number(e.target.value) || 1)) })} />
                  )}
                </div>
              </div>
            )}
          </section>

          <section aria-label="Data out" className="pane">
            <h3>Data out</h3>
            <DataRows rows={data?.out} showValues={showValues} />
          </section>
        </div>

        <footer className="detail-foot">
          <label className="check">
            <input type="checkbox" data-testid="show-values" checked={showValues} onChange={(e) => onShowValues(e.target.checked)} />
            Show values
          </label>
        </footer>
      </div>
    </div>
  )
}

function DataRows({ rows, showValues }) {
  const entries = Object.entries(rows ?? {})
  if (entries.length === 0) return <p className="empty">No data yet. Run the flow or test this node.</p>
  return (
    <dl className="data-rows">
      {entries.map(([name, value]) => (
        <div key={name} className="data-row">
          <dt>{name}</dt>
          <dd data-testid={`data-${name}`}>{showValues ? showValue(value) : describe(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

// A hidden value shows only what it is: "text · 12 characters", "list · 3 items".
function describe(shape) {
  if (shape.size === undefined) return shape.type
  const unit = { text: 'characters', list: 'items', object: 'fields' }[shape.type]
  return `${shape.type} · ${shape.size} ${unit}`
}
