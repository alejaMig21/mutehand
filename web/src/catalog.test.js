import assert from 'node:assert/strict'
import test from 'node:test'
import { appLabel, CHIP_COLOURS, chipFor, onAppNames, searchCatalog, setAppNames, taughtApp, SYSTEM_NODES } from './catalog.js'

const steps = [
  { app: 'telegram.exe', name: 'Send', origin: 'local' },
  { app: 'telegram.exe', name: 'Write message', origin: 'local' },
  { app: 'vivaldi.exe', name: 'Read page', origin: 'factory' },
]

test('an empty search shows everything, steps ordered by app then name', () => {
  const found = searchCatalog('', steps)

  assert.equal(found.system.length, SYSTEM_NODES.length)
  assert.deepEqual(found.apps.map((s) => s.name), ['Send', 'Write message', 'Read page'])
})

test('a search finds system nodes by name and steps by name and by app', () => {
  assert.deepEqual(searchCatalog('wait', steps).system.map((n) => n.title), ['Wait a while', 'Join']) // by name, then by hint
  assert.deepEqual(searchCatalog('telegram', steps).apps.map((s) => s.name), ['Send', 'Write message'])
  assert.deepEqual(searchCatalog('READ', steps).apps.map((s) => s.name), ['Read page'])
  assert.equal(searchCatalog('READ', steps).system.some((n) => n.title === 'Read a field'), true)
  assert.deepEqual(searchCatalog('zzz', steps), { system: [], apps: [], recipes: [] })
})

test('a search takes plain words, in any order, whatever separates them in the name', () => {
  const found = (query) => searchCatalog(query, [{ app: 'paint.exe', name: 'save_the-picture', origin: 'local' }]).apps.length

  assert.equal(found('picture save'), 1)
  assert.equal(found('save-the picture'), 1)
  assert.equal(found('save report'), 0)
})

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
    const found = searchCatalog('', [{ app: 'zzqx.exe', name: 'a', origin: 'local' }, { app: 'vvrt.exe', name: 'b', origin: 'local' }])
    assert.deepEqual(found.apps.map((s) => s.name), ['b', 'a']) // Atlas before Quill Ledger
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
