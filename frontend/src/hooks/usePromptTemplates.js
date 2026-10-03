import { useEffect, useMemo } from 'react';

import { useTemplatesQuery } from '../queries/templates';

/** Shared templates query + auto-selection of the active default template. */
export function usePromptTemplates(selectedId, onSelectedChange) {
  const query = useTemplatesQuery();
  const templates = useMemo(() => query.data?.items ?? [], [query.data]);

  useEffect(() => {
    if (!templates.length) return;
    const stillValid = templates.some((template) => template.id === selectedId);
    if (stillValid) return;
    const fallback = templates.find((template) => template.is_default) || templates[0];
    onSelectedChange?.(fallback.id);
  }, [templates, selectedId, onSelectedChange]);

  return { ...query, templates };
}
