import { useEffect, useRef, useState } from 'react'
import { appLabel } from './catalog.js'
import ChatMessage from './ChatMessage.jsx'
import { Icon } from './icons.jsx'
import { chooseTechnology, panelSections } from './search.js'

export const DRAG_TYPE = 'application/x-workflow-entry'
// an entry can be pressed, or dragged to the place on the canvas where it should go
const draggable = (entry) => ({ draggable: true, onDragStart: (e) => e.dataTransfer.setData(DRAG_TYPE, JSON.stringify(entry)) })

function Entry({ title, hint, children, ...props }) {
  return (
    <li>
      <button type="button" className="entry" {...props}>
        <span className="entry-text"><b>{title}</b>{hint && <small>{hint}</small>}</span>
        {children}
        <Icon name="plus" />
      </button>
    </li>
  )
}

// Asks which program a step node is for. The first choice has the focus; Escape leaves without adding anything.
function Chooser({ name, apps, onChoose, onCancel }) {
  const first = useRef(null)
  useEffect(() => first.current?.focus(), [])
  return (
    <li>
      <div role="group" aria-label={`Which program for ${name}?`} className="chooser" data-testid="technology-chooser"
        onKeyDown={(e) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onCancel() } }}>
        <p>Which program for “{name}”?</p>
        {apps.map((app, i) => (
          <button key={app} type="button" ref={i === 0 ? first : undefined} data-testid={`technology-${app}`} onClick={() => onChoose(app)}>
            {appLabel(app)}
          </button>
        ))}
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </li>
  )
}

// The column on the right of the canvas: one search field, then sections by node type. It only adds what exists. Nothing in
// it starts a lesson: lessons happen in an agent chat.
export default function SearchPanel({ steps, recipes, onAddSystem, onAddStep, onAddRecipe }) {
  const [query, setQuery] = useState('')
  const [toggled, setToggled] = useState({}) // sections the person opened or closed since the query last changed
  const [choosing, setChoosing] = useState(null) // the step that waits for a program: {name, apps}
  const [teaching, setTeaching] = useState(false)
  const field = useRef(null)
  // only what the person typed: nothing read from a program's screen
  const message = `I want to teach you a flow: ${query.trim() || '[what you want done, and in which program]'}`
  const { sections, recipes: found } = panelSections(query, steps, recipes)

  const type = (text) => { setQuery(text); setToggled({}); setChoosing(null) }
  const add = (name, app) => { setChoosing(null); onAddStep({ name, app }) }
  const press = ({ name, technologies, visible }) => {
    const pick = chooseTechnology(query, technologies, visible)
    if ('ask' in pick) setChoosing({ name, apps: pick.ask })
    else add(name, pick.app)
  }
  const cancel = () => { setChoosing(null); field.current?.focus() }
  const system = (n) => (
    <Entry key={n.key} title={n.title} hint={n.hint} data-testid={`system-${n.key}`} onClick={() => onAddSystem(n)}
      {...draggable({ system: n.key })} />
  )

  const items = (section) => {
    if (section.key === 'components') return !query.trim() && <p className="empty">No components yet.</p>
    if (section.key !== 'steps') return <ul>{section.items.map(system)}</ul>
    if (!section.items.length) return <p className="empty">Nothing learned yet.</p>
    return (
      <ul>
        {section.items.map((item) => {
          const row = item.step
          const pick = chooseTechnology(query, item.technologies, item.visible)
          return [
            <Entry key={item.name} title={item.name} hint={item.technologies.map(appLabel).join(', ')} data-testid={`palette-${item.name}`}
              onClick={() => press(item)} {...('app' in pick ? draggable({ app: pick.app, step: item.name }) : {})}>
              {row.state === 'rejected' && <span className="tag tone-bad"><Icon name="xcircle" size={13} /> Rejected</span>}
              {row.sensitive && (row.consent === 'given'
                ? <span className="tag tone-muted"><Icon name="lock" size={13} /> Consent given</span>
                : <span className="tag tone-warn"><Icon name="lock" size={13} /> Needs consent</span>)}
            </Entry>,
            choosing?.name === item.name && (
              <Chooser key={`${item.name}-choose`} name={item.name} apps={choosing.apps} onChoose={(app) => add(item.name, app)} onCancel={cancel} />
            ),
          ]
        })}
      </ul>
    )
  }

  return (
    <aside className="search-panel" aria-label="Add a node" data-testid="search-panel">
      <h2>Add a node</h2>
      <label htmlFor="find-step" className="muted">Find a node</label>
      <input id="find-step" ref={field} type="search" data-testid="search" placeholder="for example: save, or excel" value={query}
        onChange={(e) => type(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Escape' && query) { e.preventDefault(); type('') } }} />

      {sections.map((section) => (
        <details key={section.key} className="section" data-testid={`section-${section.key}`} open={toggled[section.key] ?? section.open}
          onToggle={(e) => { const now = e.currentTarget.open; if (now !== (toggled[section.key] ?? section.open)) setToggled({ ...toggled, [section.key]: now }) }}>
          {/* Space is the canvas's pan key and would be swallowed there; here it opens the section */}
          <summary onKeyDown={(e) => { if (e.key === ' ') e.stopPropagation() }}>{section.title}</summary>
          {items(section)}
        </details>
      ))}
      {query.trim() && !sections.length && !found.length && <p className="empty" role="status">Nothing matches “{query}”.</p>}
      {found.length > 0 && (
        <section aria-labelledby="recipes-heading">
          <h3 id="recipes-heading">Recipes</h3>
          <ul>
            {found.map((recipe) => (
              <Entry key={recipe.name} title={recipe.name} data-testid={`recipe-${recipe.name}`} onClick={() => onAddRecipe(recipe)}
                hint={`${recipe.holes.length} steps · ${Object.keys(recipe.apps).map(appLabel).join(', ') || 'not applied yet'}`} />
            ))}
          </ul>
        </section>
      )}
      <button type="button" className="teach" aria-expanded={teaching} onClick={() => setTeaching(!teaching)}>
        <Icon name="chat" /> It is not here: teach it
      </button>
      {teaching && <ChatMessage message={message} />}
    </aside>
  )
}
