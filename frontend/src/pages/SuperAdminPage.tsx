import { useState, type ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import Cookies from 'js-cookie';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading, PageEmpty } from '../components/PageState';
import { useAuthStore } from '../store/auth';
import { superAdminApi, Tenant, TenantCreatePayload, TenantUpdatePayload, RaiseServiceInvoicePayload, ServiceInvoiceDetail } from '../api/superAdmin';

const GST_RATES = [0, 5, 12, 18, 28];
const rupees2 = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
type RaiseItem = { item_name: string; description: string; hsn_sac_code: string; quantity: number; rate_rupees: number | ''; discount_percent: number | ''; gst_rate: number; is_free: boolean };
const blankRaiseItem: RaiseItem = { item_name: '', description: '', hsn_sac_code: '998313', quantity: 1, rate_rupees: '', discount_percent: '', gst_rate: 18, is_free: false };

const PLANS = ['FREE', 'SILVER', 'GOLD', 'PLATINUM'];
const STATUSES = ['active', 'inactive', 'suspended', 'trial'];
const PAYMENT_STATUSES = ['paid', 'pending', 'overdue', 'expired'];

// Colour coding (used consistently in listing, detail, forms, dropdowns).
const PLAN_BADGE: Record<string, string> = {
  FREE: 'bg-neutral-200 text-neutral-700',
  SILVER: 'bg-slate-300 text-slate-800',
  GOLD: 'bg-amber-300 text-amber-900',
  PLATINUM: 'bg-violet-200 text-violet-800',
};
const STATUS_BADGE: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  trial: 'bg-blue-100 text-blue-700',
  inactive: 'bg-neutral-200 text-neutral-600',
  suspended: 'bg-red-100 text-red-700',
};
const PAYMENT_BADGE: Record<string, string> = {
  paid: 'bg-green-100 text-green-700',
  pending: 'bg-amber-100 text-amber-800',
  overdue: 'bg-red-100 text-red-700',
  expired: 'bg-red-200 text-red-900',
};
const planClass = (p?: string | null) => PLAN_BADGE[(p || '').toUpperCase()] ?? 'bg-neutral-200 text-neutral-700';
const statusClass = (s?: string | null) => STATUS_BADGE[(s || '').toLowerCase()] ?? 'bg-neutral-200 text-neutral-600';
const paymentClass = (p?: string | null) => PAYMENT_BADGE[(p || '').toLowerCase()] ?? 'bg-neutral-200 text-neutral-600';
const badge = 'inline-block rounded-full px-2.5 py-0.5 text-xs font-bold capitalize';

type CreateForm = {
  name: string;
  gstin?: string;
  contact_person_name?: string;
  contact_number?: string;
  email?: string;
  phone?: string;
  website?: string;
  business_category?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  country?: string;
  pincode?: string;
  subscription_plan: string;
  account_status: string;
  payment_status: string;
  subscription_start_date?: string;
  subscription_expiry_date?: string;
  tenant_code?: string;
  admin_full_name: string;
  admin_email: string;
};

type EditForm = Omit<TenantUpdatePayload, never>;

const createDefaults: CreateForm = {
  name: '', subscription_plan: 'FREE', account_status: 'active', payment_status: 'paid',
  admin_full_name: '', admin_email: '',
};

const SuperAdminPage = () => {
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Tenant | null>(null);
  const [viewing, setViewing] = useState<Tenant | null>(null);
  const [renewing, setRenewing] = useState<Tenant | null>(null);
  const [auditing, setAuditing] = useState<Tenant | null>(null);
  const [auditUser, setAuditUser] = useState('');
  const [auditFrom, setAuditFrom] = useState('');
  const [auditTo, setAuditTo] = useState('');
  const [auditPage, setAuditPage] = useState(1);
  const AUDIT_PAGE_SIZE = 50;
  const [invoicing, setInvoicing] = useState<Tenant | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [previewInv, setPreviewInv] = useState<ServiceInvoiceDetail | null>(null);
  const [cancelInv, setCancelInv] = useState<ServiceInvoiceDetail | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [invMeta, setInvMeta] = useState({ invoice_date: new Date().toISOString().slice(0, 10), due_date: '', supply_type: 'intra', notes: '' });
  const [invItems, setInvItems] = useState<RaiseItem[]>([{ ...blankRaiseItem }]);
  const [renewForm, setRenewForm] = useState({ subscription_start_date: '', subscription_expiry_date: '', payment_status: 'paid' });
  const [tempPassword, setTempPassword] = useState<{ email: string; password: string } | null>(null);

  const form = useForm<CreateForm>({ defaultValues: createDefaults });
  const editFormHook = useForm<EditForm>();

  const dashboardQuery = useQuery({
    queryKey: ['admin', 'dashboard'],
    queryFn: superAdminApi.dashboard,
    enabled: !!user?.is_super_admin,
  });

  const tenantsQuery = useQuery({
    queryKey: ['admin', 'tenants'],
    queryFn: () => superAdminApi.listTenants(),
    enabled: !!user?.is_super_admin,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'tenants'] });
    queryClient.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: TenantCreatePayload) => superAdminApi.createTenant(payload),
    onSuccess: (tenant) => {
      invalidate();
      setShowCreate(false);
      form.reset(createDefaults);
      if (tenant.admin_temporary_password) {
        setTempPassword({ email: tenant.admin_email || tenant.email || '', password: tenant.admin_temporary_password });
      }
      toast.success('ERP customer onboarded.');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TenantUpdatePayload }) => superAdminApi.updateTenant(id, payload),
    onSuccess: () => { invalidate(); setEditing(null); toast.success('ERP customer updated.'); },
  });

  const planMutation = useMutation({
    mutationFn: ({ id, plan }: { id: string; plan: string }) => superAdminApi.changePlan(id, plan),
    onSuccess: () => { invalidate(); toast.success('Plan updated.'); },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => superAdminApi.changeStatus(id, status),
    onSuccess: () => { invalidate(); toast.success('Status updated.'); },
  });

  const resetPwMutation = useMutation({
    mutationFn: (id: string) => superAdminApi.resetAdminPassword(id),
    onSuccess: (res) => {
      if (res.temporary_password) setTempPassword({ email: res.admin_email, password: res.temporary_password });
      toast.success('Admin password reset.');
    },
  });

  const renewMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { subscription_start_date?: string; subscription_expiry_date: string; payment_status?: string } }) =>
      superAdminApi.renew(id, payload),
    onSuccess: () => { invalidate(); setRenewing(null); toast.success('Subscription renewed.'); },
  });

  const impersonateMutation = useMutation({
    mutationFn: (id: string) => superAdminApi.impersonate(id),
    onSuccess: (res) => {
      // "Login As": adopt the tenant admin's token and reload into the tenant app.
      Cookies.set('access_token', res.access_token, { sameSite: 'lax' });
      toast.success(`Logging in as ${res.impersonating}…`);
      window.location.href = '/';
    },
  });

  const auditQuery = useQuery({
    queryKey: ['admin', 'audit', auditing?.id, auditUser, auditFrom, auditTo, auditPage],
    queryFn: () => superAdminApi.auditTrail(auditing!.id, {
      user: auditUser.trim() || undefined,
      date_from: auditFrom || undefined,
      date_to: auditTo || undefined,
      page: auditPage,
      page_size: AUDIT_PAGE_SIZE,
    }),
    enabled: !!auditing?.id,
  });
  const openAudit = (t: Tenant) => {
    setAuditUser(''); setAuditFrom(''); setAuditTo(''); setAuditPage(1); setAuditing(t);
  };

  const raiseInvoiceMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RaiseServiceInvoicePayload }) => superAdminApi.raiseServiceInvoice(id, payload),
    onSuccess: (res) => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ['admin', 'service-invoices'] });
      setInvoicing(null);
      setInvItems([{ ...blankRaiseItem }]);
      setInvMeta({ invoice_date: new Date().toISOString().slice(0, 10), due_date: '', supply_type: 'intra', notes: '' });
      toast.success(`Service invoice ${res.invoice_number} raised (₹${(res.grand_total / 100).toLocaleString('en-IN')}).`);
    },
  });

  const historyQuery = useQuery({
    queryKey: ['admin', 'service-invoices'],
    queryFn: () => superAdminApi.listServiceInvoices(),
    enabled: !!user?.is_super_admin && showHistory,
  });

  const invalidateHistory = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'service-invoices'] });
    queryClient.invalidateQueries({ queryKey: ['admin', 'dashboard'] });
    queryClient.invalidateQueries({ queryKey: ['admin', 'tenants'] });
  };

  const markPaidInvMutation = useMutation({
    mutationFn: (id: string) => superAdminApi.markServiceInvoicePaid(id),
    onSuccess: () => { invalidateHistory(); toast.success('Invoice marked paid.'); },
  });
  const cancelInvMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => superAdminApi.cancelServiceInvoice(id, reason),
    onSuccess: () => { invalidateHistory(); setCancelInv(null); setCancelReason(''); toast.success('Invoice cancelled.'); },
  });
  const emailInvMutation = useMutation({
    mutationFn: (id: string) => superAdminApi.emailServiceInvoice(id),
    onSuccess: (res) => toast.success(res.delivery === 'smtp' ? `Emailed to ${res.recipient}.` : `Saved to outbox (${res.recipient}).`),
  });

  const submitRaiseInvoice = () => {
    if (!invoicing) return;
    const items = invItems
      .filter((it) => it.item_name.trim())
      .map((it) => ({
        item_name: it.item_name.trim(),
        description: it.description.trim(),
        hsn_sac_code: it.hsn_sac_code.trim() || '998313',
        quantity: Number(it.quantity) || 1,
        basic_price: Math.round((Number(it.rate_rupees) || 0) * 100),
        discount_percent: Number(it.discount_percent) || 0,
        gst_rate: Number(it.gst_rate) || 0,
        is_free: !!it.is_free,
      }));
    if (items.length === 0) { toast.error('Add at least one line item with a name.'); return; }
    if (items.some((it) => !it.description)) { toast.error('Description is required for every line item.'); return; }
    raiseInvoiceMutation.mutate({
      id: invoicing.id,
      payload: {
        invoice_date: invMeta.invoice_date || undefined,
        due_date: invMeta.due_date || undefined,
        supply_type: invMeta.supply_type,
        notes: invMeta.notes || undefined,
        items,
      },
    });
  };

  const submitRenew = () => {
    if (!renewing || !renewForm.subscription_expiry_date) {
      toast.error('Expiry date is required.');
      return;
    }
    renewMutation.mutate({
      id: renewing.id,
      payload: {
        subscription_start_date: renewForm.subscription_start_date || undefined,
        subscription_expiry_date: renewForm.subscription_expiry_date,
        payment_status: renewForm.payment_status,
      },
    });
  };

  if (!user?.is_super_admin) {
    return (
      <AppLayout title="Super Admin">
        <PageError message="Super Admin privileges are required to view this page." />
      </AppLayout>
    );
  }

  const onCreate = (values: CreateForm) => {
    createMutation.mutate(values as TenantCreatePayload);
  };

  const openEdit = (t: Tenant) => {
    editFormHook.reset({
      name: t.name,
      gstin: t.gstin ?? '',
      contact_person_name: t.contact_person_name ?? '',
      contact_number: t.contact_number ?? '',
      email: t.email ?? '',
      phone: t.phone ?? '',
      website: t.website ?? '',
      business_category: t.business_category ?? '',
      address_line1: t.address_line1 ?? '',
      address_line2: t.address_line2 ?? '',
      city: t.city ?? '',
      state: t.state ?? '',
      country: t.country ?? '',
      pincode: t.pincode ?? '',
      subscription_start_date: t.subscription_start_date ?? '',
      subscription_expiry_date: t.subscription_expiry_date ?? '',
      payment_status: t.payment_status ?? 'paid',
      tenant_code: t.tenant_code ?? '',
    });
    setEditing(t);
  };

  const onEditSubmit = (values: EditForm) => {
    if (!editing) return;
    // Drop empty strings so we only send provided values.
    const payload: TenantUpdatePayload = {};
    (Object.keys(values) as (keyof EditForm)[]).forEach((k) => {
      const v = values[k];
      if (v !== undefined && v !== '') (payload[k] as unknown) = v;
    });
    updateMutation.mutate({ id: editing.id, payload });
  };

  const d = dashboardQuery.data;
  const tenants = tenantsQuery.data?.tenants ?? [];

  return (
    <AppLayout title="Super Admin — ERP Customers">
      {/* Platform metrics (BRD §4.1) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Customers', value: d?.total_erp_customers },
          { label: 'Active', value: d?.active_erp_customers },
          { label: 'Inactive / Expired', value: d?.inactive_erp_customers },
          { label: 'Expiring (30d)', value: d?.expiring_subscriptions_30d },
          { label: 'Total Sales Invoices', value: d?.total_sales_invoices },
          { label: 'Total Purchase Orders', value: d?.total_purchase_orders },
          { label: 'Total Service Invoices', value: d?.total_service_invoices },
          { label: 'Revenue (MTD)', value: d?.revenue_mtd != null ? `₹${d.revenue_mtd.toLocaleString('en-IN')}` : undefined },
          { label: 'Revenue (YTD)', value: d?.revenue_ytd != null ? `₹${d.revenue_ytd.toLocaleString('en-IN')}` : undefined },
        ].map((m) => (
          <div key={m.label} className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">{m.label}</p>
            <p className="mt-1 text-2xl font-bold text-neutral-900">{m.value ?? '—'}</p>
          </div>
        ))}
      </div>

      {/* Plan distribution (BRD §4.1) */}
      {d?.plan_distribution && (
        <div className="hms-card p-4 mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Plan Distribution</p>
          <div className="flex flex-wrap gap-4">
            {PLANS.map((p) => (
              <span key={p} className="text-sm text-neutral-700">
                <strong>{p}</strong>: {d.plan_distribution[p] ?? 0}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="hms-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-4">
          <h2 className="font-display text-lg font-bold text-neutral-900">ERP Customers (Tenants)</h2>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowHistory(true)}
              className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50"
            >
              Service Invoices
            </button>
            <a
              href={superAdminApi.exportUrl}
              className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50"
            >
              Export CSV
            </a>
            <button
              type="button"
              onClick={() => setShowCreate((v) => !v)}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90"
            >
              {showCreate ? 'Close' : 'Add ERP Customer'}
            </button>
          </div>
        </div>

        {showCreate && (
          <form onSubmit={form.handleSubmit(onCreate)} className="grid grid-cols-1 md:grid-cols-3 gap-3 border-b border-neutral-200 p-5 bg-neutral-50/60">
            <div><label className="hms-label">ERP Customer Name *</label><input className="hms-input" {...form.register('name', { required: true })} /></div>
            <div><label className="hms-label">License Number (GSTIN)</label><input className="hms-input" placeholder="29ABCDE1234F1Z5" {...form.register('gstin')} /></div>
            <div><label className="hms-label">Business Category</label><input className="hms-input" {...form.register('business_category')} /></div>
            <div><label className="hms-label">Contact Person</label><input className="hms-input" {...form.register('contact_person_name')} /></div>
            <div><label className="hms-label">Contact Number</label><input className="hms-input" placeholder="10-digit" {...form.register('contact_number')} /></div>
            <div><label className="hms-label">Email ID</label><input type="email" className="hms-input" {...form.register('email')} /></div>
            <div className="md:col-span-2"><label className="hms-label">Business Address (line 1)</label><input className="hms-input" {...form.register('address_line1')} /></div>
            <div><label className="hms-label">Address (line 2)</label><input className="hms-input" {...form.register('address_line2')} /></div>
            <div><label className="hms-label">City</label><input className="hms-input" {...form.register('city')} /></div>
            <div><label className="hms-label">State</label><input className="hms-input" {...form.register('state')} /></div>
            <div><label className="hms-label">Pincode</label><input className="hms-input" {...form.register('pincode')} /></div>
            <div><label className="hms-label">Country</label><input className="hms-input" {...form.register('country')} /></div>
            <div>
              <label className="hms-label">Subscription Plan *</label>
              <select className={`hms-input font-bold ${planClass(form.watch('subscription_plan'))}`} {...form.register('subscription_plan')}>
                {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="hms-label">Status</label>
              <select className={`hms-input font-bold capitalize ${statusClass(form.watch('account_status'))}`} {...form.register('account_status')}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="hms-label">Payment Status</label>
              <select className={`hms-input font-bold capitalize ${paymentClass(form.watch('payment_status'))}`} {...form.register('payment_status')}>
                {PAYMENT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div><label className="hms-label">Subscription Start</label><input type="date" className="hms-input" {...form.register('subscription_start_date')} /></div>
            <div><label className="hms-label">Subscription Expiry</label><input type="date" className="hms-input" {...form.register('subscription_expiry_date')} /></div>
            <div><label className="hms-label">Tenant Code</label><input className="hms-input" placeholder="Auto-generated if left blank" {...form.register('tenant_code')} /></div>
            <div className="md:col-span-3 mt-2 border-t border-neutral-200 pt-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Tenant Administrator</div>
            <div><label className="hms-label">Admin Full Name *</label><input className="hms-input" {...form.register('admin_full_name', { required: true })} /></div>
            <div><label className="hms-label">Admin Email *</label><input type="email" className="hms-input" {...form.register('admin_email', { required: true })} /></div>
            <div className="flex items-end">
              <button type="submit" disabled={createMutation.isPending} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white hover:bg-primary/90 disabled:opacity-60">
                {createMutation.isPending ? 'Onboarding…' : 'Onboard Customer'}
              </button>
            </div>
          </form>
        )}

        <div className="p-5">
          {tenantsQuery.isLoading && <PageLoading message="Loading tenants..." />}
          {tenantsQuery.isError && <PageError message="Failed to load tenants" />}
          {!tenantsQuery.isLoading && tenants.length === 0 && <PageEmpty message="No ERP customers yet." />}
          {tenants.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-neutral-50">
                  <tr className="text-left border-y border-neutral-200">
                    {['Name', 'GSTIN', 'Plan', 'Status', 'Payment', 'Users', 'Sales Inv', 'Purch Ord', 'Expiry', 'Actions'].map((h) => (
                      <th key={h} className="px-3 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {tenants.map((t: Tenant) => (
                    <tr key={t.id} className="hover:bg-neutral-50/80">
                      <td className="px-3 py-3 font-medium">{t.name}</td>
                      <td className="px-3 py-3 text-neutral-600">{t.gstin || '—'}</td>
                      <td className="px-3 py-3">
                        <select
                          className={`rounded border-0 px-2 py-1 text-xs font-bold ${planClass(t.subscription_plan)}`}
                          value={t.subscription_plan}
                          onChange={(e) => planMutation.mutate({ id: t.id, plan: e.target.value })}
                        >
                          {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-3">
                        <select
                          className={`rounded border-0 px-2 py-1 text-xs font-bold capitalize ${statusClass(t.account_status)}`}
                          value={t.account_status || 'active'}
                          onChange={(e) => statusMutation.mutate({ id: t.id, status: e.target.value })}
                        >
                          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`${badge} ${paymentClass(t.payment_status)}`}>{t.payment_status || '—'}</span>
                      </td>
                      <td className="px-3 py-3 text-neutral-600">{t.active_users ?? '—'}/{t.user_limit}</td>
                      <td className="px-3 py-3 text-neutral-600">{t.total_sales_invoices ?? '—'}</td>
                      <td className="px-3 py-3 text-neutral-600">{t.total_purchase_orders ?? '—'}</td>
                      <td className="px-3 py-3 text-neutral-600">{t.subscription_expiry_date || '—'}</td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <button type="button" onClick={() => setViewing(t)} className="rounded px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">View</button>
                        <button type="button" onClick={() => openEdit(t)} className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10">Edit</button>
                        <button type="button" onClick={() => { setRenewForm({ subscription_start_date: t.subscription_start_date ?? '', subscription_expiry_date: t.subscription_expiry_date ?? '', payment_status: t.payment_status ?? 'paid' }); setRenewing(t); }} className="rounded px-2 py-1 text-xs font-semibold text-green-700 hover:bg-green-50">Renew</button>
                        <button type="button" onClick={() => resetPwMutation.mutate(t.id)} className="rounded px-2 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-50">Reset PW</button>
                        <button type="button" onClick={() => { setInvItems([{ ...blankRaiseItem }]); setInvMeta({ invoice_date: new Date().toISOString().slice(0, 10), due_date: '', supply_type: 'intra', notes: '' }); setInvoicing(t); }} className="rounded px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50">Raise Invoice</button>
                        <button type="button" onClick={() => openAudit(t)} className="rounded px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">Audit</button>
                        <button type="button" onClick={() => { if (confirm(`Log in as ${t.name}'s admin? You will be signed in as that tenant.`)) impersonateMutation.mutate(t.id); }} className="rounded px-2 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50">Login As</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Detail / View modal (BRD §4.2 — all customer fields) */}
      {viewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-2xl max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-neutral-900">{viewing.name}</h2>
              <button type="button" onClick={() => setViewing(null)} className="material-icons text-neutral-400 hover:text-neutral-700">close</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
              {[
                ['ERP Customer Name', viewing.name],
                ['License Number (GSTIN)', viewing.gstin],
                ['Contact Person', viewing.contact_person_name],
                ['Contact Number', viewing.contact_number],
                ['Email ID', viewing.email],
                ['Business Category', viewing.business_category],
                ['Business Address', viewing.business_address],
                ['Onboarding Date', viewing.onboarding_date],
                ['Subscription Plan', viewing.subscription_plan],
                ['Subscription Start', viewing.subscription_start_date],
                ['Subscription Expiry', viewing.subscription_expiry_date],
                ['Payment Status', viewing.payment_status],
                ['Status', viewing.account_status],
                ['No. of Active Users', `${viewing.active_users ?? '—'} / ${viewing.user_limit}`],
                ['Total Sales Invoices', viewing.total_sales_invoices ?? '—'],
                ['Total Purchase Orders', viewing.total_purchase_orders ?? '—'],
                ['Tenant Code', viewing.tenant_code],
              ].map(([label, value]) => {
                let rendered: ReactNode = (value === null || value === undefined || value === '') ? '—' : String(value);
                if (label === 'Subscription Plan') rendered = <span className={`${badge} ${planClass(viewing.subscription_plan)}`}>{viewing.subscription_plan}</span>;
                else if (label === 'Status') rendered = <span className={`${badge} ${statusClass(viewing.account_status)}`}>{viewing.account_status || '—'}</span>;
                else if (label === 'Payment Status') rendered = <span className={`${badge} ${paymentClass(viewing.payment_status)}`}>{viewing.payment_status || '—'}</span>;
                return (
                  <div key={String(label)} className="border-b border-neutral-100 py-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">{label}</p>
                    <p className="text-neutral-800">{rendered}</p>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => { setViewing(null); openEdit(viewing); }} className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90">Edit</button>
              <button type="button" onClick={() => setViewing(null)} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit modal (BRD §4.3 — modify any field) */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <form onSubmit={editFormHook.handleSubmit(onEditSubmit)} className="hms-card w-full max-w-2xl max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-neutral-900">Edit — {editing.name}</h2>
              <button type="button" onClick={() => setEditing(null)} className="material-icons text-neutral-400 hover:text-neutral-700">close</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div><label className="hms-label">ERP Customer Name</label><input className="hms-input" {...editFormHook.register('name')} /></div>
              <div><label className="hms-label">License Number (GSTIN)</label><input className="hms-input" {...editFormHook.register('gstin')} /></div>
              <div><label className="hms-label">Business Category</label><input className="hms-input" {...editFormHook.register('business_category')} /></div>
              <div><label className="hms-label">Contact Person</label><input className="hms-input" {...editFormHook.register('contact_person_name')} /></div>
              <div><label className="hms-label">Contact Number</label><input className="hms-input" {...editFormHook.register('contact_number')} /></div>
              <div><label className="hms-label">Email ID</label><input type="email" className="hms-input" {...editFormHook.register('email')} /></div>
              <div className="md:col-span-2"><label className="hms-label">Business Address (line 1)</label><input className="hms-input" {...editFormHook.register('address_line1')} /></div>
              <div><label className="hms-label">Address (line 2)</label><input className="hms-input" {...editFormHook.register('address_line2')} /></div>
              <div><label className="hms-label">City</label><input className="hms-input" {...editFormHook.register('city')} /></div>
              <div><label className="hms-label">State</label><input className="hms-input" {...editFormHook.register('state')} /></div>
              <div><label className="hms-label">Pincode</label><input className="hms-input" {...editFormHook.register('pincode')} /></div>
              <div><label className="hms-label">Country</label><input className="hms-input" {...editFormHook.register('country')} /></div>
              <div>
                <label className="hms-label">Payment Status</label>
                <select className={`hms-input font-bold capitalize ${paymentClass(editFormHook.watch('payment_status'))}`} {...editFormHook.register('payment_status')}>
                  {PAYMENT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div><label className="hms-label">Subscription Start</label><input type="date" className="hms-input" {...editFormHook.register('subscription_start_date')} /></div>
              <div><label className="hms-label">Subscription Expiry</label><input type="date" className="hms-input" {...editFormHook.register('subscription_expiry_date')} /></div>
              <div><label className="hms-label">Tenant Code</label><input className="hms-input" {...editFormHook.register('tenant_code')} /></div>
            </div>
            <p className="text-xs text-neutral-500">Plan and account status are changed from the table selectors. Subscription renewal records payment separately.</p>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setEditing(null)} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Cancel</button>
              <button type="submit" disabled={updateMutation.isPending} className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90 disabled:opacity-60">
                {updateMutation.isPending ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Service Invoice History (§8.4 Invoice History) */}
      {showHistory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-5xl max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-neutral-900">Service Invoices (Mecandria → ERP Customers)</h2>
              <button type="button" onClick={() => setShowHistory(false)} className="material-icons text-neutral-400 hover:text-neutral-700">close</button>
            </div>
            {historyQuery.isLoading && <PageLoading message="Loading invoices…" />}
            {historyQuery.isError && <PageError message="Failed to load service invoices." />}
            {historyQuery.data && historyQuery.data.service_invoices.length === 0 && <PageEmpty message="No service invoices raised yet. Use 'Raise Invoice' on a customer row." />}
            {historyQuery.data && historyQuery.data.service_invoices.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-neutral-50">
                    <tr className="text-left border-y border-neutral-200">
                      {['Invoice #', 'Customer', 'Date', 'Grand Total', 'Status', 'Payment', 'Actions'].map((h) => (
                        <th key={h} className="px-3 py-2 text-xs font-bold uppercase tracking-wider text-neutral-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {historyQuery.data.service_invoices.map((si) => (
                      <tr key={si.id} className="hover:bg-neutral-50/80">
                        <td className="px-3 py-2 font-medium">{si.invoice_number}</td>
                        <td className="px-3 py-2 text-neutral-600">{si.customer_name}</td>
                        <td className="px-3 py-2 text-neutral-600">{si.invoice_date}</td>
                        <td className="px-3 py-2 text-neutral-600">{rupees2(si.grand_total)}</td>
                        <td className="px-3 py-2"><span className={`capitalize ${si.status === 'cancelled' ? 'text-red-600' : si.status === 'paid' ? 'text-green-700' : 'text-neutral-700'}`}>{si.status}</span></td>
                        <td className="px-3 py-2 text-neutral-600 capitalize">{si.payment_status}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <button type="button" onClick={() => setPreviewInv(si)} className="rounded px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">Preview</button>
                          <button type="button" onClick={() => superAdminApi.downloadServiceInvoicePdf(si.id, si.invoice_number)} className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10">PDF</button>
                          <button type="button" onClick={() => emailInvMutation.mutate(si.id)} className="rounded px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50">Email</button>
                          {si.status !== 'paid' && si.status !== 'cancelled' && <button type="button" onClick={() => markPaidInvMutation.mutate(si.id)} className="rounded px-2 py-1 text-xs font-semibold text-green-700 hover:bg-green-50">Mark Paid</button>}
                          {si.status !== 'paid' && si.status !== 'cancelled' && <button type="button" onClick={() => { setCancelReason(''); setCancelInv(si); }} className="rounded px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50">Cancel</button>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {auditQuery.data && auditQuery.data.total > 0 && (
              <div className="flex items-center justify-between text-sm text-neutral-600">
                <span>
                  {(auditQuery.data.page - 1) * auditQuery.data.page_size + 1}
                  –{Math.min(auditQuery.data.page * auditQuery.data.page_size, auditQuery.data.total)} of {auditQuery.data.total}
                </span>
                <div className="flex gap-2">
                  <button type="button" disabled={auditPage <= 1} onClick={() => setAuditPage((p) => Math.max(1, p - 1))} className="rounded-lg border border-neutral-200 px-3 py-1.5 font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-40">Prev</button>
                  <button type="button" disabled={auditPage * AUDIT_PAGE_SIZE >= auditQuery.data.total} onClick={() => setAuditPage((p) => p + 1)} className="rounded-lg border border-neutral-200 px-3 py-1.5 font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-40">Next</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Preview a service invoice (§8.4 Preview) */}
      {previewInv && (
        <div className="fixed inset-0 z-[55] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-3xl max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-neutral-900">{previewInv.invoice_number}</h2>
              <button type="button" onClick={() => setPreviewInv(null)} className="material-icons text-neutral-400 hover:text-neutral-700">close</button>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-neutral-400">Customer:</span> {previewInv.customer_name}</div>
              <div><span className="text-neutral-400">GSTIN:</span> {previewInv.customer_gstin || '—'}</div>
              <div><span className="text-neutral-400">Date:</span> {previewInv.invoice_date}</div>
              <div><span className="text-neutral-400">Due:</span> {previewInv.due_date || '—'}</div>
              <div><span className="text-neutral-400">Supply:</span> {previewInv.supply_type}</div>
              <div><span className="text-neutral-400">Status:</span> <span className="capitalize">{previewInv.status}</span></div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-neutral-50">
                  <tr className="text-left border-y border-neutral-200">
                    {['#', 'Item', 'Description', 'HSN', 'Qty', 'Rate', 'Disc', 'Taxable', 'GST%', 'Amount'].map((h) => (
                      <th key={h} className="px-2 py-1 font-bold text-neutral-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {previewInv.items.map((it) => (
                    <tr key={it.sr_no}>
                      <td className="px-2 py-1">{it.sr_no}</td>
                      <td className="px-2 py-1">{it.item_name}{it.is_free ? ' (Free)' : ''}</td>
                      <td className="px-2 py-1 text-neutral-600">{it.description}</td>
                      <td className="px-2 py-1">{it.hsn_sac_code}</td>
                      <td className="px-2 py-1">{it.quantity}</td>
                      <td className="px-2 py-1">{rupees2(it.basic_price)}</td>
                      <td className="px-2 py-1">{rupees2(it.discount_amount)}</td>
                      <td className="px-2 py-1">{rupees2(it.taxable_amount)}</td>
                      <td className="px-2 py-1">{it.gst_rate}%</td>
                      <td className="px-2 py-1">{rupees2(it.total_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="ml-auto w-64 text-sm">
              <div className="flex justify-between"><span>Taxable</span><span>{rupees2(previewInv.total_taxable_amount)}</span></div>
              <div className="flex justify-between"><span>Total GST</span><span>{rupees2(previewInv.total_gst)}</span></div>
              <div className="flex justify-between font-bold border-t border-neutral-200 pt-1"><span>Grand Total</span><span>{rupees2(previewInv.grand_total)}</span></div>
            </div>
            {previewInv.amount_in_words && <p className="text-xs text-neutral-500">{previewInv.amount_in_words}</p>}
            {previewInv.cancel_reason && <p className="text-xs text-red-600">Cancelled: {previewInv.cancel_reason}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => superAdminApi.downloadServiceInvoicePdf(previewInv.id, previewInv.invoice_number)} className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90">Download PDF</button>
              <button type="button" onClick={() => setPreviewInv(null)} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel invoice (§8.4) */}
      {cancelInv && (
        <div className="fixed inset-0 z-[55] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-md space-y-4 p-6">
            <h2 className="font-display text-lg font-bold text-neutral-900">Cancel {cancelInv.invoice_number}</h2>
            <div><label className="hms-label">Reason *</label><textarea className="hms-input" rows={3} value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} /></div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setCancelInv(null)} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Back</button>
              <button type="button" disabled={!cancelReason.trim() || cancelInvMutation.isPending} onClick={() => cancelInvMutation.mutate({ id: cancelInv.id, reason: cancelReason.trim() })} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-60">Confirm Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Raise Service Invoice modal — Mecandria → tenant (BRD §4.3) */}
      {invoicing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-3xl max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-neutral-900">Raise Service Invoice — {invoicing.name}</h2>
              <button type="button" onClick={() => setInvoicing(null)} className="material-icons text-neutral-400 hover:text-neutral-700">close</button>
            </div>
            <p className="text-xs text-neutral-500">Mecandria subscription invoice billed to this ERP customer. Customer details are taken from the tenant profile; GST is computed by the standard engine.</p>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div><label className="hms-label">Invoice Date</label><input type="date" className="hms-input" value={invMeta.invoice_date} onChange={(e) => setInvMeta((m) => ({ ...m, invoice_date: e.target.value }))} /></div>
              <div><label className="hms-label">Due Date</label><input type="date" className="hms-input" value={invMeta.due_date} onChange={(e) => setInvMeta((m) => ({ ...m, due_date: e.target.value }))} /></div>
              <div>
                <label className="hms-label">Supply Type</label>
                <select className="hms-input" value={invMeta.supply_type} onChange={(e) => setInvMeta((m) => ({ ...m, supply_type: e.target.value }))}>
                  <option value="intra">Intra-state (CGST+SGST)</option>
                  <option value="inter">Inter-state (IGST)</option>
                </select>
              </div>
              <div><label className="hms-label">Notes</label><input className="hms-input" value={invMeta.notes} onChange={(e) => setInvMeta((m) => ({ ...m, notes: e.target.value }))} /></div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-neutral-900">Line Items</h3>
                <button type="button" onClick={() => setInvItems((arr) => [...arr, { ...blankRaiseItem }])} className="text-sm font-semibold text-primary hover:underline">+ Add item</button>
              </div>
              {invItems.map((it, idx) => (
                <div key={idx} className="grid grid-cols-2 md:grid-cols-7 gap-2 items-end border-b border-neutral-100 pb-2">
                  <div className="md:col-span-2"><label className="hms-label">Item *</label><input className="hms-input" value={it.item_name} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, item_name: e.target.value } : x))} /></div>
                  <div><label className="hms-label">HSN/SAC *</label><input className="hms-input" value={it.hsn_sac_code} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, hsn_sac_code: e.target.value } : x))} /></div>
                  <div><label className="hms-label">Qty</label><input type="number" step="0.01" className="hms-input" value={it.quantity} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, quantity: Number(e.target.value) } : x))} /></div>
                  <div><label className="hms-label">Rate ₹</label><input type="number" step="0.01" placeholder="0.00" className="hms-input" value={it.rate_rupees} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, rate_rupees: e.target.value === '' ? '' : Number(e.target.value) } : x))} /></div>
                  <div><label className="hms-label">Disc %</label><input type="number" step="0.01" placeholder="0" className="hms-input" value={it.discount_percent} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, discount_percent: e.target.value === '' ? '' : Number(e.target.value) } : x))} /></div>
                  <div>
                    <label className="hms-label">GST %</label>
                    <select className="hms-input" value={it.gst_rate} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, gst_rate: Number(e.target.value) } : x))}>
                      {GST_RATES.map((g) => <option key={g} value={g}>{g}%</option>)}
                    </select>
                  </div>
                  <div className="md:col-span-7"><label className="hms-label">Description * (incl. HSN/SAC &amp; plan period)</label><input className="hms-input" placeholder="Annual subscription | 4 Users | All GOLD Modules | 12 Months | SAC: 998313" value={it.description} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, description: e.target.value } : x))} /></div>
                  <div className="md:col-span-7 flex items-center gap-3 text-xs text-neutral-600">
                    <label className="flex items-center gap-1"><input type="checkbox" checked={it.is_free} onChange={(e) => setInvItems((arr) => arr.map((x, i) => i === idx ? { ...x, is_free: e.target.checked } : x))} /> Free (price &amp; GST = 0)</label>
                    {invItems.length > 1 && <button type="button" onClick={() => setInvItems((arr) => arr.filter((_, i) => i !== idx))} className="text-red-600 hover:underline">Remove</button>}
                  </div>
                </div>
              ))}
            </div>
            {(() => {
              // Live preview of totals (§8.4 Preview). Authoritative compute is server-side.
              const igst = invMeta.supply_type === 'inter';
              let subtotal = 0, disc = 0, taxable = 0, cgst = 0, sgst = 0, igstAmt = 0;
              invItems.forEach((it) => {
                if (it.is_free) return;
                const base = Math.round((Number(it.rate_rupees) || 0) * 100) * (Number(it.quantity) || 0);
                const d = Math.round(base * (Number(it.discount_percent) || 0) / 100);
                const t = base - d;
                subtotal += base; disc += d; taxable += t;
                if (igst) igstAmt += Math.round(t * (Number(it.gst_rate) || 0) / 100);
                else { const c = Math.round(t * (Number(it.gst_rate) || 0) / 200); cgst += c; sgst += c; }
              });
              const gst = cgst + sgst + igstAmt;
              const grand = Math.round((taxable + gst) / 100) * 100;
              return (
                <div className="ml-auto w-full md:w-72 rounded-lg border border-neutral-200 bg-neutral-50 p-3 text-sm">
                  <div className="flex justify-between"><span>Sub Total</span><span>{rupees2(subtotal)}</span></div>
                  <div className="flex justify-between"><span>Total Discount</span><span>{rupees2(disc)}</span></div>
                  <div className="flex justify-between"><span>Taxable</span><span>{rupees2(taxable)}</span></div>
                  {igst
                    ? <div className="flex justify-between"><span>IGST</span><span>{rupees2(igstAmt)}</span></div>
                    : <><div className="flex justify-between"><span>CGST</span><span>{rupees2(cgst)}</span></div><div className="flex justify-between"><span>SGST</span><span>{rupees2(sgst)}</span></div></>}
                  <div className="mt-1 flex justify-between border-t border-neutral-200 pt-1 font-bold"><span>Grand Total</span><span>{rupees2(grand)}</span></div>
                </div>
              );
            })()}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setInvoicing(null)} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Cancel</button>
              <button type="button" onClick={submitRaiseInvoice} disabled={raiseInvoiceMutation.isPending} className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90 disabled:opacity-60">{raiseInvoiceMutation.isPending ? 'Raising…' : 'Raise Invoice'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Renew Subscription modal (BRD §4.3) */}
      {renewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-md space-y-4 p-6">
            <h2 className="font-display text-lg font-bold text-neutral-900">Renew — {renewing.name}</h2>
            <div className="space-y-3">
              <div><label className="hms-label">New Start Date</label><input type="date" className="hms-input" value={renewForm.subscription_start_date} onChange={(e) => setRenewForm((f) => ({ ...f, subscription_start_date: e.target.value }))} /></div>
              <div><label className="hms-label">New Expiry Date *</label><input type="date" className="hms-input" value={renewForm.subscription_expiry_date} onChange={(e) => setRenewForm((f) => ({ ...f, subscription_expiry_date: e.target.value }))} /></div>
              <div>
                <label className="hms-label">Payment Status</label>
                <select className="hms-input" value={renewForm.payment_status} onChange={(e) => setRenewForm((f) => ({ ...f, payment_status: e.target.value }))}>
                  {PAYMENT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setRenewing(null)} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Cancel</button>
              <button type="button" onClick={submitRenew} disabled={renewMutation.isPending} className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90 disabled:opacity-60">{renewMutation.isPending ? 'Renewing…' : 'Renew'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Audit Trail modal (BRD §4.3) */}
      {auditing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-3xl max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-neutral-900">Audit Trail — {auditing.name}</h2>
              <button type="button" onClick={() => setAuditing(null)} className="material-icons text-neutral-400 hover:text-neutral-700">close</button>
            </div>
            {/* Filters */}
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label className="hms-label">User</label>
                <input className="hms-input" placeholder="Search by user…" value={auditUser} onChange={(e) => { setAuditUser(e.target.value); setAuditPage(1); }} />
              </div>
              <div>
                <label className="hms-label">From</label>
                <input type="date" className="hms-input" value={auditFrom} onChange={(e) => { setAuditFrom(e.target.value); setAuditPage(1); }} />
              </div>
              <div>
                <label className="hms-label">To</label>
                <input type="date" className="hms-input" value={auditTo} onChange={(e) => { setAuditTo(e.target.value); setAuditPage(1); }} />
              </div>
              {(auditUser || auditFrom || auditTo) && (
                <button type="button" onClick={() => { setAuditUser(''); setAuditFrom(''); setAuditTo(''); setAuditPage(1); }} className="rounded-lg border border-neutral-200 px-3 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Clear</button>
              )}
            </div>
            {auditQuery.isLoading && <PageLoading message="Loading activity…" />}
            {auditQuery.isError && <PageError message="Failed to load audit trail." />}
            {auditQuery.data && auditQuery.data.logs.length === 0 && <PageEmpty message="No activity found for these filters." />}
            {auditQuery.data && auditQuery.data.logs.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-neutral-50">
                    <tr className="text-left border-y border-neutral-200">
                      {['When', 'User', 'Module', 'Action', 'Description', 'Status'].map((h) => (
                        <th key={h} className="px-2 py-2 font-bold uppercase tracking-wider text-neutral-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {auditQuery.data.logs.map((l, i) => (
                      <tr key={i} className="hover:bg-neutral-50/80">
                        <td className="px-2 py-2 whitespace-nowrap text-neutral-600">{l.created_at ? new Date(l.created_at).toLocaleString() : '—'}</td>
                        <td className="px-2 py-2 text-neutral-700">{l.username || '—'}</td>
                        <td className="px-2 py-2 text-neutral-700">{l.module || '—'}</td>
                        <td className="px-2 py-2 text-neutral-700">{l.action_type || l.action || '—'}</td>
                        <td className="px-2 py-2 text-neutral-700 whitespace-pre-line">{l.description || '—'}</td>
                        <td className="px-2 py-2 text-neutral-700">{l.status || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {tempPassword && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-md space-y-4 p-6">
            <h2 className="font-display text-lg font-bold text-neutral-900">Temporary Admin Password</h2>
            <p className="text-sm text-neutral-600">Share this securely with <strong>{tempPassword.email}</strong>. It is shown only once.</p>
            <code className="block rounded bg-neutral-100 px-3 py-2 text-sm font-mono">{tempPassword.password}</code>
            <button type="button" onClick={() => setTempPassword(null)} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white hover:bg-primary/90">
              Done
            </button>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default SuperAdminPage;
