import { ChevronLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

/** Consistent page heading with optional back link, actions and meta row. */
export function PageHeader({ title, description, backTo, backLabel, actions, meta, className }) {
  return (
    <header className={className}>
      {backTo && (
        <Link
          to={backTo}
          className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-content"
        >
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
          {backLabel || 'Back'}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {meta && <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">{meta}</div>}
    </header>
  );
}

export default PageHeader;
