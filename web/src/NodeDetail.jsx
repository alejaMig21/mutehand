import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { fieldsOf, showValue } from './bindings.js'
import { appLabel, chipFor, systemEntryFor, titleOf } from './catalog.js'
import FieldEditor from './FieldEditor.jsx'
import { Icon } from './icons.jsx'

const INPUT_TYPES = ['str', 'int', 'float', 'bool']
const POLICIES = [['stop', 'Stop and ask the tutor'], ['retry', 'Retry'], ['continue', 'Carry on without it']]

// The window over the dimmed canvas: what went in (Data in), the settings, what came out (Data out).
export default function NodeDetail({ node, meta, refs, data, showValues, onShowValues, onChange, onClose, onDelete, flowId, appName, context, ensureSaved, onTested }) {
  const system = node.kind && node.kind !== 'step'
  const entry = system && systemEntryFor(node)
  const chip = !system && meta?.app ? chipFor(meta.app) : null
  const title = titleOf(node)
  const subtitle = system ? entry?.hint ?? '' : meta?.app ? appLabel(meta.app) : ''
  const testable = node.kind === 'data' || !node.kind || node.kind === 'step'
  const physical = (!node.kind || node.kind === 'step') && meta?.action !== 'read_value'
  const [asking, setAsking] = useState(false)
  const [test, setTest] = useState({ state: 'idle' })
  const dialog = useRef(null)

  useEffect(() => { dialog.current?.focus() }, [])

  async function runTest() {
    setAsking(false)
    setTest({ state: 'running' })
    try {
      const values = JSON.parse(context || '{}')
      await ensureSaved()
      const { run_id } = await api(`/api/flows/${flowId}/nodes/${node.id}/test`, { method: 'POST', body: { app: appName, context: values } })
      for (;;) {
        const view = await api(`/api/runs/${run_id}`)
        if (view.status !== 'running') {
          setTest({ state: view.status === 'finished' ? 'ok' : 'failed', status: view.status })
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 250))
      }
      onTested()
    } catch (e) {
      setTest({ state: 'failed', status: e.message })
    }
  }

  const fields = fieldsOf(node, meta)
  const policy = node.on_failure ?? 'stop'

  return (
    <div className="scrim" onClick={onClose}>
      <div className="detail" role="dialog" aria-modal="true" aria-label={`${title} details`} data-testid="detail" tabIndex={-1}
        ref={dialog} onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.key === 'Escape' && onClose()}>
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
                onChange={(binding) => onChange({ fields: { ...node.fields, [spec.name]: binding } })} />
            ))}
            {fields.length === 0 && system && <p className="empty">Nothing to set on this node.</p>}

            {!system && (
              <>
                <label className="check">
                  <input type="checkbox" data-testid="exclusive" checked={Boolean(node.exclusive_input)}
                    onChange={(e) => onChange({ exclusive_input: e.target.checked })} />
                  needs the mouse or keyboard
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

        {asking && (
          <div className="warning" role="alertdialog" aria-label="Before the test" data-testid="test-warning">
            <p><b>This will use your mouse and keyboard</b> on {meta?.app ? appLabel(meta.app) : 'the app'}. Keep your hands off them until the test ends.</p>
            <div className="row">
              <button className="ghost small" onClick={() => setAsking(false)}>Cancel</button>
              <button className="primary small" data-testid="confirm-test" onClick={runTest}>Start the test</button>
            </div>
          </div>
        )}

        <footer className="detail-foot">
          <label className="check">
            <input type="checkbox" data-testid="show-values" checked={showValues} onChange={(e) => onShowValues(e.target.checked)} />
            Show values
          </label>
          <span className="test-result" role="status" data-testid="test-result">
            {test.state === 'running' && 'Testing…'}
            {test.state === 'ok' && 'Test finished'}
            {test.state === 'failed' && `Test did not finish: ${test.status}`}
          </span>
          <button className="danger small" data-testid="detail-delete" onClick={onDelete}><Icon name="trash" size={15} /> Delete node</button>
          <button className="primary small" data-testid="test-node" disabled={!testable || test.state === 'running'}
            title={testable ? '' : 'This kind of node is tested by running the flow'}
            onClick={() => (physical ? setAsking(true) : runTest())}>
            <Icon name="flask" size={15} /> Test this node
          </button>
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
