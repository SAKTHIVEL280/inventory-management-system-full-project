interface PageStateProps {
  message: string;
}

export const PageLoading = ({ message }: PageStateProps) => {
  return (
    <div className="hms-card p-6" role="status" aria-live="polite">
      <p className="text-sm font-medium text-neutral-600">{message}</p>
    </div>
  );
};

export const PageError = ({ message }: PageStateProps) => {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4" role="alert" aria-live="assertive">
      <p className="text-sm font-medium text-red-700">{message}</p>
    </div>
  );
};

export const PageEmpty = ({ message }: PageStateProps) => {
  return (
    <div className="hms-card p-6" role="status" aria-live="polite">
      <p className="text-sm font-medium text-neutral-600">{message}</p>
    </div>
  );
};
