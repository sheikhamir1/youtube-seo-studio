import { cn } from '../../utils/cn';

export function Card({ className, children, as: Tag = 'section', ...rest }) {
  return (
    <Tag className={cn('card', className)} {...rest}>
      {children}
    </Tag>
  );
}

export function CardHeader({ title, description, actions, icon: Icon, className }) {
  return (
    <header
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5',
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-2.5">
        {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />}
        <div className="min-w-0">
          <h2 className="truncate text-[15px] font-semibold text-content">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

export function CardBody({ className, children }) {
  return <div className={cn('card-pad', className)}>{children}</div>;
}

export function CardFooter({ className, children }) {
  return (
    <footer
      className={cn(
        'flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 sm:px-5',
        className,
      )}
    >
      {children}
    </footer>
  );
}

export default Card;
