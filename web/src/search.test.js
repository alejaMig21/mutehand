import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { chooseTechnology, panelSections, searchMatches } from './search.js'

const vectors = JSON.parse(readFileSync(new URL('../../tests/search_vectors.json', import.meta.url), 'utf8'))

for (const v of vectors) {
  test(`the shared search vectors: ${v.why}`, () => assert.equal(searchMatches(v.query, v.name, v.tags), v.match))
}

const row = (name, app, tags = [], technologies = [app]) => ({ name, app, tags, technologies, origin: 'local' })
const rows = [
  row('Save', 'excel.exe', ['file'], ['excel.exe', 'paint.exe']), row('Save', 'paint.exe', ['file'], ['excel.exe', 'paint.exe']),
  row('Open menu', 'paint.exe'), row('Mouse move', '', ['mouse'], []),
]
const names = (section) => section.items.map((item) => item.name ?? item.title)
const section = (found, key) => found.sections.find((s) => s.key === key)

test('with the box empty only Steps and Components are open, and a universal step stays out', () => {
  const found = panelSections('', rows)

  assert.deepEqual(found.sections.map((s) => [s.key, s.open]),
    [['steps', true], ['components', true], ['triggers', false], ['order', false], ['logic', false], ['data', false]])
  assert.deepEqual(names(section(found, 'steps')), ['Open menu', 'Save'])
  assert.deepEqual(section(found, 'components').items, [])
})

test('typing opens every section that has a match and drops the ones without', () => {
  const found = panelSections('wait', rows)

  assert.deepEqual(found.sections.map((s) => [s.key, s.open]), [['order', true]])
  assert.equal(found.sections[0].items[0].title, 'Wait a while')
})

test('a technology typed finds its steps, a name finds every program, and a universal step needs its own name or tag', () => {
  assert.deepEqual(names(section(panelSections('excel', rows), 'steps')), ['Save'])
  assert.deepEqual(names(section(panelSections('sav', rows), 'steps')), ['Save'])
  assert.deepEqual(names(section(panelSections('mou', rows), 'steps')), ['Mouse move'])
  assert.equal(section(panelSections('excel', rows), 'steps').items[0].technologies.length, 2)
})

test('nothing matching leaves no section', () => assert.deepEqual(panelSections('zzz', rows).sections, []))

test('a step gets the technology that was searched, else the only one, else it asks which', () => {
  const [a, b] = ['excel.exe', 'paint.exe']
  assert.deepEqual(chooseTechnology('excel', [a, b]), { app: a })
  assert.deepEqual(chooseTechnology('Save PAINT', [a, b]), { app: b })
  assert.deepEqual(chooseTechnology('save', [a]), { app: a })
  assert.deepEqual(chooseTechnology('save', [a, b]), { ask: [a, b] })
  assert.deepEqual(chooseTechnology('', [a, b]), { ask: [a, b] })
})

test('a technology the server hides is not searched by, but its step is still found by name', () => {
  const hidden = [row('Pay', 'vault.exe', [], [])]

  assert.deepEqual(panelSections('vault', hidden).sections, [])
  assert.deepEqual(names(section(panelSections('pay', hidden), 'steps')), ['Pay'])
})
