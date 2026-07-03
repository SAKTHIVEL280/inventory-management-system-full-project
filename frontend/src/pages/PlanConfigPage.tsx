import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading } from '../components/PageState';
import { planConfigApi, PlanConfig, PlanUpdatePayload } from '../api/planConfig';

const PLAN_BADGE: Record<string, string> = {
  FREE: 'bg-neutral-200 text-neutral-700',
  SILVER: 'bg-slate-300 text-slate-800',
  GOLD: 'bg-amber-300 text-amber-900',
  PLATINUM: 'bg-violet-200 text-violet-800',
};
const planClass = (p: string) => PLAN_BADGE[p.toUpperCase()] ?? 'bg-neutral-200 text-neutral-700';

// Editable, per-plan working copy (price is edited in rupees for usability).
type Draft = {
  name: string;
  price_rupees: string;
  billing_period: string;
  user_limit: string;
  free_invoice_cap: string; // '' = unlimited
  is_active: boolean;
  modules: Set<string>;
};

const toDraft = (p: PlanConfig): Draft => ({
  name: p.name,
  price_rupees: (p.price_paise / 100).toString(),
  billing_period: p.billing_period,
  user_limit: String(p.user_limit),
  free_invoice_cap: p.free_invoice_cap == null ? '' : String(p.free_invoice_cap),
  is_active: p.is_active,
  modules: new Set(p.modules),
});

const setEq = (a: Set<string>, b: Set<string>) => a.size === b.size && [...a].every((x) => b.has(x));

export default function PlanConfigPage() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ['plan-config'], queryFn: planConfigApi.list });

  const [drafts, setDrafts] = useState<Record<string, Draft>>({});

  // Seed local drafts whenever the server data (re)loads.
  useEffect(() => {
    if (!query.data) return;
    const next: Record<string, Draft> = {};
    for (const p of query.data.plans) next[p.plan_key] = toDraft(p);
    setDrafts(next);
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: ({ planKey, payload }: { planKey: string; payload: PlanUpdatePayload }) =>
      planConfigApi.update(planKey, payload),
    onSuccess: (_res, vars) => {
      toast.success(`${vars.planKey} plan updated. Changes are live for all tenants on this plan.`);
      qc.invalidateQueries({ queryKey: ['plan-config'] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Failed to update plan.'),
  });

  const plans = query.data?.plans ?? [];
  const moduleCatalog = query.data?.module_catalog ?? [];
  const billingPeriods = query.data?.billing_periods ?? ['none', 'monthly', 'yearly'];

  const isDirty = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (const p of plans) {
      const d = drafts[p.plan_key];
      if (!d) { map[p.plan_key] = false; continue; }
      map[p.plan_key] =
        d.name !== p.name ||
        d.price_rupees !== (p.price_paise / 100).toString() ||
        d.billing_period !== p.billing_period ||
        d.user_limit !== String(p.user_limit) ||
        d.free_invoice_cap !== (p.free_invoice_cap == null ? '' : String(p.free_invoice_cap)) ||
        d.is_active !== p.is_active ||
        !setEq(d.modules, new Set(p.modules));
    }
    return map;
  }, [drafts, plans]);

  const update = (key: string, patch: Partial<Draft>) =>
    setDrafts((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  const toggleModule = (key: string, value: string) =>
    setDrafts((prev) => {
      const cur = new Set(prev[key].modules);
      cur.has(value) ? cur.delete(value) : cur.add(value);
      return { ...prev, [key]: { ...prev[key], modules: cur } };
    });

  const save = (p: PlanConfig) => {
    const d = drafts[p.plan_key];
    if (!d) return;
    if (!d.name.trim()) { toast.error('Plan name cannot be empty.'); return; }
    const rupees = Number(d.price_rupees);
    if (Number.isNaN(rupees) || rupees < 0) { toast.error('Price must be a positive number.'); return; }
    const limit = Number(d.user_limit);
    if (!Number.isInteger(limit) || limit < 1) { toast.error('User limit must be at least 1.'); return; }
    const cap = d.free_invoice_cap.trim() === '' ? null : Number(d.free_invoice_cap);
    if (cap != null && (!Number.isInteger(cap) || cap < 0)) { toast.error('Invoice cap must be 0 or more (blank = unlimited).'); return; }

    const payload: PlanUpdatePayload = {
      name: d.name.trim(),
      price_paise: Math.round(rupees * 100),
      billing_period: d.billing_period,
      user_limit: limit,
      free_invoice_cap: cap,
      is_active: d.is_active,
      modules: [...d.modules].sort(),
    };
    mutation.mutate({ planKey: p.plan_key, payload });
  };

  const reset = (p: PlanConfig) => update(p.plan_key, toDraft(p));

  if (query.isLoading) return <AppLayout title="Super Admin — Plan Configuration"><PageLoading message="Loading plan configuration…" /></AppLayout>;
  if (query.isError) return <AppLayout title="Super Admin — Plan Configuration"><PageError message="Failed to load plan configuration." /></AppLayout>;

  const th = 'px-4 py-3 text-left text-xs font-bold uppercase tracking-wider text-neutral-500';
  const cellInput = 'w-full rounded-lg border border-neutral-200 px-2 py-1.5 text-sm focus:border-primary focus:outline-none';

  return (
    <AppLayout title="Super Admin — Plan Configuration">
      <div className="mb-4">
        <p className="text-sm text-neutral-600">
          Configure each subscription plan below. Saving a plan applies the new pricing, user limits
          and module access <strong>immediately</strong> to every tenant on that plan. Feature access is
          granted automatically based on the modules enabled for the plan.
        </p>
      </div>

      <div className="hms-card overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="border-b border-neutral-200 bg-neutral-50">
            <tr>
              <th className={th}>Setting</th>
              {plans.map((p) => (
                <th key={p.plan_key} className="px-4 py-3 text-center">
                  <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${planClass(p.plan_key)}`}>{p.plan_key}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {/* Plan Name */}
            <tr>
              <td className="px-4 py-2 font-semibold text-neutral-700">Plan Name</td>
              {plans.map((p) => (
                <td key={p.plan_key} className="px-4 py-2">
                  <input className={cellInput} value={drafts[p.plan_key]?.name ?? ''} onChange={(e) => update(p.plan_key, { name: e.target.value })} />
                </td>
              ))}
            </tr>
            {/* Pricing */}
            <tr>
              <td className="px-4 py-2 font-semibold text-neutral-700">Price (₹)</td>
              {plans.map((p) => (
                <td key={p.plan_key} className="px-4 py-2">
                  <input type="number" min={0} step="0.01" className={cellInput} value={drafts[p.plan_key]?.price_rupees ?? ''} onChange={(e) => update(p.plan_key, { price_rupees: e.target.value })} />
                </td>
              ))}
            </tr>
            {/* Billing Period */}
            <tr>
              <td className="px-4 py-2 font-semibold text-neutral-700">Billing Period</td>
              {plans.map((p) => (
                <td key={p.plan_key} className="px-4 py-2">
                  <select className={cellInput} value={drafts[p.plan_key]?.billing_period ?? 'monthly'} onChange={(e) => update(p.plan_key, { billing_period: e.target.value })}>
                    {billingPeriods.map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                </td>
              ))}
            </tr>
            {/* User Limit */}
            <tr>
              <td className="px-4 py-2 font-semibold text-neutral-700">User Limit</td>
              {plans.map((p) => (
                <td key={p.plan_key} className="px-4 py-2">
                  <input type="number" min={1} className={cellInput} value={drafts[p.plan_key]?.user_limit ?? ''} onChange={(e) => update(p.plan_key, { user_limit: e.target.value })} />
                </td>
              ))}
            </tr>
            {/* FREE cap */}
            <tr>
              <td className="px-4 py-2 font-semibold text-neutral-700">Service Invoice Cap<span className="ml-1 text-xs font-normal text-neutral-400">/month (blank = ∞)</span></td>
              {plans.map((p) => (
                <td key={p.plan_key} className="px-4 py-2">
                  <input type="number" min={0} placeholder="∞" className={cellInput} value={drafts[p.plan_key]?.free_invoice_cap ?? ''} onChange={(e) => update(p.plan_key, { free_invoice_cap: e.target.value })} />
                </td>
              ))}
            </tr>
            {/* Status */}
            <tr>
              <td className="px-4 py-2 font-semibold text-neutral-700">Plan Status</td>
              {plans.map((p) => {
                const active = drafts[p.plan_key]?.is_active ?? true;
                return (
                  <td key={p.plan_key} className="px-4 py-2 text-center">
                    <button type="button" onClick={() => update(p.plan_key, { is_active: !active })}
                      className={`rounded-full px-3 py-1 text-xs font-bold ${active ? 'bg-green-100 text-green-700' : 'bg-neutral-200 text-neutral-500'}`}>
                      {active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                );
              })}
            </tr>

            {/* Module matrix */}
            <tr className="bg-neutral-50">
              <td className="px-4 py-2 text-xs font-bold uppercase tracking-wider text-neutral-500" colSpan={plans.length + 1}>Module Access</td>
            </tr>
            {moduleCatalog.map((m) => (
              <tr key={m.key}>
                <td className="px-4 py-2 text-neutral-700">{m.label}</td>
                {plans.map((p) => (
                  <td key={p.plan_key} className="px-4 py-2 text-center">
                    <input type="checkbox" className="h-4 w-4 accent-primary" checked={drafts[p.plan_key]?.modules.has(m.key) ?? false} onChange={() => toggleModule(p.plan_key, m.key)} />
                  </td>
                ))}
              </tr>
            ))}

            {/* Actions */}
            <tr className="border-t-2 border-neutral-200">
              <td className="px-4 py-3 font-semibold text-neutral-700">Save</td>
              {plans.map((p) => (
                <td key={p.plan_key} className="px-4 py-3 text-center">
                  <div className="flex flex-col items-center gap-1">
                    <button type="button" disabled={!isDirty[p.plan_key] || mutation.isPending} onClick={() => save(p)}
                      className="rounded-lg bg-primary px-4 py-1.5 text-xs font-bold text-white hover:bg-primary/90 disabled:opacity-40">
                      Save
                    </button>
                    {isDirty[p.plan_key] && (
                      <button type="button" onClick={() => reset(p)} className="text-[11px] font-semibold text-neutral-500 hover:underline">Reset</button>
                    )}
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </AppLayout>
  );
}
