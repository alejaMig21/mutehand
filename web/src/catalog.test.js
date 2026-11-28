import assert from 'node:assert/strict'
import test from 'node:test'
import { appLabel, CHIP_COLOURS, chipFor, onAppNames, setAppNames, taughtApp, technologiesOf, SYSTEM_NODES } from './catalog.js'

test('every system node can be stored as it is: a kind, and its operation when it is a data node', () => {
  const keys = new Set()
  for (const n of SYSTEM_NODES) {
    assert.equal(keys.has(n.key), false, `duplicate key ${n.key}`)
    keys.add(n.key)
    assert.ok(n.node.kind, n.key)
    if (n.node.kind === 'data') assert.ok(n.node.op, n.key)
    for (const binding of Object.values(n.node.fields ?? {})) assert.deepEqual(Object.keys(binding), ['value'])
  }
})

test('no system node starts a lesson or teaches anything', () => {
  for (const n of SYSTEM_NODES) assert.doesNotMatch(`${n.title} ${n.hint}`, /lesson|teach/i)
})

test('app names read like names and every chip has readable text', () => {
  assert.equal(appLabel('telegram.exe'), 'Telegram')
  assert.equal(appLabel('Word'), 'Word')
  assert.deepEqual(chipFor('telegram.exe'), chipFor('TELEGRAM.EXE'))

  const luminance = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  for (const colour of CHIP_COLOURS) assert.ok(1.05 / (luminance(colour) + 0.05) >= 4.5, colour)
})

test('an app is called by its product name once it is known, and keeps its chip colour', () => {
  const before = chipFor('zzqx.exe')
  let heard = 0
  const stop = onAppNames(() => { heard += 1 })
  try {
    setAppNames({ zzqx: 'Quill Ledger', vvrt: 'Atlas' })
    setAppNames({ zzqx: 'Quill Ledger', vvrt: 'Atlas' }) // the same names again: nothing to redraw

    assert.equal(heard, 1)
    assert.equal(appLabel('ZZQX.EXE'), 'Quill Ledger')
    assert.equal(appLabel('other.exe'), 'Other')
    assert.deepEqual(chipFor('zzqx.exe'), { letter: 'Q', colour: before.colour })
  } finally {
    stop()
    setAppNames({})
  }
})

test('an app typed in any spelling is the one the steps were taught on', () => {
  const apps = ['Telegram.exe', 'paint']

  assert.equal(taughtApp(' telegram ', apps), 'Telegram.exe')
  assert.equal(taughtApp('PAINT.EXE', apps), 'paint')
  assert.equal(taughtApp(' unknown.exe ', apps), 'unknown.exe')
  assert.equal(taughtApp('', apps), '')
})

test('the programs a step is learned for are ordered by their names on screen, and Paint.exe and paint.exe are one', () => {
  setAppNames({})
  const rows = [
    { app: 'paint.exe', name: 'save' }, { app: 'excel.exe', name: 'save' }, { app: 'Paint.exe', name: 'save' },
    { app: 'word.exe', name: 'open' },
  ]
  assert.deepEqual(technologiesOf(rows, 'save'), ['excel.exe', 'paint.exe'])
  assert.deepEqual(technologiesOf(rows, 'nope'), [])
})
