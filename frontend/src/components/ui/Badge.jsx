import { cn } from '../../utils/cn';

const VARIANTS = {
  neutral: 'bg-surface-2 text-muted border-border',
  accent: 'bg-accent/12 text-accent border-accent/30',
  success: 'bg-success/12 text-success border-success/30',
  warning: 'bg-warning/12 text-warning border-warning/30',
  danger: 'bg-danger/12 text-danger border-danger/40',
  info: 'bg-accent/10 text-accent border-accent/25',
};

export function Badge({ variant = 'neutral', className, children, mono = false, title }) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-5',
        mono && 'font-mono tabular-nums',
        VARIANTS[variant] || VARIANTS.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}

export default Badge;
