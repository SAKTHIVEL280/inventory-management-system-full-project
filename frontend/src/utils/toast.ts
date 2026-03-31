/**
 * Toast Confirmation Helper
 * 
 * Provides an in-app confirmation prompt using toast action buttons.
 */

import { toast } from 'sonner';
import { confirmWithToast } from './toastHelper';

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
  return confirmWithToast(message, { onConfirm, onCancel, type });
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
