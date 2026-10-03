import { AlertTriangle } from 'lucide-react';

import { Button } from './Button';
import { Modal } from './Modal';

/** Confirmation dialog used before any destructive action. */
export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  isLoading = false,
}) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            {cancelLabel}
          </Button>
          <Button variant={variant} onClick={onConfirm} isLoading={isLoading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex gap-3">
        <AlertTriangle
          className={variant === 'danger' ? 'mt-0.5 h-5 w-5 shrink-0 text-danger' : 'mt-0.5 h-5 w-5 shrink-0 text-warning'}
          aria-hidden="true"
        />
        <p className="text-sm text-muted">{message}</p>
      </div>
    </Modal>
  );
}

export default ConfirmDialog;
