import { Monitor, Moon, Sun } from 'lucide-react';

import { useThemeStore } from '../../stores/themeStore';
import { cn } from '../../utils/cn';
import { Card, CardBody, CardHeader } from '../ui/Card';

const OPTIONS = [
  { value: 'dark', label: 'Dark', icon: Moon, description: 'Default - easier on the eyes for long edits.' },
  { value: 'light', label: 'Light', icon: Sun, description: 'Best in bright rooms.' },
  { value: 'system', label: 'System', icon: Monitor, description: 'Follows your OS setting.' },
];

/** Theme preference (persisted in localStorage). */
export function ThemePanel() {
  const theme = useThemeStore((state) => state.theme);
  const setTheme = useThemeStore((state) => state.setTheme);

  return (
    <Card>
      <CardHeader title="Appearance" description="Dark by default; the choice is remembered." />
      <CardBody>
        <div className="grid gap-2 sm:grid-cols-3">
          {OPTIONS.map((option) => {
            const selected = theme === option.value;
            const Icon = option.icon;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setTheme(option.value)}
                aria-pressed={selected}
                className={cn(
                  'rounded-md border p-3 text-left transition-colors',
                  selected ? 'border-accent bg-accent/8' : 'border-border hover:bg-surface-2',
                )}
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {option.label}
                </span>
                <span className="mt-1 block text-xs text-muted">{option.description}</span>
              </button>
            );
          })}
        </div>
      </CardBody>
    </Card>
  );
}

export default ThemePanel;
