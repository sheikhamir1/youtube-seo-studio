import { Check, Copy } from 'lucide-react';

import { useCopyToClipboard } from '../../hooks/useCopyToClipboard';
import { Button } from './Button';

/** Copy button that confirms success without leaving the page. */
export function CopyButton({ value, label = 'Copy', copiedLabel = 'Copied', size = 'sm', variant = 'secondary', onCopied }) {
  const { copied, copy } = useCopyToClipboard();

  return (
    <Button
      size={size}
      variant={copied ? 'success' : variant}
      icon={copied ? Check : Copy}
      onClick={async () => {
        const ok = await copy(value);
        if (ok) onCopied?.();
      }}
      aria-label={copied ? copiedLabel : label}
    >
      {copied ? copiedLabel : label}
    </Button>
  );
}

export default CopyButton;
