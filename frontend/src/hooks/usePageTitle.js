import { useEffect } from 'react';

import { PRODUCT_NAME } from '../constants';

/** Keeps document.title in sync with the current page. */
export function usePageTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · ${PRODUCT_NAME}` : PRODUCT_NAME;
  }, [title]);
}
