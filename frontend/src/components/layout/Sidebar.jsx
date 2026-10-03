import {
  FileText,
  History,
  LayoutDashboard,
  PlusCircle,
  Settings as SettingsIcon,
  Youtube,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { NAV_ITEMS, PRODUCT_NAME, ROUTES } from '../../constants';
import { useSystemStatusQuery } from '../../queries/system';
import { cn } from '../../utils/cn';

const ICONS = {
  'layout-dashboard': LayoutDashboard,
  'plus-circle': PlusCircle,
  history: History,
  'file-text': FileText,
  settings: SettingsIcon,
};

/** Desktop navigation rail. Hidden below `lg`, replaced by the mobile drawer. */
export function Sidebar() {
  const { data: status } = useSystemStatusQuery();

  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-surface lg:flex">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/15 text-accent">
          <Youtube className="h-4 w-4" aria-hidden="true" />
        </span>
        <span className="truncate text-sm font-semibold">{PRODUCT_NAME}</span>
      </div>
      <nav className="flex-1 space-y-0.5 p-2">
        {NAV_ITEMS.map((item) => {
          const Icon = ICONS[item.icon];
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === ROUTES.dashboard}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-accent/12 font-medium text-content'
                    : 'text-muted hover:bg-surface-2 hover:text-content',
                )
              }
            >
              {Icon && <Icon className="h-4 w-4" aria-hidden="true" />}
              {item.label}
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t border-border p-3 text-xs text-muted">
        <p className="font-medium text-content">Local first</p>
        <p className="mt-0.5">
          {status?.ffmpeg_available === false
            ? 'FFmpeg missing - install it to process video.'
            : 'FFmpeg ready · single-process worker'}
        </p>
      </div>
    </aside>
  );
}

export default Sidebar;
