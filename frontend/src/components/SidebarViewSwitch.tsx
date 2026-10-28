export type SidebarView = 'markets' | 'deployers'

const VIEWS: { value: SidebarView; label: string }[] = [
  { value: 'markets', label: 'Markets' },
  { value: 'deployers', label: 'Deployers' },
]

interface SidebarViewSwitchProps {
  value: SidebarView
  onChange: (view: SidebarView) => void
}

// Markets | Deployers switch at the top of the sidebar (Milestone 20.1b).
function SidebarViewSwitch({ value, onChange }: SidebarViewSwitchProps) {
  return (
    <div className="sidebar-view-switch side-toggle" role="group" aria-label="Sidebar view">
      {VIEWS.map((view) => (
        <button
          key={view.value}
          type="button"
          className={
            view.value === value
              ? 'side-toggle-button side-toggle-button--active'
              : 'side-toggle-button'
          }
          aria-pressed={view.value === value}
          onClick={() => onChange(view.value)}
        >
          {view.label}
        </button>
      ))}
    </div>
  )
}

export default SidebarViewSwitch