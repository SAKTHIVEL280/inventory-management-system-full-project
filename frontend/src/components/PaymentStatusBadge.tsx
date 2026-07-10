/**
 * PaymentStatusBadge — consistent, color-coded payment-status pill.
 *
 * Paid → green · Partially Paid → amber · Not Paid → red. Purely presentational:
 * it maps an existing payment-status value to a badge and never changes any logic.
 * Matches the green/amber/red language used by the Sales Invoices screen.
 */
interface PaymentStatusBadgeProps {
  status?: string | null;
  size?: 'sm' | 'md';
  className?: string;
}

type Tone = { label: string; classes: string; icon: string };

const paymentTone = (status?: string | null): Tone => {
  const s = (status || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (s === 'paid' || s === 'fully_paid') {
    return { label: 'Paid', classes: 'bg-green-100 text-green-700 ring-green-600/20', icon: 'check_circle' };
  }
  if (s === 'partial' || s === 'partially_paid' || s === 'partial_paid') {
    return { label: 'Partially Paid', classes: 'bg-amber-100 text-amber-700 ring-amber-600/20', icon: 'timelapse' };
  }
  // unpaid / not_paid / empty / anything else
  return { label: 'Not Paid', classes: 'bg-red-100 text-red-700 ring-red-600/20', icon: 'error' };
};

const SIZES: Record<NonNullable<PaymentStatusBadgeProps['size']>, string> = {
  sm: 'px-2 py-0.5 text-[11px]',
  md: 'px-2.5 py-1 text-xs',
};

export const PaymentStatusBadge = ({ status, size = 'md', className = '' }: PaymentStatusBadgeProps) => {
  const tone = paymentTone(status);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-semibold ring-1 ring-inset ${SIZES[size]} ${tone.classes} ${className}`}
      title={tone.label}
    >
      <span className="material-icons text-[0.9em] leading-none" aria-hidden="true">{tone.icon}</span>
      {tone.label}
    </span>
  );
};
