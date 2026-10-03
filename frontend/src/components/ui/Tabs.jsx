import { cn } from '../../utils/cn';

/** Simple accessible tab bar: buttons with aria-selected, no focus traps. */
export function Tabs({ tabs, active, onChange, className }) {
  return (
    <div role="tablist" className={cn('flex flex-wrap gap-1 border-b border-border', className)}>
      {tabs.map((tab) => {
        const isActive = tab.value === active;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.value)}
            className={cn(
              'relative -mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'border-accent text-content'
                : 'border-transparent text-muted hover:text-content',
            )}
          >
            {tab.label}
            {tab.count !== undefined && tab.count !== null && (
              <span className="mono ml-1.5 text-xs text-muted">{tab.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;
