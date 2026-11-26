import assert from 'node:assert/strict'
import test from 'node:test'
import { fieldsOf, kindOf, outputFieldsOf, parseValue, refOptions, showValue } from './bindings.js'
import { SYSTEM_NODES } from './catalog.js'

test('a value is read as the kind the person chose and never guessed', () => {
  assert.deepEqual(parseValue('text', ' 12 '), { ok: true, value: ' 12 ' })
  assert.deepEqual(parseValue('number', '12.5'), { ok: true, value: 12.5 })
  assert.equal(parseValue('number', 'abc').ok, false)
  assert.equal(parseValue('number', '').ok, false)
  assert.deepEqual(parseValue('boolean', 'true'), { ok: true, value: true })
  assert.deepEqual(parseValue('json', '[1,2]'), { ok: true, value: [1, 2] })
  assert.equal(parseValue('json', '3').ok, false)
  assert.equal(parseValue('json', '{oops').ok, false)
})

test('the kind of a stored value says how to edit it', () => {
  assert.deepEqual([true, 3, 'a', [1], { a: 1 }, null].map(kindOf), ['boolean', 'number', 'text', 'json', 'json', 'text'])
  assert.equal(showValue('a'), 'a')
  assert.equal(showValue([1]), '[1]')
})

test('every system node exposes the fields its operation needs, and no field it does not have', () => {
  for (const entry of SYSTEM_NODES) {
    const specs = fieldsOf(entry.node)
    const names = specs.map((f) => f.name)
    for (const name of specs.filter((f) => !f.optional).map((f) => f.name)) assert.ok(name in (entry.node.fields ?? {}) || entry.node.kind === 'trigger', `${entry.key}: ${name}`)
    for (const name of Object.keys(entry.node.fields ?? {})) {
      if (entry.node.kind === 'trigger' && name === 'mode') continue
      assert.ok(names.includes(name), `${entry.key} should let you edit ${name}`)
    }
  }
})

test('a daily trigger has a time to edit and a manual one does not', () => {
  assert.deepEqual(fieldsOf({ kind: 'trigger', fields: { mode: { value: 'daily' } } }).map((f) => f.name), ['at'])
  assert.deepEqual(fieldsOf({ kind: 'trigger', fields: { mode: { value: 'manual' } } }), [])
})

test('a step takes a text field only when it types text', () => {
  assert.deepEqual(fieldsOf({ step: 'x' }, { action: 'type_value' }).map((f) => f.name), ['text'])
  assert.deepEqual(fieldsOf({ step: 'x' }, { action: 'click' }), [])
})

test('what a node gives out can be pointed at, with the choices limited to what exists', () => {
  assert.deepEqual(outputFieldsOf({ step: 'x' }, { action: 'read_value' }), ['value', 'effect'])
  assert.deepEqual(outputFieldsOf({ kind: 'data', op: 'regex' }), ['value', 'match', 'groups'])
  assert.deepEqual(outputFieldsOf({ kind: 'foreach' }), ['item', 'index', 'count'])
  assert.deepEqual(outputFieldsOf({ kind: 'stop' }), [])
})

test('the reference list holds the run data and the other nodes, never the node itself', () => {
  const nodes = [
    { id: 'n1', data: { node: { kind: 'data', op: 'fixed' }, meta: {} } },
    { id: 'n2', data: { node: { step: 'Read page' }, meta: { action: 'read_value' } } },
    { id: 'n3', data: { node: { kind: 'data', op: 'math' }, meta: {} } },
  ]
  const options = refOptions(nodes, 'n3', ['name'])

  assert.deepEqual(options.map((o) => `${o.node}.${o.field}`), ['run.name', 'n1.value', 'n2.value', 'n2.effect'])
  assert.ok(options.every((o) => o.label.length > 0))
})
