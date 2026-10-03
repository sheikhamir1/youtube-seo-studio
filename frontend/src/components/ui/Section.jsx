import { cn } from '../../utils/cn';

export function Section({ title, description, actions, children, className }) {
  return (
    <section className={cn('space-y-3', className)}>
      {(title || actions) && (
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            {title && <h2 className="text-sm font-semibold text-content">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export default Section;
