import { Plus, X } from 'lucide-react';
import { useState } from 'react';

import { cn } from '../../utils/cn';
import Button from '../ui/Button';
import Input from '../ui/Input';

const MAX_TAGS = 60;
const MAX_TAG_LENGTH = 60;

/**
 * Tag editor: chips with add/remove, deduplicated case-insensitively.
 * Also offers a comma-separated bulk import because that is how the model
 * output is commonly pasted.
 */
export function TagsEditor({ tags = [], onChange, disabled = false, maxTags = MAX_TAGS }) {
  const [draft, setDraft] = useState('');
  const [bulk, setBulk] = useState('');
  const [showBulk, setShowBulk] = useState(false);

  const addTag = (value) => {
    const cleaned = String(value || '').trim().replace(/^#/, '').trim();
    if (!cleaned) return false;
    if (cleaned.length > MAX_TAG_LENGTH) return false;
    if (tags.length >= maxTags) return false;
    if (tags.some((tag) => tag.toLowerCase() === cleaned.toLowerCase())) return false;
    onChange([...tags, cleaned]);
    return true;
  };

  const removeTag = (tag) => onChange(tags.filter((value) => value !== tag));

  const applyBulk = () => {
    const candidates = bulk
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    const next = [...tags];
    candidates.forEach((candidate) => {
      const cleaned = candidate.replace(/^#/, '').trim();
      if (!cleaned || cleaned.length > MAX_TAG_LENGTH) return;
      if (next.length >= maxTags) return;
      if (next.some((tag) => tag.toLowerCase() === cleaned.toLowerCase())) return;
      next.push(cleaned);
    });
    onChange(next);
    setBulk('');
    setShowBulk(false);
  };

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <label htmlFor="tag-input" className="text-sm font-medium">
          Tags
        </label>
        <span className={cn('mono text-muted', tags.length >= maxTags && 'text-warning')}>
          {tags.length} / {maxTags}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5 rounded-md border border-border bg-surface-2 p-2">
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-0.5 text-xs"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              disabled={disabled}
              aria-label={`Remove tag ${tag}`}
              className="rounded text-muted transition-colors hover:text-danger disabled:opacity-40"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {!tags.length && <span className="px-1 py-0.5 text-xs text-muted">No tags yet.</span>}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <div className="flex min-w-[220px] flex-1 items-center gap-2">
          <Input
            id="tag-input"
            placeholder="Add a tag and press Enter"
            value={draft}
            disabled={disabled || tags.length >= maxTags}
            maxLength={MAX_TAG_LENGTH}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ',') {
                event.preventDefault();
                if (addTag(draft)) setDraft('');
              }
              if (event.key === 'Backspace' && !draft && tags.length) {
                removeTag(tags[tags.length - 1]);
              }
            }}
          />
          <Button
            variant="outline"
            size="sm"
            icon={Plus}
            disabled={disabled || !draft.trim()}
            onClick={() => {
              if (addTag(draft)) setDraft('');
            }}
          >
            Add
          </Button>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setShowBulk((value) => !value)}>
          {showBulk ? 'Hide bulk import' : 'Paste comma-separated'}
        </Button>
      </div>

      {showBulk && (
        <div className="mt-2 space-y-2">
          <textarea
            value={bulk}
            disabled={disabled}
            onChange={(event) => setBulk(event.target.value)}
            placeholder="keyword one, keyword two, keyword three"
            className="input-base min-h-[70px]"
          />
          <Button variant="secondary" size="sm" onClick={applyBulk} disabled={!bulk.trim()}>
            Import tags
          </Button>
        </div>
      )}

      {tags.length >= maxTags && (
        <p className="mt-1.5 text-xs text-warning">
          Tag limit reached ({maxTags}). Remove a tag before adding another.
        </p>
      )}
    </div>
  );
}

export default TagsEditor;
