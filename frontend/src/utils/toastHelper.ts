/**
 * Toast Notification Helper Functions
 * 
 * Centralized toast notifications for the entire application
 * All toast notifications should use these functions for consistency
 */

import { toast } from 'sonner';

// Toast duration settings (in milliseconds)
const TOAST_DURATION = {
  success: 3000,
  error: 5000,
  warning: 4000,
  info: 3000,
  loading: 2000,
};

/**
 * Success Toast - Green color
 * Used for: Successful operations, completions
 */
export const showSuccess = (message: string, duration: number = TOAST_DURATION.success) => {
  return toast.success(message, {
    duration,
  });
};

/**
 * Error Toast - Red color
 * Used for: Validation errors, API failures, critical issues
 */
export const showError = (message: string, duration: number = TOAST_DURATION.error) => {
  return toast.error(message, {
    duration,
  });
};

/**
 * Warning Toast - Amber/Yellow color
 * Used for: Warnings, cautions, non-critical issues
 */
export const showWarning = (message: string, duration: number = TOAST_DURATION.warning) => {
  return toast.warning(message, {
    duration,
  });
};

/**
 * Info Toast - Blue color
 * Used for: Informational messages, updates
 */
export const showInfo = (message: string, duration: number = TOAST_DURATION.info) => {
  return toast.info(message, {
    duration,
  });
};

/**
 * Loading Toast - Shows a loading spinner
 * Used for: In-progress operations
 */
export const showLoading = (message: string) => {
  return toast.loading(message, {
    duration: TOAST_DURATION.loading,
  });
};

/**
 * Confirmation with Toast Feedback
 * Shows a confirmation dialog (native browser confirm) with toast notifications
 * 
 * @param message - Confirmation message
 * @param options - Options object
 */
export const confirmWithToast = async (
  message: string,
  options?: {
    onConfirm?: () => void | Promise<void>;
    onCancel?: () => void;
    type?: 'confirm' | 'warning' | 'danger';
    successMessage?: string;
  }
): Promise<boolean> => {
  const { onConfirm, onCancel, type = 'confirm', successMessage } = options || {};

  // Show warning/info toast before confirmation
  if (type === 'danger') {
    showWarning(message);
  }

  // Use native browser confirm (in production, replace with custom modal)
  const confirmed = window.confirm(message);

  if (confirmed) {
    if (onConfirm) {
      try {
        await onConfirm();
        if (successMessage) {
          showSuccess(successMessage);
        } else if (type === 'danger') {
          showSuccess('Action completed successfully');
        }
      } catch (error) {
        showError('Operation failed. Please try again.');
      }
    }
  } else {
    if (onCancel) {
      onCancel();
    }
  }

  return confirmed;
};

/**
 * Delete Confirmation Toast
 * Specialized confirmation for delete operations
 */
export const confirmDelete = async (
  itemName: string,
  onConfirmDelete: () => void | Promise<void>
): Promise<boolean> => {
  return confirmWithToast(
    `Are you sure you want to delete "${itemName}"? This action cannot be undone.`,
    {
      onConfirm: onConfirmDelete,
      type: 'danger',
      successMessage: `${itemName} deleted successfully`,
    }
  );
};

// Re-export toast for direct use
export { toast };
