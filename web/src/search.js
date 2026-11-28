// The panel's one search and its sections by node type. Pure, so node can test it.
import { appKey, appLabel, SYSTEM_NODES } from './catalog.js'

const words = (text) => String(text).normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []

// The one search rule, the same as `search_matches` in steps.py (tests/search_vectors.json is asserted by both): every
// word of the query starts a word of the name or of one of the tags. Capitals and accents do not matter.
export function searchMatches(query, name, tags) {
  const present = [name, ...tags].flatMap(words)
  return words(query).every((part) => present.some((word) => word.startsWith(part)))
}

// The programs a step name has rows for, in the order of their names on screen; a row with no program is a universal step.
const programs = (rows) => [...new Map(rows.filter((r) => r.app).map((r) => [appKey(r.app), r.app])).values()]
  .sort((a, b) => appLabel(a).localeCompare(appLabel(b)))

// A program is searchable only when the server lists it for the step (a private one is left out of `technologies`).
const listed = (row) => (row.technologies ?? []).some((t) => appKey(t) === appKey(row.app) || t === appLabel(row.app))

const searchable = (rows) => rows.filter(listed).map((r) => r.app)

const SECTIONS = [['steps', 'Steps'], ['components', 'Components'], ['triggers', 'Triggers'], ['order', 'Order'], ['logic', 'Logic'],
  ['data', 'Data']]

// What the panel shows for a query: the sections, each {key, title, open, items}. With no query only Steps and Components
// are open (and all are listed); typing lists only the sections with a match, all open.
// A step is found by its name, its tags and the programs it was learned for; a universal step (none) only by name or tag,
// so with no query it is not listed. A system node is found by its title and its group.
export function panelSections(query, rows, recipes = []) {
  const typing = words(query).length > 0
  const names = [...new Set(rows.map((row) => row.name))].sort((a, b) => a.localeCompare(b))
  const steps = names.flatMap((name) => {
    const own = rows.filter((row) => row.name === name)
    const technologies = programs(own)
    const tags = [...own.flatMap((r) => [...(r.tags ?? []), ...(r.technologies ?? [])].map((t) => appLabel(t))), ...searchable(own).map(appLabel)]
    const shown = !technologies.length ? typing && searchMatches(query, name, tags) : searchMatches(query, name, tags)
    return shown ? [{ name, technologies, visible: searchable(own), step: own.find((r) => r.app && appKey(r.app) === appKey(technologies[0])) ?? own[0] }] : []
  })
  const system = (group) => SYSTEM_NODES.filter((n) => n.group === group && searchMatches(query, n.title, [n.group]))
  const sections = SECTIONS.map(([key, title]) => ({
    key, title, open: typing || key === 'steps' || key === 'components',
    items: key === 'steps' ? steps : key === 'components' ? [] : system(title),
  })).filter((s) => !typing || s.items.length)
  const found = recipes.filter((r) => searchMatches(query, r.name, [...r.holes.map((h) => h.hole), ...Object.keys(r.apps).map(appLabel)]))
  return { sections, recipes: found }
}

// The program a step node takes when pressed from a search: the one the typed words name, else the only one (none for a universal step),
// else the person is asked: {app} or {ask: [apps to choose from]}.
export function chooseTechnology(query, technologies, visible) {
  const typed = words(query)
  const named = technologies.filter((app) => visible.includes(app)).filter((app) => words(appLabel(app)).some((word) => typed.some((part) => word.startsWith(part))))
  const candidates = named.length ? named : technologies
  return candidates.length <= 1 ? { app: candidates[0] } : { ask: candidates }
}
