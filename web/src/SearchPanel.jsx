import { useMemo, useState } from 'react'
import { appLabel, chipFor, searchCatalog, SYSTEM_NODES } from './catalog.js'
import { Icon } from './icons.jsx'

const SYSTEM_PREVIEW = 4 // like n8n: a few first, the rest on request or by searching

// The floating card on the right of the canvas: search, then system nodes and the steps already taught.
// It only adds what exists. Nothing in it starts a lesson: lessons happen in an agent chat.
export default function SearchPanel({ steps, recipes, onAddSystem, onAddStep, onAddRecipe, onClose }) {
  const [query, setQuery] = useState('')
  const [all, setAll] = useState(false)
  const { system, apps, recipes: foundRecipes } = useMemo(() => searchCatalog(query, steps, undefined, recipes), [query, steps, recipes])
  const shown = query || all ? system : system.slice(0, SYSTEM_PREVIEW)
  const rest = system.length - shown.length

  return (
    <aside className="search-panel" aria-label="Add a node" data-testid="search-panel">
      <div className="search-box">
        <Icon name="search" />
        <input type="search" aria-label="Search nodes and steps" data-testid="search" placeholder="Search nodes, apps, steps"
          value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="icon-button" aria-label="Close the panel" onClick={onClose}><Icon name="close" /></button>
      </div>

      <div className="panel-scroll">
        {shown.length > 0 && (
          <section aria-label="System nodes">
            <h2>System nodes <span>{SYSTEM_NODES.length}</span></h2>
            {shown.map((n) => (
              <button key={n.key} className="entry" data-testid={`system-${n.key}`} onClick={() => onAddSystem(n)}>
                <span className="chip system" aria-hidden="true"><Icon name={n.icon} /></span>
                <span className="entry-text"><b>{n.title}</b><small>{n.hint}</small></span>
              </button>
            ))}
            {rest > 0 && <button className="more" onClick={() => setAll(true)}>{rest} more</button>}
          </section>
        )}

        <section aria-label="Steps taught by apps">
          <h2>Apps <span>{apps.length}</span></h2>
          {apps.length === 0 && !query && <p className="empty">No steps yet. An agent teaches them in a chat; they show up here.</p>}
          {apps.map((step) => {
            const chip = chipFor(step.app)
            return (
              <button key={`${step.app}/${step.name}`} className={`entry${step.sensitive ? ' sensitive' : ''}`}
                data-testid={`palette-${step.name}`} onClick={() => onAddStep(step)}>
                <span className="chip" style={{ background: chip.colour }} aria-hidden="true">{chip.letter}</span>
                <span className="entry-text">
                  <b>{step.name}</b>
                  <small>{appLabel(step.app)} · {step.origin}</small>
                </span>
                {step.sensitive && <span className="tag"><Icon name="lock" size={13} /> Needs consent</span>}
              </button>
            )
          })}
        </section>
        {foundRecipes.length > 0 && (
          <section aria-label="Recipes">
            <h2>Recipes <span>{foundRecipes.length}</span></h2>
            {foundRecipes.map((recipe) => (
              <button key={recipe.name} className="entry" data-testid={`recipe-${recipe.name}`} onClick={() => onAddRecipe(recipe)}>
                <span className="chip system" aria-hidden="true"><Icon name="layers" /></span>
                <span className="entry-text">
                  <b>{recipe.name}</b>
                  <small>{recipe.holes.length} steps · {Object.keys(recipe.apps).map(appLabel).join(', ') || 'not applied yet'}</small>
                </span>
              </button>
            ))}
          </section>
        )}
        {query && system.length === 0 && apps.length === 0 && foundRecipes.length === 0 && <p className="empty" role="status">Nothing matches “{query}”.</p>}
      </div>
    </aside>
  )
}
