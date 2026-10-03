import { cn } from '../../utils/cn';

/** Definition-list style key/value grid used across detail views. */
export function KeyValue({ items, columns = 2, className }) {
  const visible = items.filter(Boolean);
  if (!visible.length) return null;
  return (
    <dl
      className={cn(
        'grid gap-x-6 gap-y-3',
        columns === 1 ? 'grid-cols-1' : columns === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2',
        className,
      )}
    >
      {visible.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">{item.label}</dt>
          <dd className={cn('mt-0.5 text-sm text-content', item.mono && 'mono')}>
            {item.value ?? '—'}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default KeyValue;
