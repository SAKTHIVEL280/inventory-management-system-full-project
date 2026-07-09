/**
 * SubscriptionCard — premium tenant subscription widget for the Dashboard.
 *
 * Presents the tenant's current plan with plan-specific colors/icon, status,
 * renewal/expiry, days remaining (except FREE), user usage and module count.
 * Purely presentational — reads from useSubscription; no business logic here.
 * Visual language matches Super Admin → Plan Configuration (shared planStyle).
 */
import { useSubscription } from '../hooks/useSubscription';
import { useAuthStore } from '../store/auth';
import { planStyle } from '../utils/planStyles';

const daysUntil = (iso: string | null): number | null => {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
};

const fmtDate = (iso: string | null): string | null => {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
};

export const SubscriptionCard = () => {
  const user = useAuthStore((s) => s.user);
  const { plan, planName, userLimit, activeUserCount, expiryDate, modules } = useSubscription();

  // Super Admins have no tenant plan; render nothing (also nothing while loading).
  if (user?.is_super_admin || !plan) return null;

  const style = planStyle(plan);
  const isFree = plan === 'FREE';
  const effectiveExpiry = isFree ? null : expiryDate;
  const daysLeft = daysUntil(effectiveExpiry);
  const expired = daysLeft !== null && daysLeft < 0;
  const expiringSoon = daysLeft !== null && daysLeft >= 0 && daysLeft <= 30;

  const used = activeUserCount ?? 0;
  const limit = userLimit ?? 0;
  const usagePct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const atLimit = limit > 0 && used >= limit;

  return (
    <section className="overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm">
      <div className="flex flex-col md:flex-row">
        {/* Plan identity (gradient) */}
        <div className={`relative flex flex-col justify-between gap-4 px-6 py-5 text-white md:w-72 md:shrink-0 ${style.header}`}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-white/70">Current Plan</p>
              <p className="mt-1 text-2xl font-black leading-tight">{planName || plan}</p>
              <span className="mt-1 inline-flex items-center rounded-full bg-white/20 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide">
                {plan}
              </span>
            </div>
            <span className="material-icons text-3xl text-white/85" aria-hidden="true">{style.icon}</span>
          </div>
          {/* Status pill */}
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-bold uppercase tracking-wide">
            <span className="h-2 w-2 rounded-full bg-green-300 shadow-[0_0_0_3px_rgba(255,255,255,0.15)]" />
            Active
          </span>
        </div>

        {/* Stats */}
        <div className="grid flex-1 grid-cols-2 gap-px bg-neutral-100 lg:grid-cols-4">
          {/* User usage */}
          <div className="flex flex-col justify-center bg-white px-5 py-4">
            <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-neutral-400">
              <span className="material-icons text-base text-neutral-400">group</span> Users
            </p>
            <p className="mt-1 text-lg font-bold text-neutral-800">
              {used}<span className="text-sm font-medium text-neutral-400"> / {limit || '—'}</span>
            </p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
              <div
                className={`h-full rounded-full ${atLimit ? 'bg-red-500' : style.accent}`}
                style={{ width: `${usagePct}%` }}
              />
            </div>
          </div>

          {/* Modules */}
          <div className="flex flex-col justify-center bg-white px-5 py-4">
            <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-neutral-400">
              <span className="material-icons text-base text-neutral-400">widgets</span> Modules
            </p>
            <p className="mt-1 text-lg font-bold text-neutral-800">{modules.length}</p>
            <p className="mt-0.5 text-xs text-neutral-400">enabled</p>
          </div>

          {/* Days remaining (hidden for FREE) */}
          <div className="flex flex-col justify-center bg-white px-5 py-4">
            <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-neutral-400">
              <span className="material-icons text-base text-neutral-400">schedule</span> Days Left
            </p>
            {isFree ? (
              <p className="mt-1 text-lg font-bold text-neutral-800">∞</p>
            ) : daysLeft === null ? (
              <p className="mt-1 text-lg font-bold text-neutral-800">—</p>
            ) : (
              <p className={`mt-1 text-lg font-bold ${expired ? 'text-red-600' : expiringSoon ? 'text-amber-600' : 'text-neutral-800'}`}>
                {expired ? 'Expired' : `${daysLeft}`}
                {!expired && <span className="text-sm font-medium text-neutral-400"> day{daysLeft === 1 ? '' : 's'}</span>}
              </p>
            )}
            {isFree && <p className="mt-0.5 text-xs text-neutral-400">no expiry</p>}
          </div>

          {/* Renewal / expiry date */}
          <div className="flex flex-col justify-center bg-white px-5 py-4">
            <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-neutral-400">
              <span className="material-icons text-base text-neutral-400">event</span> Renews / Expires
            </p>
            <p className="mt-1 text-sm font-bold text-neutral-800">
              {isFree ? 'Never' : (fmtDate(effectiveExpiry) ?? '—')}
            </p>
            {!isFree && (expiringSoon || expired) && (
              <p className={`mt-0.5 text-xs font-semibold ${expired ? 'text-red-600' : 'text-amber-600'}`}>
                {expired ? 'Renew to restore access' : 'Renew soon'}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
