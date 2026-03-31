import { useEffect, useState } from 'react';

export interface ConfirmDialogOptions {
  message: string;
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  type?: 'confirm' | 'warning' | 'danger';
}

interface ConfirmDialogRequest {
  options: ConfirmDialogOptions;
  resolve: (value: boolean) => void;
}

let openConfirmDialogImpl: ((options: ConfirmDialogOptions) => Promise<boolean>) | null = null;

export const openConfirmDialog = (options: ConfirmDialogOptions): Promise<boolean> => {
  if (openConfirmDialogImpl) {
    return openConfirmDialogImpl(options);
  }

  // Fallback during startup edge-cases before host mounts.
  return Promise.resolve(window.confirm(options.message));
};

export const ConfirmDialogHost = () => {
  const [request, setRequest] = useState<ConfirmDialogRequest | null>(null);

  useEffect(() => {
    openConfirmDialogImpl = (options: ConfirmDialogOptions) =>
      new Promise<boolean>((resolve) => {
        setRequest({ options, resolve });
      });

    return () => {
      openConfirmDialogImpl = null;
    };
  }, []);

  if (!request) {
    return null;
  }

  const { options, resolve } = request;
  const {
    message,
    title = 'Please Confirm',
    confirmLabel = options.type === 'danger' ? 'Confirm' : 'Yes',
    cancelLabel = 'Cancel',
    type = 'confirm',
  } = options;

  const close = (result: boolean) => {
    resolve(result);
    setRequest(null);
  };

  const confirmButtonClass =
    type === 'danger'
      ? 'bg-red-600 hover:bg-red-700 focus:ring-red-200'
      : type === 'warning'
      ? 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-200'
      : 'bg-primary hover:bg-primary/90 focus:ring-primary/20';

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      onClick={() => close(false)}
    >
      <div
        className="hms-card w-full max-w-md space-y-5 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="space-y-2">
          <h2 id="confirm-dialog-title" className="font-display text-lg font-bold text-neutral-900">
            {title}
          </h2>
          <p className="text-sm leading-relaxed text-neutral-600">{message}</p>
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => close(false)}
            className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={() => close(true)}
            className={`rounded-lg px-4 py-2.5 text-sm font-semibold text-white shadow-lg transition focus:outline-none focus:ring-2 ${confirmButtonClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
