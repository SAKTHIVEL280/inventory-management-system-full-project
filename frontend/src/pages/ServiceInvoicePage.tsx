import { useState } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading, PageEmpty } from '../components/PageState';
import { PaymentStatusBadge } from '../components/PaymentStatusBadge';
import { serviceInvoiceApi, ServiceInvoicePayload, ServiceInvoice } from '../api/serviceInvoice';

const rupees = (paise: number | undefined) =>
  paise == null ? '—' : `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

// Color-coded invoice lifecycle status (draft/issued/paid/cancelled). Presentational only.
const invoiceStatusClass = (status?: string | null): string => {
  switch ((status || '').trim().toLowerCase()) {
    case 'paid': return 'bg-green-100 text-green-700';
    case 'issued': return 'bg-blue-100 text-blue-700';
    case 'cancelled': return 'bg-red-100 text-red-700';
    default: return 'bg-neutral-100 text-neutral-600'; // draft / unknown
  }
};

type ItemForm = {
  item_name: string;
  hsn_sac_code?: string;
  quantity: number;
  basic_price_rupees?: number;
  discount_percent?: number;
  gst_rate: number;
  is_free: boolean;
};

type CreateForm = {
  invoice_date: string;
  due_date?: string;
  customer_name: string;
  customer_gstin?: string;
  customer_email?: string;
  customer_contact?: string;
  billing_address?: string;
  supply_type: string;
  items: ItemForm[];
};

const blankItem: ItemForm = {
  item_name: '', hsn_sac_code: '', quantity: 1, basic_price_rupees: undefined,
  discount_percent: undefined, gst_rate: 18, is_free: false,
};

const ServiceInvoicePage = () => {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [viewing, setViewing] = useState<ServiceInvoice | null>(null);

  const form = useForm<CreateForm>({
    defaultValues: {
      invoice_date: new Date().toISOString().slice(0, 10),
      supply_type: 'intra',
      customer_name: '',
      items: [{ ...blankItem }],
    },
  });
  const { fields, append, remove } = useFieldArray({ control: form.control, name: 'items' });

  const listQuery = useQuery({ queryKey: ['service-invoices'], queryFn: () => serviceInvoiceApi.list() });
  const capQuery = useQuery({ queryKey: ['service-invoices', 'cap'], queryFn: serviceInvoiceApi.capStatus });

  const createMutation = useMutation({
    mutationFn: (payload: ServiceInvoicePayload) => serviceInvoiceApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['service-invoices'] });
      setShowCreate(false);
      form.reset();
      toast.success('Service invoice created.');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => serviceInvoiceApi.cancel(id, 'Cancelled by user'),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['service-invoices'] }); toast.success('Cancelled.'); },
  });

  const markPaidMutation = useMutation({
    mutationFn: (id: string) => serviceInvoiceApi.markPaid(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['service-invoices'] }); toast.success('Marked paid.'); },
  });

  const onCreate = (values: CreateForm) => {
    const payload: ServiceInvoicePayload = {
      invoice_date: values.invoice_date,
      due_date: values.due_date || null,
      customer_name: values.customer_name,
      customer_gstin: values.customer_gstin || null,
      customer_email: values.customer_email,
      customer_contact: values.customer_contact,
      billing_address: values.billing_address,
      supply_type: values.supply_type,
      items: values.items.map((it) => ({
        item_name: it.item_name,
        hsn_sac_code: it.hsn_sac_code,
        quantity: Number(it.quantity) || 0,
        basic_price: Math.round((Number(it.basic_price_rupees) || 0) * 100), // rupees → paise
        discount_percent: Number(it.discount_percent) || 0,
        gst_rate: Number(it.gst_rate) || 0,
        is_free: !!it.is_free,
      })),
    };
    createMutation.mutate(payload);
  };

  const cap = capQuery.data;
  const invoices = listQuery.data?.service_invoices ?? [];

  return (
    <AppLayout title="Service Invoices">
      {cap?.capped && (
        <div className={`mb-4 rounded-lg border p-4 text-sm ${
          (cap.remaining ?? 0) <= 2 ? 'border-amber-300 bg-amber-50 text-amber-800' : 'border-neutral-200 bg-neutral-50 text-neutral-700'
        }`}>
          <strong>FREE plan:</strong> {cap.used_this_month}/{cap.cap} service invoices used this month
          {(cap.remaining ?? 0) <= 2 && ' — approaching your monthly limit. Upgrade for unlimited invoices.'}
        </div>
      )}

      <div className="hms-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-4">
          <h2 className="font-display text-lg font-bold text-neutral-900">Service Invoices</h2>
          <button
            type="button"
            onClick={() => setShowCreate((v) => !v)}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90"
          >
            {showCreate ? 'Close' : 'New Service Invoice'}
          </button>
        </div>

        {showCreate && (
          <form onSubmit={form.handleSubmit(onCreate)} className="space-y-4 border-b border-neutral-200 p-5 bg-neutral-50/60">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div><label className="hms-label">Invoice Date *</label><input type="date" className="hms-input" {...form.register('invoice_date', { required: true })} /></div>
              <div><label className="hms-label">Due Date</label><input type="date" className="hms-input" {...form.register('due_date')} /></div>
              <div><label className="hms-label">Customer Name *</label><input className="hms-input" {...form.register('customer_name', { required: true })} /></div>
              <div><label className="hms-label">Customer GSTIN</label><input className="hms-input" placeholder="29ABCDE1234F1Z5 (if registered)" {...form.register('customer_gstin')} /></div>
              <div><label className="hms-label">Email *</label><input type="email" className="hms-input" {...form.register('customer_email', { required: true })} /></div>
              <div>
                <label className="hms-label">Contact * (10-digit mobile)</label>
                <input
                  className="hms-input"
                  inputMode="numeric"
                  maxLength={14}
                  placeholder="e.g. 9876543210"
                  {...form.register('customer_contact', {
                    required: 'Contact number is required',
                    validate: (v) => {
                      let d = String(v || '').replace(/[\s\-()]/g, '').replace(/^\+/, '');
                      if (d.length === 12 && d.startsWith('91')) d = d.slice(2);
                      else if (d.length === 11 && d.startsWith('0')) d = d.slice(1);
                      return /^[6-9]\d{9}$/.test(d)
                        || 'Enter a valid 10-digit mobile number starting with 6-9 (numbers starting with 0-5 are not allowed).';
                    },
                  })}
                />
                {form.formState.errors.customer_contact && (
                  <p className="mt-1 text-xs text-danger">{form.formState.errors.customer_contact.message as string}</p>
                )}
              </div>
              <div>
                <label className="hms-label">Supply Type</label>
                <select className="hms-input" {...form.register('supply_type')}>
                  <option value="intra">Intra-state (CGST+SGST)</option>
                  <option value="inter">Inter-state (IGST)</option>
                </select>
              </div>
              <div className="md:col-span-3"><label className="hms-label">Billing Address *</label><input className="hms-input" {...form.register('billing_address', { required: true })} /></div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-neutral-900">Line Items</h3>
                <button type="button" onClick={() => append({ ...blankItem })} className="text-sm font-semibold text-primary hover:underline">+ Add item</button>
              </div>
              <div className="space-y-2">
                {fields.map((f, idx) => (
                  <div key={f.id} className="grid grid-cols-2 md:grid-cols-7 gap-2 items-end">
                    <div className="md:col-span-2"><label className="hms-label">Item *</label><input className="hms-input" {...form.register(`items.${idx}.item_name` as const, { required: true })} /></div>
                    <div><label className="hms-label">HSN/SAC *</label><input className="hms-input" placeholder="998313" {...form.register(`items.${idx}.hsn_sac_code` as const, { required: true })} /></div>
                    <div><label className="hms-label">Qty</label><input type="number" step="0.01" className="hms-input" {...form.register(`items.${idx}.quantity` as const)} /></div>
                    <div><label className="hms-label">Rate ₹</label><input type="number" step="0.01" placeholder="0.00" className="hms-input" {...form.register(`items.${idx}.basic_price_rupees` as const)} /></div>
                    <div><label className="hms-label">Disc %</label><input type="number" step="0.01" placeholder="0" className="hms-input" {...form.register(`items.${idx}.discount_percent` as const)} /></div>
                    <div className="flex items-center gap-2">
                      <select className="hms-input" {...form.register(`items.${idx}.gst_rate` as const)}>
                        {[0, 5, 12, 18, 28].map((r) => <option key={r} value={r}>{r}%</option>)}
                      </select>
                      {fields.length > 1 && (
                        <button type="button" onClick={() => remove(idx)} className="text-danger text-xs font-semibold">✕</button>
                      )}
                    </div>
                    <label className="md:col-span-7 flex items-center gap-2 text-xs text-neutral-600">
                      <input type="checkbox" {...form.register(`items.${idx}.is_free` as const)} /> Free item (price &amp; GST = 0)
                    </label>
                  </div>
                ))}
              </div>
            </div>

            <button type="submit" disabled={createMutation.isPending} className="rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white hover:bg-primary/90 disabled:opacity-60">
              {createMutation.isPending ? 'Saving…' : 'Create Service Invoice'}
            </button>
          </form>
        )}

        <div className="p-5">
          {listQuery.isLoading && <PageLoading message="Loading service invoices..." />}
          {listQuery.isError && <PageError message="Failed to load service invoices" />}
          {!listQuery.isLoading && invoices.length === 0 && <PageEmpty message="No service invoices yet." />}
          {invoices.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-neutral-50">
                  <tr className="text-left border-y border-neutral-200">
                    {['Number', 'Date', 'Customer', 'Total', 'Status', 'Payment', 'Actions'].map((h) => (
                      <th key={h} className="px-3 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-neutral-50/80">
                      <td className="px-3 py-3 font-medium">{inv.invoice_number}</td>
                      <td className="px-3 py-3 text-neutral-600">{inv.invoice_date}</td>
                      <td className="px-3 py-3">{inv.customer_name}</td>
                      <td className="px-3 py-3 font-medium">{rupees(inv.grand_total)}</td>
                      <td className="px-3 py-3"><span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${invoiceStatusClass(inv.status)}`}>{inv.status}</span></td>
                      <td className="px-3 py-3"><PaymentStatusBadge status={inv.payment_status} /></td>
                      <td className="px-3 py-3">
                        <div className="flex gap-2">
                          <button type="button" onClick={() => setViewing(inv)} className="rounded px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">View</button>
                          <button type="button" onClick={() => serviceInvoiceApi.downloadPdf(inv.id, inv.invoice_number)} className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10">Download</button>
                          {inv.status !== 'paid' && inv.status !== 'cancelled' && (
                            <button type="button" onClick={() => markPaidMutation.mutate(inv.id)} className="rounded px-2 py-1 text-xs font-semibold text-success hover:bg-green-50">Mark Paid</button>
                          )}
                          {inv.status !== 'cancelled' && (
                            <button type="button" onClick={() => cancelMutation.mutate(inv.id)} className="rounded px-2 py-1 text-xs font-semibold text-danger hover:bg-red-50">Cancel</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {viewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-3xl max-h-[90vh] overflow-y-auto space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-neutral-900">{viewing.invoice_number}</h2>
              <button type="button" onClick={() => setViewing(null)} className="material-icons text-neutral-400 hover:text-neutral-700">close</button>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-neutral-400">Customer:</span> {viewing.customer_name}</div>
              <div><span className="text-neutral-400">GSTIN:</span> {viewing.customer_gstin || '—'}</div>
              <div><span className="text-neutral-400">Date:</span> {viewing.invoice_date}</div>
              <div><span className="text-neutral-400">Due:</span> {viewing.due_date || '—'}</div>
              <div><span className="text-neutral-400">Supply:</span> {viewing.supply_type === 'inter' ? 'Inter-state (IGST)' : 'Intra-state (CGST+SGST)'}</div>
              <div className="flex items-center gap-2"><span className="text-neutral-400">Status:</span> <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${invoiceStatusClass(viewing.status)}`}>{viewing.status}</span></div>
              <div className="flex items-center gap-2"><span className="text-neutral-400">Payment:</span> <PaymentStatusBadge status={viewing.payment_status} size="sm" /></div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-neutral-50">
                  <tr className="text-left border-y border-neutral-200">
                    {['#', 'Item', 'HSN/SAC', 'Qty', 'Rate', 'Disc', 'Taxable', 'GST%', 'Amount'].map((h) => (
                      <th key={h} className="px-2 py-1 font-bold text-neutral-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {viewing.items.map((it) => (
                    <tr key={it.sr_no}>
                      <td className="px-2 py-1">{it.sr_no}</td>
                      <td className="px-2 py-1">{it.item_name}{it.is_free ? ' (Free)' : ''}</td>
                      <td className="px-2 py-1">{it.hsn_sac_code}</td>
                      <td className="px-2 py-1">{it.quantity}</td>
                      <td className="px-2 py-1">{rupees(it.basic_price)}</td>
                      <td className="px-2 py-1">{rupees(it.discount_amount)}</td>
                      <td className="px-2 py-1">{rupees(it.taxable_amount)}</td>
                      <td className="px-2 py-1">{it.gst_rate}%</td>
                      <td className="px-2 py-1">{rupees(it.total_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="ml-auto w-64 text-sm">
              <div className="flex justify-between"><span>Taxable</span><span>{rupees(viewing.total_taxable_amount)}</span></div>
              <div className="flex justify-between"><span>Total GST</span><span>{rupees(viewing.total_gst)}</span></div>
              <div className="flex justify-between font-bold border-t border-neutral-200 pt-1"><span>Grand Total</span><span>{rupees(viewing.grand_total)}</span></div>
            </div>
            {viewing.amount_in_words && <p className="text-xs text-neutral-500">{viewing.amount_in_words}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => serviceInvoiceApi.downloadPdf(viewing.id, viewing.invoice_number)} className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary/90">Download PDF</button>
              <button type="button" onClick={() => setViewing(null)} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">Close</button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default ServiceInvoicePage;
