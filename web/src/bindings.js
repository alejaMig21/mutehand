// How a node's fields are edited: as a fixed value or as a reference to another node's output. Pure, so node can test it.
//
// A stored field is exactly one of { value }, { ref: { node, field } } or { expression } (see data.py).

export const KINDS = [
  ['text', 'Text'],
  ['number', 'Number'],
  ['boolean', 'True or false'],
  ['json', 'List or object'],
]

export function kindOf(value) {
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'string' || value === undefined || value === null) return 'text'
  return 'json'
}

// What the person typed, read as the kind they chose. Never guesses: a bad number is an error, not a text.
export function parseValue(kind, text) {
  if (kind === 'text') return { ok: true, value: text }
  if (kind === 'boolean') return { ok: true, value: text === 'true' }
  if (kind === 'number') {
    const n = Number(text)
    return text.trim() !== '' && Number.isFinite(n) ? { ok: true, value: n } : { ok: false, error: 'Type a number' }
  }
  try {
    const value = JSON.parse(text)
    return value !== null && typeof value === 'object' ? { ok: true, value } : { ok: false, error: 'Type a list [..] or an object {..}' }
  } catch {
    return { ok: false, error: 'This is not a valid list or object' }
  }
}

export const showValue = (value) => (typeof value === 'string' ? value : JSON.stringify(value))

// The fields each node has, with the choices a field is limited to. Mirrors dataops.py and flow.py.
const OPERATORS = ['equals', 'not_equals', 'greater', 'greater_or_equal', 'less', 'less_or_equal', 'contains', 'starts_with', 'ends_with']
export const FIELD_SPECS = {
  trigger: [{ name: 'at', label: 'Time (HH:MM)', when: (node) => node.fields?.mode?.value === 'daily' }],
  wait: [{ name: 'seconds', label: 'Seconds to wait' }],
  foreach: [{ name: 'items', label: 'Items' }],
  if: [{ name: 'condition', label: 'Condition (true or false)' }],
  'data:fixed': [{ name: 'value', label: 'Value' }],
  'data:convert': [{ name: 'value', label: 'Value' }, { name: 'to', label: 'Convert to', options: ['text', 'number', 'integer', 'boolean'] }],
  'data:split': [{ name: 'text', label: 'Text' }, { name: 'separator', label: 'Separator' }, { name: 'trim', label: 'Trim the pieces', optional: true }],
  'data:join': [{ name: 'items', label: 'Items' }, { name: 'separator', label: 'Separator' }],
  'data:format': [{ name: 'template', label: 'Template, with {names}' }, { name: 'values', label: 'Values (object)' }],
  'data:regex': [{ name: 'text', label: 'Text' }, { name: 'pattern', label: 'Pattern' }],
  'data:get': [{ name: 'object', label: 'Object or list' }, { name: 'path', label: 'Path, like a.b.0' }],
  'data:set': [{ name: 'object', label: 'Object' }, { name: 'path', label: 'Path, like a.b' }, { name: 'value', label: 'Value to write' }],
  'data:math': [{ name: 'a', label: 'First number' }, { name: 'b', label: 'Second number' },
    { name: 'operation', label: 'Operation', options: ['add', 'subtract', 'multiply', 'divide', 'modulo', 'power'] }],
  'data:compare': [{ name: 'a', label: 'First value' }, { name: 'b', label: 'Second value' }, { name: 'operator', label: 'Compare', options: OPERATORS }],
  'data:and': [{ name: 'a', label: 'First (true or false)' }, { name: 'b', label: 'Second (true or false)' }],
  'data:or': [{ name: 'a', label: 'First (true or false)' }, { name: 'b', label: 'Second (true or false)' }],
  'data:not': [{ name: 'a', label: 'Value (true or false)' }],
}

// The editable fields of a node. A step that types text takes a `text` field.
export function fieldsOf(node, meta = {}) {
  if (!node.kind || node.kind === 'step') return meta.action === 'type_value' ? [{ name: 'text', label: 'Text to type' }] : []
  const specs = FIELD_SPECS[node.kind === 'data' ? `data:${node.op}` : node.kind] ?? []
  return specs.filter((spec) => !spec.when || spec.when(node))
}

// What a node gives out, by name, so another node can point at it.
export function outputFieldsOf(node, meta = {}) {
  if (!node.kind || node.kind === 'step') return meta.action === 'read_value' ? ['value', 'effect'] : ['effect']
  if (node.kind === 'data') return node.op === 'regex' ? ['value', 'match', 'groups'] : ['value']
  if (node.kind === 'foreach') return ['item', 'index', 'count']
  if (node.kind === 'wait') return ['waited']
  return []
}

// The list a person picks a reference from: the run's starting data, then every other node's outputs.
export function refOptions(nodes, selectedId, runKeys = [], titleOf = (n) => n.data.node.step || n.data.node.kind) {
  const options = runKeys.map((field) => ({ node: 'run', field, label: `Run data · ${field}` }))
  for (const n of nodes) {
    if (n.id === selectedId) continue
    for (const field of outputFieldsOf(n.data.node, n.data.meta)) {
      options.push({ node: n.id, field, label: `${titleOf(n)} (${n.id}) · ${field}` })
    }
  }
  return options
}

export const refKey = (ref) => `${ref.node}.${ref.field}`
