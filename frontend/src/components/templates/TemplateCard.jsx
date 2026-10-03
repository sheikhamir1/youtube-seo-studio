import { Copy, Pencil, Star, Trash2 } from 'lucide-react';

import { formatRelative, truncate } from '../../utils/format';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import Dropdown from '../ui/Dropdown';

/** One prompt template row: preview, badges and its available actions. */
export function TemplateCard({ template, onEdit, onDuplicate, onDelete }) {
  const variables = template.variables || [];

  return (
    <div className="card card-pad">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold normal-case tracking-normal text-content">
              {template.name}
            </h3>
            {template.is_default && (
              <Badge variant="accent">
                <Star className="h-3 w-3" aria-hidden="true" />
                default
              </Badge>
            )}
          </div>
          {template.description && (
            <p className="mt-1 text-sm text-muted">{truncate(template.description, 160)}</p>
          )}
          <p className="mono mt-1 text-xs text-muted">
            updated {formatRelative(template.updated_at)} · {variables.length} variable
            {variables.length === 1 ? '' : 's'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" icon={Pencil} onClick={() => onEdit?.(template)}>
            Open
          </Button>
          <Dropdown
            items={[
              { label: 'Edit', icon: Pencil, onSelect: () => onEdit?.(template) },
              { label: 'Duplicate', icon: Copy, onSelect: () => onDuplicate?.(template) },
              {
                label: 'Delete',
                icon: Trash2,
                variant: 'danger',
                disabled: template.is_default,
                onSelect: () => onDelete?.(template),
              },
            ]}
          />
        </div>
      </div>

      {variables.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {variables.map((variable) => (
            <code key={variable} className="mono rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px]">
              {`{{ ${variable} }}`}
            </code>
          ))}
        </div>
      )}
    </div>
  );
}

export default TemplateCard;
