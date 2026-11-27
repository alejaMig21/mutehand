// The right-hand panel's catalogue: system nodes and the steps the apprentice has been taught. Pure, so node can test it.

const fixed = (value) => ({ value })

const system = (key, title, hint, group, icon, node) => ({ key, title, hint, group, icon, node })
const data = (op, fields) => ({ kind: 'data', op, fields: Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, fixed(v)])) })

export const SYSTEM_NODES = [
  system('manual-trigger', 'Manual trigger', 'Starts a chore by hand', 'Triggers', 'play',
    { kind: 'trigger', fields: { mode: fixed('manual') } }),
  system('daily-trigger', 'Daily trigger', 'Starts a chore every day at a time', 'Triggers', 'clock',
    { kind: 'trigger', fields: { mode: fixed('daily'), at: fixed('09:00') } }),
  system('foreach', 'Repeat for each', 'Repeats the first action it connects to, once per item', 'Order', 'repeat',
    { kind: 'foreach', fields: { items: fixed([]) } }),
  system('if', 'Two paths: yes or no', 'Chooses a path: the first line is yes, the second is no', 'Order', 'branch',
    { kind: 'if', fields: { condition: fixed(true) } }),
  system('wait', 'Wait a while', 'Pauses the chore', 'Order', 'clock', { kind: 'wait', fields: { seconds: fixed(5) } }),
  system('join', 'Join', 'Waits for every path that leads to it', 'Order', 'merge', { kind: 'join' }),
  system('stop', 'Stop', 'Ends the chore on purpose', 'Order', 'stop', { kind: 'stop' }),
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

// 'Telegram', 'TELEGRAM.EXE' and 'telegram.exe' are one app
export const appKey = (app) => String(app).toLowerCase().replace(/\.exe$/, '')

// The product names the apps' executables declare, by app key, as the server recorded them when it saw each app. The
// screens subscribe, so they are drawn again when the names arrive.
let productNames = {}
const listeners = new Set()
export const getAppNames = () => productNames
export const onAppNames = (listener) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
export function setAppNames(found) {
  if (JSON.stringify(found) === JSON.stringify(productNames)) return
  productNames = found
  listeners.forEach((listener) => listener())
}

// What an app is called on screen: its product name, else its file name without the extension, capitalised.
export const appLabel = (app) => {
  const known = productNames[appKey(app)]
  if (known) return known
  const base = String(app).replace(/\.exe$/i, '')
  return base.charAt(0).toUpperCase() + base.slice(1)
}

// 'open-menu', 'Open_menu' and 'open menu' are the same words
const plain = (text) => String(text).toLowerCase().replace(/[-_]+/g, ' ')

// What the panel shows for a search, which is plain words in any order: system nodes by name, hint or group; steps by
// name, app or origin.
export function searchCatalog(query, steps, systemNodes = SYSTEM_NODES, recipes = []) {
  const words = plain(query).split(/\s+/).filter(Boolean)
  const matches = (texts) => {
    const text = plain(texts.join(' '))
    return words.every((word) => text.includes(word))
  }
  const system = systemNodes.filter((n) => matches([n.title, n.hint, n.group]))
  const apps = steps
    .filter((s) => matches([s.name, s.app, appLabel(s.app), s.origin]))
    .sort((a, b) => appLabel(a.app).localeCompare(appLabel(b.app)) || a.name.localeCompare(b.name))
  const found = recipes.filter((r) => matches([r.name, ...r.holes.map((h) => h.hole), ...Object.keys(r.apps).map(appLabel)]))
  return { system, apps, recipes: found }
}

// The system nodes a person meets first: a choice, a repeat and a pause, in this order.
export const DECISIONS = ['if', 'foreach', 'wait']

// Letter chip colours: white text on each is at least 4.5:1 (checked by the tests).
export const CHIP_COLOURS = ['#1F6FA8', '#7B4FC4', '#1B7A4E', '#B0405F', '#3F5FB8', '#8A5A12']

// The same app always gets the same chip, whatever the case of its name: the letter of the name on screen, and a colour
// that does not change when that name arrives.
export function chipFor(app) {
  let hash = 0
  for (const ch of appKey(app)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return { letter: appLabel(app).charAt(0).toUpperCase(), colour: CHIP_COLOURS[hash % CHIP_COLOURS.length] }
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
