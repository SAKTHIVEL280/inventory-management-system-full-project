/**
 * Toast Confirmation Helper
 * 
 * Provides a promise-based confirmation dialog using native browser confirm()
 * but with toast notifications for feedback.
 */

import { toast } from 'sonner';

/**
 * Show a confirmation dialog with toast notifications
 * @param message - Confirmation message to display
 * @param options - Options object
 * @param options.onConfirm - Callback when user confirms
 * @param options.onCancel - Callback when user cancels
 * @param options.type - Type of confirmation ('confirm' | 'warning' | 'danger')
 */
export const confirmToast = (
  message: string,
  options?: {
    onConfirm?: () => void;
    onCancel?: () => void;
    type?: 'confirm' | 'warning' | 'danger';
  }
) => {
  const { onConfirm, onCancel, type = 'confirm' } = options || {};

  // Use native confirm dialog for now (browser's built-in)
  // In production, replace with a custom modal
  const confirmed = window.confirm(message);

  if (confirmed) {
    if (type === 'danger') {
      toast.success('Action completed');
    }
    onConfirm?.();
  } else {
    onCancel?.();
  }

  return confirmed;
};

/**
 * Show a warning toast
 */
export const warningToast = (message: string) => {
  toast.warning(message, {
    duration: 4000,
  });
};

/**
 * Show an error toast
 */
export const errorToast = (message: string) => {
  toast.error(message, {
    duration: 5000,
  });
};

/**
 * Show a success toast
 */
export const successToast = (message: string) => {
  toast.success(message, {
    duration: 3000,
  });
};
