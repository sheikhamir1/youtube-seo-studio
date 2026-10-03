import { Menu, Moon, Sun, Youtube } from 'lucide-react';
import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import { NAV_ITEMS, PRODUCT_NAME, ROUTES } from '../../constants';
import { useThemeStore } from '../../stores/themeStore';
import { cn } from '../../utils/cn';
import Button from '../ui/Button';

/** Top bar: mobile navigation trigger, product mark and the theme switch. */
export function TopBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const theme = useThemeStore((state) => state.theme);
  const resolved = useThemeStore((state) => state.resolved);
  const cycleTheme = useThemeStore((state) => state.cycleTheme);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-border bg-surface/95 px-4 backdrop-blur sm:px-6">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="lg:hidden"
            icon={Menu}
            aria-label="Open navigation"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((value) => !value)}
          />
          <Link to={ROUTES.dashboard} className="flex items-center gap-2 lg:hidden">
            <Youtube className="h-4 w-4 text-accent" aria-hidden="true" />
            <span className="text-sm font-semibold">{PRODUCT_NAME}</span>
          </Link>
          <span className="hidden text-xs text-muted lg:block">
            Long-form video → validated YouTube SEO metadata
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden text-xs text-muted sm:block">
            Theme: <span className="font-medium text-content">{theme}</span>
          </span>
          <Button
            variant="ghost"
            size="sm"
            icon={resolved === 'dark' ? Sun : Moon}
            aria-label={`Switch theme (current: ${theme})`}
            title="Cycle theme: dark → light → system"
            onClick={cycleTheme}
          />
        </div>
      </header>

      {menuOpen && (
        <nav className="border-b border-border bg-surface p-2 lg:hidden" aria-label="Mobile navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === ROUTES.dashboard}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                cn(
                  'block rounded-md px-3 py-2 text-sm',
                  isActive ? 'bg-accent/12 font-medium text-content' : 'text-muted hover:bg-surface-2',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      )}
    </>
  );
}

export default TopBar;
