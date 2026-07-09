import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading } from '../components/PageState';
import { planConfigApi, PlanConfig, PlanUpdatePayload, CatalogEntry } from '../api/planConfig';
import { planStyle } from '../utils/planStyles';

// Short marketing tagline per tier (UI copy only — no business logic).
const PLAN_TAGLINE: Record<string, string> = {
  FREE: 'Get started at no cost',
  SILVER: 'For small, growing teams',
  GOLD: 'Advanced tools for scaling businesses',
  PLATINUM: 'Everything, unlocked',
};

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

const rupees = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
const periodSuffix = (bp: string) => (bp && bp !== 'none' ? `/${bp}` : '');

export default function PlanConfigPage() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ['plan-config'], queryFn: planConfigApi.list });

  // The plan currently open in the edit modal (null = closed) + its working draft.
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [form, setForm] = useState<Draft | null>(null);

  const mutation = useMutation({
    mutationFn: ({ planKey, payload }: { planKey: string; payload: PlanUpdatePayload }) =>
      planConfigApi.update(planKey, payload),
    onSuccess: (_res, vars) => {
      toast.success(`${vars.planKey} plan updated. Changes are live for all tenants on this plan.`);
      qc.invalidateQueries({ queryKey: ['plan-config'] });
      setEditingKey(null);
      setForm(null);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Failed to update plan.'),
  });

  const plans = query.data?.plans ?? [];
  const moduleCatalog = query.data?.module_catalog ?? [];
  const billingPeriods = query.data?.billing_periods ?? ['none', 'monthly', 'yearly'];
  const moduleLabel = useMemo(() => {
    const m: Record<string, string> = {};
    moduleCatalog.forEach((c) => { m[c.key] = c.label; });
    return m;
  }, [moduleCatalog]);

  const editingPlan = plans.find((p) => p.plan_key === editingKey) || null;

  const openEdit = (p: PlanConfig) => {
    setEditingKey(p.plan_key);
    setForm(toDraft(p));
  };
  const closeEdit = () => { setEditingKey(null); setForm(null); };

  const patch = (p: Partial<Draft>) => setForm((prev) => (prev ? { ...prev, ...p } : prev));
  const toggleModule = (key: string) =>
    setForm((prev) => {
      if (!prev) return prev;
      const cur = new Set(prev.modules);
      cur.has(key) ? cur.delete(key) : cur.add(key);
      return { ...prev, modules: cur };
    });

  const save = () => {
    if (!editingPlan || !form) return;
    if (!form.name.trim()) { toast.error('Plan name cannot be empty.'); return; }
    const price = Number(form.price_rupees);
    if (Number.isNaN(price) || price < 0) { toast.error('Price must be a positive number.'); return; }
    const limit = Number(form.user_limit);
    if (!Number.isInteger(limit) || limit < 1) { toast.error('User limit must be at least 1.'); return; }
    const cap = form.free_invoice_cap.trim() === '' ? null : Number(form.free_invoice_cap);
    if (cap != null && (!Number.isInteger(cap) || cap < 0)) { toast.error('Invoice cap must be 0 or more (blank = unlimited).'); return; }

    const payload: PlanUpdatePayload = {
      name: form.name.trim(),
      price_paise: Math.round(price * 100),
      billing_period: form.billing_period,
      user_limit: limit,
      free_invoice_cap: cap,
      is_active: form.is_active,
      modules: [...form.modules].sort(),
    };
    mutation.mutate({ planKey: editingPlan.plan_key, payload });
  };

  if (query.isLoading) return <AppLayout title="Super Admin — Plan Configuration"><PageLoading message="Loading plan configuration…" /></AppLayout>;
  if (query.isError) return <AppLayout title="Super Admin — Plan Configuration"><PageError message="Failed to load plan configuration." /></AppLayout>;

  return (
    <AppLayout title="Super Admin — Plan Configuration">
      {/* Intro */}
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold text-neutral-900">Plan Configuration</h1>
        <p className="mt-1 max-w-3xl text-sm text-neutral-500">
          Manage your subscription tiers. Editing a plan applies pricing, limits and module access
          <strong className="text-neutral-700"> immediately</strong> to every tenant on that plan.
        </p>
      </div>

      {/* Plan cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
        {plans.map((p) => (
          <PlanCard key={p.plan_key} plan={p} moduleLabel={moduleLabel} onEdit={() => openEdit(p)} />
        ))}
      </div>

      {/* Edit modal */}
      {editingPlan && form && (
        <EditPlanModal
          plan={editingPlan}
          form={form}
          moduleCatalog={moduleCatalog}
          billingPeriods={billingPeriods}
          saving={mutation.isPending}
          onPatch={patch}
          onToggleModule={toggleModule}
          onClose={closeEdit}
          onSave={save}
        />
      )}
    </AppLayout>
  );
}

/* ─────────────────────────── Plan summary card ─────────────────────────── */
function PlanCard({ plan, moduleLabel, onEdit }: { plan: PlanConfig; moduleLabel: Record<string, string>; onEdit: () => void; }) {
  const style = planStyle(plan.plan_key);
  const modules = [...plan.modules].sort();
  const SHOWN = 6;

  return (
    <div className="group flex flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-xl">
      {/* Gradient header */}
      <div className={`relative ${style.header} px-5 py-5 text-white`}>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-lg font-bold leading-tight">{plan.name}</p>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-white/70">{plan.plan_key}</p>
          </div>
          <span className="material-icons text-2xl text-white/80" aria-hidden="true">{style.icon}</span>
        </div>
        <div className="mt-4 flex items-end gap-1">
          <span className="text-3xl font-black tracking-tight">{rupees(plan.price_paise)}</span>
          <span className="mb-1 text-xs font-medium text-white/75">{periodSuffix(plan.billing_period)}</span>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col px-5 pb-5 pt-4">
        <p className="text-sm text-neutral-500">{PLAN_TAGLINE[plan.plan_key] ?? 'Subscription plan'}</p>

        {/* Quick stats */}
        <div className="mt-4 space-y-2 rounded-xl bg-neutral-50 p-3">
          <Stat icon="group" label="Max Users" value={String(plan.user_limit)} />
          <Stat icon="widgets" label="Modules" value={String(plan.modules.length)} />
          <Stat icon="receipt_long" label="Svc Invoices / mo" value={plan.free_invoice_cap == null ? '∞' : String(plan.free_invoice_cap)} />
        </div>

        {/* Module chips */}
        <p className="mt-4 text-[11px] font-bold uppercase tracking-wider text-neutral-400">Modules Included</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {modules.length === 0 ? (
            <span className="text-xs italic text-neutral-400">No modules enabled</span>
          ) : (
            <>
              {modules.slice(0, SHOWN).map((m) => (
                <span key={m} className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${style.soft}`}>
                  {moduleLabel[m] ?? m}
                </span>
              ))}
              {modules.length > SHOWN && (
                <span className="rounded-md bg-neutral-100 px-2 py-0.5 text-[11px] font-semibold text-neutral-500">
                  +{modules.length - SHOWN} more
                </span>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="mt-5 flex items-center justify-between border-t border-neutral-100 pt-4">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${plan.is_active ? 'bg-green-100 text-green-700' : 'bg-neutral-200 text-neutral-500'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${plan.is_active ? 'bg-green-500' : 'bg-neutral-400'}`} />
            {plan.is_active ? 'Active' : 'Inactive'}
          </span>
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3.5 py-2 text-sm font-semibold text-neutral-700 shadow-sm transition hover:border-primary hover:text-primary"
          >
            <span className="material-icons text-base">edit</span>
            Edit Plan
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
        <span className="material-icons text-base text-neutral-400">{icon}</span>
        {label}
      </span>
      <span className="text-sm font-bold text-neutral-800">{value}</span>
    </div>
  );
}

/* ─────────────────────────────── Edit modal ─────────────────────────────── */
function EditPlanModal({
  plan, form, moduleCatalog, billingPeriods, saving,
  onPatch, onToggleModule, onClose, onSave,
}: {
  plan: PlanConfig;
  form: Draft;
  moduleCatalog: CatalogEntry[];
  billingPeriods: string[];
  saving: boolean;
  onPatch: (p: Partial<Draft>) => void;
  onToggleModule: (key: string) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  const style = planStyle(plan.plan_key);
  const label = 'mb-1 block text-[11px] font-bold uppercase tracking-wider text-neutral-500';
  const input = 'w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-800 shadow-sm transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/50 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className={`flex items-center justify-between ${style.header} px-6 py-4 text-white`}>
          <div className="flex items-center gap-3">
            <span className="material-icons text-2xl text-white/90" aria-hidden="true">{style.icon}</span>
            <div>
              <h2 className="text-lg font-bold leading-tight">Edit Subscription Plan</h2>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-white/70">{plan.plan_key}</p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="material-icons rounded-full p-1 text-white/80 transition hover:bg-white/20 hover:text-white">close</button>
        </div>

        {/* Modal body (scrolls) */}
        <div className="flex-1 space-y-7 overflow-y-auto px-6 py-6">
          {/* Basic info + Pricing */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <section>
              <SectionHeader icon="info" title="Basic Information" />
              <div className="mt-3 space-y-4">
                <div>
                  <label className={label}>Plan Name</label>
                  <input className={input} value={form.name} onChange={(e) => onPatch({ name: e.target.value })} />
                </div>
                <div>
                  <label className={label}>Plan Code</label>
                  <input className={`${input} cursor-not-allowed bg-neutral-100 text-neutral-500`} value={plan.plan_key} readOnly title="The plan code is a fixed identifier and cannot be changed." />
                </div>
              </div>
            </section>

            <section>
              <SectionHeader icon="payments" title="Pricing & Status" />
              <div className="mt-3 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={label}>Base Price (₹)</label>
                    <input type="number" min={0} step="0.01" className={input} value={form.price_rupees} onChange={(e) => onPatch({ price_rupees: e.target.value })} />
                  </div>
                  <div>
                    <label className={label}>Billing Cycle</label>
                    <select className={input} value={form.billing_period} onChange={(e) => onPatch({ billing_period: e.target.value })}>
                      {billingPeriods.map((b) => <option key={b} value={b}>{b}</option>)}
                    </select>
                  </div>
                </div>
                {/* Active toggle */}
                <div className="flex items-center justify-between rounded-lg border border-neutral-200 px-3 py-2.5">
                  <div>
                    <p className="text-sm font-semibold text-neutral-800">Plan Active</p>
                    <p className="text-xs text-neutral-400">Inactive plans cannot be assigned to tenants.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onPatch({ is_active: !form.is_active })}
                    className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${form.is_active ? 'bg-green-500' : 'bg-neutral-300'}`}
                    aria-pressed={form.is_active}
                  >
                    <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${form.is_active ? 'translate-x-5' : 'translate-x-0.5'}`} />
                  </button>
                </div>
              </div>
            </section>
          </div>

          {/* Resource quotas */}
          <section>
            <SectionHeader icon="tune" title="Resource Quotas" />
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className={label}>Max Users</label>
                <input type="number" min={1} className={input} value={form.user_limit} onChange={(e) => onPatch({ user_limit: e.target.value })} />
              </div>
              <div>
                <label className={label}>Service Invoices / month <span className="font-normal normal-case text-neutral-400">(blank = unlimited)</span></label>
                <input type="number" min={0} placeholder="∞" className={input} value={form.free_invoice_cap} onChange={(e) => onPatch({ free_invoice_cap: e.target.value })} />
              </div>
            </div>
          </section>

          {/* Included modules */}
          <section>
            <div className="flex items-center justify-between">
              <SectionHeader icon="widgets" title="Included Modules" />
              <span className="text-xs font-semibold text-neutral-500">{form.modules.size} of {moduleCatalog.length} enabled</span>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
              {moduleCatalog.map((m) => {
                const on = form.modules.has(m.key);
                return (
                  <button
                    type="button"
                    key={m.key}
                    onClick={() => onToggleModule(m.key)}
                    className={`flex items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition ${on ? `${style.card} ${style.text} font-semibold shadow-sm` : 'border-neutral-200 bg-white text-neutral-600 hover:border-neutral-300 hover:bg-neutral-50'}`}
                  >
                    <span className="truncate">{m.label}</span>
                    <span className={`material-icons text-lg ${on ? style.text : 'text-neutral-300'}`}>
                      {on ? 'check_box' : 'check_box_outline_blank'}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>
        </div>

        {/* Modal footer */}
        <div className="flex items-center justify-end gap-3 border-t border-neutral-200 bg-neutral-50 px-6 py-4">
          <button type="button" onClick={onClose} className="rounded-lg border border-neutral-200 bg-white px-5 py-2 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-100">
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="material-icons text-base">save</span>
            {saving ? 'Saving…' : 'Update Plan'}
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-neutral-100 pb-1.5">
      <span className="material-icons text-lg text-primary">{icon}</span>
      <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-600">{title}</h3>
    </div>
  );
}
