import { useEffect } from 'react';

/** Warns before leaving a page with unsaved edits. */
export function useUnsavedChanges(isDirty, message = 'You have unsaved changes. Leave this page?') {
  useEffect(() => {
    if (!isDirty) return undefined;
    const handler = (event) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty, message]);
}
