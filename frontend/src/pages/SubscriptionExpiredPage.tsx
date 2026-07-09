/**
 * SubscriptionExpiredPage
 *
 * Shown to a tenant whose PAID subscription has lapsed. Blocks all tenant modules
 * (the backend also 403s every tenant API, so this is the user-facing gate). No
 * tenant data is loaded or shown here — data is preserved and returns automatically
 * once a Super Admin renews the subscription.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../store/auth';
import { useSubscription } from '../hooks/useSubscription';
import { planStyle } from '../utils/planStyles';

const fmtDate = (iso: string | null): string | null => {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
};

export default function SubscriptionExpiredPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const logout = useAuthStore((s) => s.logout);
  const { plan, planName, expiryDate } = useSubscription();
  const [checking, setChecking] = useState(false);

  const style = planStyle(plan);

  const recheck = async () => {
    setChecking(true);
    // Re-fetch entitlements; if the Super Admin has renewed, access restores.
    await qc.invalidateQueries({ queryKey: ['subscription', 'me'] });
    setTimeout(() => setChecking(false), 600);
  };

  const handleLogout = () => {
    qc.clear();
    logout();
    navigate('/login');
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-100 p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-xl">
        {/* Header */}
        <div className={`${style.header} px-6 py-6 text-center text-white`}>
          <span className="material-icons text-5xl text-white/90" aria-hidden="true">lock_clock</span>
          <h1 className="mt-2 text-2xl font-bold">Subscription Expired</h1>
          <p className="mt-1 text-sm text-white/80">
            {planName || plan} plan{expiryDate ? ` · expired on ${fmtDate(expiryDate)}` : ''}
          </p>
        </div>

        {/* Body */}
        <div className="space-y-5 px-6 py-6">
          <p className="text-center text-sm text-neutral-600">
            Your subscription has expired and access to your modules is temporarily paused.
          </p>

          {/* Reassurance */}
          <div className="flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3">
            <span className="material-icons text-green-600">verified_user</span>
            <div>
              <p className="text-sm font-semibold text-green-800">Your data is safe</p>
              <p className="text-xs text-green-700">
                Nothing has been deleted or changed. All your invoices, products, stock and
                records return automatically the moment your plan is renewed.
              </p>
            </div>
          </div>

          {/* Renewal instructions */}
          <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3">
            <p className="text-sm font-semibold text-neutral-800">How to renew</p>
            <ol className="mt-1 list-decimal space-y-1 pl-5 text-xs text-neutral-600">
              <li>Contact your Mecandria account manager or platform administrator to renew your subscription.</li>
              <li>Once renewed, use “I’ve renewed — recheck access” below (or simply sign in again).</li>
            </ol>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={recheck}
              disabled={checking}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-primary/90 disabled:opacity-60"
            >
              <span className={`material-icons text-base ${checking ? 'animate-spin' : ''}`}>{checking ? 'progress_activity' : 'refresh'}</span>
              {checking ? 'Checking…' : 'I’ve renewed — recheck access'}
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
