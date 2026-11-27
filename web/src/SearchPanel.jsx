import { useState } from 'react'
import AppSelect from './AppSelect.jsx'
import { appKey, appLabel, chipFor, DECISIONS, searchCatalog } from './catalog.js'
import ChatMessage from './ChatMessage.jsx'
import { Icon } from './icons.jsx'

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

// The column on the right of the canvas: the app, its steps, then decisions, recipes and the other nodes.
// It only adds what exists. Nothing in it starts a lesson: lessons happen in an agent chat.
export default function SearchPanel({ steps, recipes, apps, app, onApp, onAddSystem, onAddStep, onAddRecipe }) {
  const [query, setQuery] = useState('')
  const [teaching, setTeaching] = useState(false)
  // only what the person typed and the app's name: nothing read from the app's screen
  const message = app ? `I want to teach you a new step in ${appLabel(app)}: ${query.trim() || '[what you want done]'}`
    : `I want to teach you a flow: ${query.trim() || '[what you want done, and in which program]'}`
  const own = steps.filter((step) => appKey(step.app) === appKey(app))
  const found = searchCatalog(query, own, undefined, recipes)
  const decisions = DECISIONS.map((key) => found.system.find((n) => n.key === key)).filter(Boolean)
  const others = found.system.filter((n) => !DECISIONS.includes(n.key))
  const chip = app && chipFor(app)
  const system = (n, hint) => (
    <Entry key={n.key} title={n.title} hint={hint} data-testid={`system-${n.key}`} onClick={() => onAddSystem(n)}
      {...draggable({ system: n.key })} />
  )

  return (
    <aside className="search-panel" aria-label="Add a node" data-testid="search-panel">
      <h2>Add a node</h2>
      <div className="panel-app">
        {chip && <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>}
        <AppSelect aria-label="App to run on" data-testid="app-name" apps={apps} value={app} onChange={onApp} />
      </div>
      <label htmlFor="find-step" className="muted">Find a step</label>
      <input id="find-step" type="search" data-testid="search" placeholder="for example: save" value={query}
        onChange={(e) => setQuery(e.target.value)} />

      <ul aria-label="Steps">
        {found.apps.map((step) => (
          <Entry key={`${step.app}/${step.name}`} title={step.name} data-testid={`palette-${step.name}`}
            onClick={() => onAddStep(step)} {...draggable({ app: step.app, step: step.name })}>
            {step.state === 'rejected' && <span className="tag tone-bad"><Icon name="xcircle" size={13} /> Rejected</span>}
            {step.sensitive && (step.consent === 'given'
              ? <span className="tag tone-muted"><Icon name="lock" size={13} /> Consent given</span>
              : <span className="tag tone-warn"><Icon name="lock" size={13} /> Needs consent</span>)}
          </Entry>
        ))}
      </ul>
      {own.length === 0 && <p className="empty">{app ? `Nothing learned for ${appLabel(app)} yet.` : 'Nothing learned yet.'}</p>}
      {query && !found.apps.length && !found.system.length && !found.recipes.length
        && <p className="empty" role="status">Nothing matches “{query}”.</p>}

      {decisions.length > 0 && (
        <section aria-labelledby="decisions-heading">
          <h3 id="decisions-heading">Decisions and repeats</h3>
          <ul>{decisions.map((n) => system(n))}</ul>
        </section>
      )}
      <button type="button" className="teach" aria-expanded={teaching} onClick={() => setTeaching(!teaching)}>
        <Icon name="chat" /> It is not here: teach it
      </button>
      {teaching && <ChatMessage message={message} />}
      {found.recipes.length > 0 && (
        <section aria-labelledby="recipes-heading">
          <h3 id="recipes-heading">Recipes</h3>
          <ul>
            {found.recipes.map((recipe) => (
              <Entry key={recipe.name} title={recipe.name} data-testid={`recipe-${recipe.name}`} onClick={() => onAddRecipe(recipe)}
                hint={`${recipe.holes.length} steps · ${Object.keys(recipe.apps).map(appLabel).join(', ') || 'not applied yet'}`} />
            ))}
          </ul>
        </section>
      )}
      {others.length > 0 && (
        <details open={query ? true : undefined}>
          <summary><h3>Other nodes</h3></summary>
          <ul>{others.map((n) => system(n, n.hint))}</ul>
        </details>
      )}
    </aside>
  )
}
