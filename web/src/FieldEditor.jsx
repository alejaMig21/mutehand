import { useState } from 'react'
import { kindOf, KINDS, parseValue, refKey, showValue } from './bindings.js'

// One field of a node: a fixed value (typed as text, number, true or false, or a list or object) or a reference
// picked from a list of what other nodes give out. A stored expression is shown as it is and cannot be edited yet.
export default function FieldEditor({ spec, binding, draft, refs, onChange, onDraft }) {
  const mode = binding && 'ref' in binding ? 'ref' : binding && 'expression' in binding ? 'expression' : 'value'
  const current = binding && 'value' in binding ? binding.value : undefined
  const [kind, setKind] = useState(draft?.kind ?? kindOf(current))
  const [text, setText] = useState(draft?.text ?? (current === undefined ? '' : showValue(current)))
  const error = draft?.error ?? ''
  const id = `field-${spec.name}`

  function setValueFrom(nextKind, nextText) {
    const parsed = parseValue(nextKind, nextText)
    // text that is not a value yet is kept as typed: saving waits until it is one
    onDraft(parsed.ok ? null : { kind: nextKind, text: nextText, error: parsed.error, label: spec.label })
    if (parsed.ok) onChange({ value: parsed.value })
  }

  if (mode === 'expression') {
    return <div className="field"><span className="field-label">{spec.label}</span><code>{binding.expression}</code></div>
  }
  return (
    <div className="field" data-testid={`field-${spec.name}`}>
      <label htmlFor={id} className="field-label">{spec.label}</label>
      <div className="field-row">
        <select aria-label={`${spec.label}: where it comes from`} value={mode} data-testid={`mode-${spec.name}`}
          onChange={(e) => {
            if (e.target.value !== 'ref') {
              setValueFrom(kind, text)
              return
            }
            onDraft(null)
            onChange(refs[0] ? { ref: { node: refs[0].node, field: refs[0].field } } : { value: current })
          }}>
          <option value="value">Fixed value</option>
          <option value="ref" disabled={refs.length === 0}>From another node</option>
        </select>
        {mode === 'ref' ? (
          <select id={id} aria-label={`${spec.label}: which node`} data-testid={`ref-${spec.name}`}
            value={refKey(binding.ref)} onChange={(e) => {
              const picked = refs.find((r) => refKey(r) === e.target.value)
              onChange({ ref: { node: picked.node, field: picked.field } })
            }}>
            {!refs.some((r) => refKey(r) === refKey(binding.ref)) && <option value={refKey(binding.ref)}>{refKey(binding.ref)} (missing)</option>}
            {refs.map((r) => <option key={refKey(r)} value={refKey(r)}>{r.label}</option>)}
          </select>
        ) : spec.options ? (
          <select id={id} value={String(current ?? spec.options[0])} data-testid={`value-${spec.name}`}
            onChange={(e) => onChange({ value: e.target.value })}>
            {spec.options.map((o) => <option key={o}>{o}</option>)}
          </select>
        ) : (
          <>
            <select aria-label={`${spec.label}: kind of value`} value={kind} data-testid={`kind-${spec.name}`}
              onChange={(e) => {
                setKind(e.target.value)
                const next = e.target.value === 'boolean' ? 'true' : e.target.value === 'json' ? '[]' : e.target.value === 'number' ? '0' : text
                setText(next)
                setValueFrom(e.target.value, next)
              }}>
              {KINDS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
            {kind === 'boolean' ? (
              <select id={id} value={text} data-testid={`value-${spec.name}`}
                onChange={(e) => { setText(e.target.value); setValueFrom(kind, e.target.value) }}>
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            ) : (
              <input id={id} value={text} data-testid={`value-${spec.name}`} aria-invalid={Boolean(error)}
                onChange={(e) => { setText(e.target.value); setValueFrom(kind, e.target.value) }} />
            )}
          </>
        )}
      </div>
      {error && <div className="field-error" role="alert">{error}</div>}
    </div>
  )
}
