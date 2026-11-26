// The right-hand panel's catalogue: system nodes and the steps the apprentice has been taught. Pure, so node can test it.

const fixed = (value) => ({ value })

const system = (key, title, hint, group, icon, node) => ({ key, title, hint, group, icon, node })
const data = (op, fields) => ({ kind: 'data', op, fields: Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, fixed(v)])) })

export const SYSTEM_NODES = [
  system('manual-trigger', 'Manual trigger', 'Starts a flow by hand', 'Triggers', 'play',
    { kind: 'trigger', fields: { mode: fixed('manual') } }),
  system('daily-trigger', 'Daily trigger', 'Starts a flow every day at a time', 'Triggers', 'clock',
    { kind: 'trigger', fields: { mode: fixed('daily'), at: fixed('09:00') } }),
  system('foreach', 'For each', 'Repeats the first node it connects to, once per item', 'Flow', 'repeat',
    { kind: 'foreach', fields: { items: fixed([]) } }),
  system('if', 'If', 'Chooses a path: first wire when true, second when false', 'Flow', 'branch',
    { kind: 'if', fields: { condition: fixed(true) } }),
  system('wait', 'Wait', 'Pauses the flow', 'Flow', 'clock', { kind: 'wait', fields: { seconds: fixed(5) } }),
  system('join', 'Join', 'Waits for every path that leads to it', 'Flow', 'merge', { kind: 'join' }),
  system('stop', 'Stop', 'Ends the flow on purpose', 'Flow', 'stop', { kind: 'stop' }),
  system('compare', 'Compare', 'Two values: equal, greater, contains...', 'Logic', 'scale',
    data('compare', { a: 0, b: 0, operator: 'equals' })),
  system('and', 'And', 'True when both are true', 'Logic', 'scale', data('and', { a: true, b: true })),
  system('or', 'Or', 'True when either is true', 'Logic', 'scale', data('or', { a: true, b: false })),
  system('not', 'Not', 'Turns true into false', 'Logic', 'scale', data('not', { a: true })),
  system('fixed', 'Fixed value', 'A value you type once', 'Data', 'braces', data('fixed', { value: '' })),
  system('convert', 'Convert', 'Text, number, whole number or true/false', 'Data', 'braces',
    data('convert', { value: '', to: 'text' })),
  system('split', 'Split text', 'Cuts a text into a list', 'Data', 'braces', data('split', { text: '', separator: ',' })),
  system('join-text', 'Join text', 'Puts a list into one text', 'Data', 'braces', data('join', { items: [], separator: ',' })),
  system('format', 'Format text', 'Fills named places in a template', 'Data', 'braces', data('format', { template: '', values: {} })),
  system('regex', 'Regular expression', 'Finds a pattern in a text', 'Data', 'braces', data('regex', { text: '', pattern: '.' })),
  system('get', 'Read a field', 'Takes one field out of an object', 'Data', 'braces', data('get', { object: {}, path: 'a' })),
  system('set', 'Write a field', 'Gives back an object with one field set', 'Data', 'braces', data('set', { object: {}, path: 'a', value: '' })),
  system('math', 'Math', 'Add, subtract, multiply, divide...', 'Data', 'braces',
    data('math', { a: 0, b: 0, operation: 'add' })),
]

// 'telegram.exe' -> 'Telegram'
export const appLabel = (app) => {
  const base = String(app).replace(/\.exe$/i, '')
  return base.charAt(0).toUpperCase() + base.slice(1)
}

// 'Telegram', 'TELEGRAM.EXE' and 'telegram.exe' are one app
export const appKey = (app) => String(app).toLowerCase().replace(/\.exe$/, '')

const has = (text, query) => String(text).toLowerCase().includes(query)

// What the panel shows for a search: system nodes by name, hint or group; steps by name, app or origin.
export function searchCatalog(query, steps, systemNodes = SYSTEM_NODES, recipes = []) {
  const q = query.trim().toLowerCase()
  const system = systemNodes.filter((n) => !q || [n.title, n.hint, n.group].some((t) => has(t, q)))
  const apps = steps
    .filter((s) => !q || [s.name, s.app, appLabel(s.app), s.origin].some((t) => has(t, q)))
    .sort((a, b) => a.app.localeCompare(b.app) || a.name.localeCompare(b.name))
  const found = recipes.filter((r) => !q || [r.name, ...r.holes.map((h) => h.hole), ...Object.keys(r.apps).map(appLabel)].some((t) => has(t, q)))
  return { system, apps, recipes: found }
}

// Letter chip colours: white text on each is at least 4.5:1 (checked by the tests).
export const CHIP_COLOURS = ['#1F6FA8', '#7B4FC4', '#1B7A4E', '#B0405F', '#3F5FB8', '#8A5A12']

// The same app always gets the same chip, whatever the case of its name.
export function chipFor(app) {
  const label = appLabel(app)
  let hash = 0
  for (const ch of label.toLowerCase()) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return { letter: label.charAt(0), colour: CHIP_COLOURS[hash % CHIP_COLOURS.length] }
}

// The catalogue entry a stored system node came from (by kind, operation and, for a trigger, its mode).
export const systemEntryFor = (node) => SYSTEM_NODES.find((s) => s.node.kind === node.kind && (s.node.op ?? null) === (node.op ?? null)
  && (node.kind !== 'trigger' || s.node.fields.mode.value === node.fields?.mode?.value))

// What a node is called on screen.
export const titleOf = (node) => (node.kind && node.kind !== 'step' ? systemEntryFor(node)?.title ?? node.kind : node.step)

// The app as the taught steps spell it, so a run finds them: 'Telegram' is telegram.exe.
export function taughtApp(typed, apps) {
  const app = typed.trim()
  return apps.includes(app) ? app : apps.find((known) => appKey(known) === appKey(app)) ?? app
}
