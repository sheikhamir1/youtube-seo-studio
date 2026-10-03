import { MoreHorizontal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { cn } from '../../utils/cn';
import { Button } from './Button';

/** Minimal dropdown menu (keyboard + click-outside aware, no dependencies). */
export function Dropdown({ items = [], label = 'More actions', trigger, align = 'right', className }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onClick = (event) => {
      if (!containerRef.current?.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const visibleItems = items.filter(Boolean);

  return (
    <div ref={containerRef} className={cn('relative inline-flex', className)}>
      {trigger ? (
        trigger({ open, toggle: () => setOpen((value) => !value) })
      ) : (
        <Button
          variant="ghost"
          size="sm"
          icon={MoreHorizontal}
          aria-label={label}
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        />
      )}
      {open && (
        <div
          role="menu"
          className={cn(
            'absolute top-full z-40 mt-1 min-w-[190px] overflow-hidden rounded-md border border-border bg-surface py-1 shadow-lg animate-fade-in',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {visibleItems.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onSelect?.();
              }}
              className={cn(
                'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors',
                'disabled:cursor-not-allowed disabled:opacity-40',
                item.variant === 'danger'
                  ? 'text-danger hover:bg-danger/10'
                  : 'text-content hover:bg-surface-2',
              )}
            >
              {item.icon && <item.icon className="h-3.5 w-3.5" aria-hidden="true" />}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default Dropdown;
