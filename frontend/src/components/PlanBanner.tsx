/**
 * PlanBanner (Module M6)
 *
 * Shows the tenant's active plan and an expiry reminder (BRD §9.2). Renders
 * nothing for Super Admins (no tenant) or while entitlements are loading.
 */
import { useSubscription } from '../hooks/useSubscription';
import { useAuthStore } from '../store/auth';

const daysUntil = (iso: string | null): number | null => {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
};

export const PlanBanner = () => {
  const user = useAuthStore((s) => s.user);
  const { plan, expiryDate } = useSubscription();

  if (user?.is_super_admin || !plan) return null;

  // FREE plan has no subscription fee and never expires (BRD §5.1).
  const isFree = plan === 'FREE';
  const effectiveExpiry = isFree ? null : expiryDate;

  const left = daysUntil(effectiveExpiry);
  const expiringSoon = left !== null && left <= 30;
  const expired = left !== null && left < 0;

  const tone = expired
    ? 'border-red-300 bg-red-50 text-red-800'
    : expiringSoon
      ? 'border-amber-300 bg-amber-50 text-amber-800'
      : 'border-neutral-200 bg-neutral-50 text-neutral-600';

  return (
    <div className={`mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border px-4 py-2 text-sm ${tone}`}>
      <span>
        Active plan: <strong>{plan}</strong>
        {effectiveExpiry && <> &middot; {expired ? 'expired on' : 'renews/expires'} {effectiveExpiry}</>}
      </span>
      {(expiringSoon || plan === 'FREE') && (
        <span className="font-medium">
          {expired
            ? 'Your subscription has expired — please renew.'
            : expiringSoon
              ? `Expires in ${left} day(s) — renew to avoid interruption.`
              : 'Upgrade for more modules and users.'}
        </span>
      )}
    </div>
  );
};
