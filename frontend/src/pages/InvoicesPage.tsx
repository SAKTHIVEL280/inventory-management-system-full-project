/**
 * Sales Invoices Page
 * List, create, edit, issue invoices. GST-aware line items.
 */
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { salesApi, type SalesInvoice, type CreateInvoicePayload, type SalesLineItem, type SalesInvoiceItem, type InvoiceTypeValue } from '../api/sales';
import { apiClient } from '../api/client';
import { toast } from 'sonner';
import { confirmWithToast } from '../utils/toastHelper';
import { addDaysToDateInputValue, todayLocalDateInputValue } from '../utils/date';
import { emptyWhenZero } from '../utils/numberInput';

interface ProductOption { id: string; name: string; product_code: string; selling_price: number; mrp: number; gst_rate: number; hsn_code: string; description?: string; }
interface CustomerOption {
  id: string;
  company_name: string;
  customer_code: string;
  payment_terms_days?: number;
  billing_state?: string;
  billing_state_code?: string;
  billing_country?: string;
}
interface CompanyLocation { state?: string; state_code?: string; }

const INVOICE_TYPE_LABELS: Record<InvoiceTypeValue, string> = {
  export_invoice: 'Export Invoice',
  within_state: 'Sales Invoice - Within State',
  other_states: 'Sales Invoice - Other States',
  union_territory: 'Sales Invoice - Union Territory',
};

const INVOICE_TYPE_OPTIONS: Array<{ value: InvoiceTypeValue; label: string }> = [
  { value: 'export_invoice', label: INVOICE_TYPE_LABELS.export_invoice },
  { value: 'within_state', label: INVOICE_TYPE_LABELS.within_state },
  { value: 'other_states', label: INVOICE_TYPE_LABELS.other_states },
  { value: 'union_territory', label: INVOICE_TYPE_LABELS.union_territory },
];

const INDIA_INVOICE_TYPE_OPTIONS: Array<{ value: InvoiceTypeValue; label: string }> = [
  { value: 'within_state', label: INVOICE_TYPE_LABELS.within_state },
  { value: 'other_states', label: INVOICE_TYPE_LABELS.other_states },
  { value: 'union_territory', label: INVOICE_TYPE_LABELS.union_territory },
];

const EXPORT_ONLY_INVOICE_TYPE_OPTIONS: Array<{ value: InvoiceTypeValue; label: string }> = [
  { value: 'export_invoice', label: INVOICE_TYPE_LABELS.export_invoice },
];

const UNION_TERRITORY_CODES = new Set(['01', '04', '07', '26', '31', '34', '35', '37', '38']);
const UNION_TERRITORY_NAMES = new Set([
  'andaman and nicobar islands',
  'chandigarh',
  'dadra and nagar haveli and daman and diu',
  'delhi',
  'jammu and kashmir',
  'ladakh',
  'lakshadweep',
  'puducherry',
]);

const normalizeTextToken = (value?: string | null) => (value || '').trim().toLowerCase().replace(/\s+/g, ' ');
const normalizeStateCodeToken = (value?: string | null) => {
  const raw = (value || '').trim().toUpperCase();
  if (!raw) return '';
  if (/^\d+$/.test(raw)) return raw.padStart(2, '0');
  return raw;
};
const isIndiaCountry = (value?: string | null) => {
  const token = normalizeTextToken(value);
  return token === 'india' || token === 'in' || token === 'bharat' || token === 'republic of india';
};

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState<SalesInvoice | null>(null);
  const [selectedInvoiceItems, setSelectedInvoiceItems] = useState<SalesInvoiceItem[]>([]);
  const [showInvoiceDetail, setShowInvoiceDetail] = useState(false);
  const [companyLocation, setCompanyLocation] = useState<CompanyLocation | null>(null);

  const [customerId, setCustomerId] = useState('');
  const [invoiceType, setInvoiceType] = useState<InvoiceTypeValue>('within_state');
  const [importExportCode, setImportExportCode] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(todayLocalDateInputValue());
  const [dueDate, setDueDate] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<SalesLineItem[]>([]);

  const isExportInvoice = invoiceType === 'export_invoice';
  const lineItemColumnCount = isExportInvoice ? 14 : 15;
  const lineItemTotalLabelColSpan = isExportInvoice ? 12 : 13;

  const selectedCustomer = customers.find((c) => c.id === customerId);
  const selectedCustomerIsIndia = selectedCustomer ? isIndiaCountry(selectedCustomer.billing_country) : null;
  const allowedInvoiceTypeOptions = selectedCustomerIsIndia === null
    ? INVOICE_TYPE_OPTIONS
    : selectedCustomerIsIndia
      ? INDIA_INVOICE_TYPE_OPTIONS
      : EXPORT_ONLY_INVOICE_TYPE_OPTIONS;

  const invoiceTypeLabel = (value?: string) => {
    if (!value) return INVOICE_TYPE_LABELS.within_state;
    return INVOICE_TYPE_LABELS[value as InvoiceTypeValue] || INVOICE_TYPE_LABELS.within_state;
  };

  const gstColumnLabel = (type?: InvoiceTypeValue) => {
    if (type === 'other_states') return 'IGST %';
    if (type === 'union_territory') return 'GST % (CGST+UTGST)';
    return 'GST % (CGST+SGST)';
  };

  const deriveDefaultInvoiceType = (selectedCustomerId: string): InvoiceTypeValue => {
    const customer = customers.find((c) => c.id === selectedCustomerId);
    if (!customer) return 'within_state';

    if (!isIndiaCountry(customer.billing_country)) {
      return 'export_invoice';
    }

    const customerStateCode = normalizeStateCodeToken(customer.billing_state_code);
    const customerStateName = normalizeTextToken(customer.billing_state);
    if (UNION_TERRITORY_CODES.has(customerStateCode) || UNION_TERRITORY_NAMES.has(customerStateName)) {
      return 'union_territory';
    }

    const companyStateCode = normalizeStateCodeToken(companyLocation?.state_code);
    const companyStateName = normalizeTextToken(companyLocation?.state);
    if (companyStateCode && customerStateCode) {
      return companyStateCode === customerStateCode ? 'within_state' : 'other_states';
    }
    if (companyStateName && customerStateName) {
      return companyStateName === customerStateName ? 'within_state' : 'other_states';
    }

    return 'other_states';
  };

  const calculateInvoiceDueDate = (selectedCustomerId: string, selectedInvoiceDate: string) => {
    if (!selectedCustomerId || !selectedInvoiceDate) {
      return '';
    }

    const customer = customers.find((c) => c.id === selectedCustomerId);
    const paymentTermsDays = typeof customer?.payment_terms_days === 'number' && customer.payment_terms_days > 0
      ? customer.payment_terms_days
      : 0;

    return addDaysToDateInputValue(selectedInvoiceDate, paymentTermsDays);
  };

  const fetchInvoices = async () => {
    try { setLoading(true); const res = await salesApi.listInvoices(statusFilter || undefined); setInvoices(res.data.items || []); } catch { setError('Failed to load'); } finally { setLoading(false); }
  };
  const fetchMasterData = async () => {
    try {
      const [c, p, comp] = await Promise.all([
        apiClient.get('/api/v1/customers', { params: { page_size: 100 } }),
        apiClient.get('/api/v1/products', { params: { page_size: 100 } }),
        apiClient.get('/api/v1/company'),
      ]);
      setCustomers(c.data.items || []);
      setProducts(p.data.items || []);
      setCompanyLocation({ state: comp.data?.state || '', state_code: comp.data?.state_code || '' });
    } catch {
      /* */
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchInvoices should run when statusFilter changes
  useEffect(() => { fetchInvoices(); }, [statusFilter]);
  useEffect(() => { fetchMasterData(); }, []);

  const resetForm = () => { setCustomerId(''); setInvoiceType('within_state'); setImportExportCode(''); setInvoiceDate(todayLocalDateInputValue()); setDueDate(''); setNotes(''); setItems([]); setEditingId(null); setError(''); };
  const addItem = () => {
    setItems([
      ...items,
      {
        product_id: '',
        order_unit: '',
        batch_no: '',
        manufacture_date: '',
        expiry_date: '',
        quantity: 1,
        free_quantity: 0,
        unit_price: 0,
        discount_percent: 0,
        gst_rate: 18,
      },
    ]);
  };
  const paiseToRupees = (paise: number) => (Number.isFinite(paise) ? paise / 100 : 0);
  const rupeesToPaise = (value: string | number) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(num) ? Math.round(num * 100) : 0;
  };

  // SAL-025: Auto-calculate due date from customer payment terms when customer changes
  const handleCustomerChange = (newCustomerId: string) => {
    setCustomerId(newCustomerId);
    setDueDate(calculateInvoiceDueDate(newCustomerId, invoiceDate));
    setInvoiceType(deriveDefaultInvoiceType(newCustomerId));
  };

  useEffect(() => {
    if (!customerId) return;

    const customer = customers.find((c) => c.id === customerId);
    if (!customer) return;

    const customerInIndia = isIndiaCountry(customer.billing_country);
    if (!customerInIndia && invoiceType !== 'export_invoice') {
      setInvoiceType('export_invoice');
      return;
    }

    if (customerInIndia && invoiceType === 'export_invoice') {
      setInvoiceType(deriveDefaultInvoiceType(customerId));
    }
  }, [customerId, customers, invoiceType]);

  useEffect(() => {
    if (!customerId || !invoiceDate) {
      if (dueDate) {
        setDueDate('');
      }
      return;
    }

    // Wait until customer master is loaded to avoid transient blank due-date while editing.
    if (!customers.some((c) => c.id === customerId)) {
      return;
    }

    const calculatedDueDate = calculateInvoiceDueDate(customerId, invoiceDate);
    if (calculatedDueDate !== dueDate) {
      setDueDate(calculatedDueDate);
    }
  }, [customerId, invoiceDate, customers, dueDate]);

  const updateItem = (idx: number, field: keyof SalesLineItem, value: string | number) => {
    const updated = [...items]; (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    // SAL-020/022/023: Auto-fill MRP and GST from product master
    if (field === 'product_id') { const p = products.find(x => x.id === value); if (p) { updated[idx].unit_price = p.mrp || p.selling_price; updated[idx].gst_rate = p.gst_rate; } }
    setItems(updated);
  };
  const removeItem = (idx: number) => { setItems(items.filter((_, i) => i !== idx)); };
  const calcTotal = (i: SalesLineItem) => {
    const g = i.unit_price * i.quantity;
    const d = g * (i.discount_percent || 0) / 100;
    const t = g - d;
    const gstRate = isExportInvoice ? 0 : i.gst_rate;
    return Math.round(t + t * gstRate / 100);
  };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  // SAL-028: Proper status label formatting with correct capitalization
  const formatStatusLabel = (status?: string) => {
    const s = (status || 'unknown').replace('_', ' ');
    return s.charAt(0).toUpperCase() + s.slice(1);
  };
  const productById = (id: string) => products.find(p => p.id === id);

  const handleDateFromChange = (value: string) => {
    setDateFrom(value);
    if (dateTo && value && value > dateTo) {
      setDateTo(value);
    }
  };

  const handleDateToChange = (value: string) => {
    setDateTo(value);
    if (dateFrom && value && value < dateFrom) {
      setDateFrom(value);
    }
  };

  const handleSubmit = async () => {
    if (!customerId || items.length === 0) { setError('Select customer & add items'); return; }
    setSubmitting(true); setError('');
    try {
      const payload: CreateInvoicePayload = {
        customer_id: customerId, sales_order_id: undefined, invoice_date: invoiceDate,
        bill_to_customer_id: customerId,
        invoice_type: invoiceType,
        import_export_code: importExportCode.trim() || undefined,
        notes: notes || undefined,
        items: items.map(i => ({
          product_id: i.product_id,
          order_unit: i.order_unit || undefined,
          batch_no: i.batch_no || undefined,
          manufacture_date: i.manufacture_date || undefined,
          expiry_date: i.expiry_date || undefined,
          quantity: Number(i.quantity),
          free_quantity: Number(i.free_quantity || 0),
          unit_price: Number(i.unit_price),
          discount_percent: Number(i.discount_percent || 0),
          gst_rate: Number(isExportInvoice ? 0 : i.gst_rate),
        })),
      };
      if (editingId) await salesApi.updateInvoice(editingId, payload); else await salesApi.createInvoice(payload);
      setShowForm(false); resetForm(); fetchInvoices();
    } catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; setError(typeof m === 'string' ? m : 'Failed'); } finally { setSubmitting(false); }
  };

  const handleIssue = async (id: string) => {
    const confirmed = await confirmWithToast('Issue this invoice? This will deduct stock.', {
      type: 'warning',
    });
    if (!confirmed) return;
    try { await salesApi.issueInvoice(id); fetchInvoices(); }
    catch (err: unknown) {
      const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof m === 'string' ? m : 'Issue failed');
    }
  };

  const handleDownloadPDF = async (inv: SalesInvoice) => {
    try {
      toast.info('Generating PDF...');
      const response = await salesApi.downloadInvoicePdf(inv.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Invoice-${inv.invoice_number}.pdf`);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      link.remove();
      toast.success('PDF downloaded successfully');
    } catch {
      toast.error('Failed to download PDF');
    }
  };

  const handleViewInvoice = async (inv: SalesInvoice) => {
    try {
      const { data } = await salesApi.getInvoice(inv.id);
      setSelectedInvoice(data.invoice || inv);
      setSelectedInvoiceItems(data.items || []);
      setShowInvoiceDetail(true);
    } catch {
      setSelectedInvoice(inv);
      setSelectedInvoiceItems([]);
      setShowInvoiceDetail(true);
    }
  };

  const customerNameById = (customerId: string) => {
    return customers.find((c) => c.id === customerId)?.company_name || 'Unknown customer';
  };
  const productNameById = (productId: string) => {
    return products.find((p) => p.id === productId)?.name || productId;
  };

  const filteredInvoices = invoices.filter((inv) => {
    const q = searchQuery.trim().toLowerCase();
    const customerName = customerNameById(inv.customer_id).toLowerCase();
    const matchesSearch =
      !q ||
      inv.invoice_number.toLowerCase().includes(q) ||
      customerName.includes(q) ||
      inv.status.toLowerCase().includes(q) ||
      inv.invoice_date.toLowerCase().includes(q) ||
      (inv.due_date || '').toLowerCase().includes(q);
    const matchesFrom = !dateFrom || inv.invoice_date >= dateFrom;
    const matchesTo = !dateTo || inv.invoice_date <= dateTo;
    return matchesSearch && matchesFrom && matchesTo;
  });

  const sc: Record<string, string> = { draft: 'bg-gray-100 text-gray-700', issued: 'bg-blue-100 text-blue-700', partial_paid: 'bg-amber-100 text-amber-700', paid: 'bg-green-100 text-green-700', cancelled: 'bg-red-100 text-red-700' };

  return (
    <AppLayout title="Sales Invoices">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All</option><option value="draft">Draft</option><option value="issued">Issued</option><option value="partial_paid">Partial Paid</option><option value="paid">Paid</option><option value="cancelled">Cancelled</option>
            </select>
            <input
              type="text"
              className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              placeholder="Search invoice #, customer, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">From</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(e) => handleDateFromChange(e.target.value)}
                title="Invoice date from"
              />
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(e) => handleDateToChange(e.target.value)}
                title="Invoice date to"
              />
            </div>
          </div>
          <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ New Invoice</button>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Invoice Number</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Customer</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Invoice Type</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Due Date</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Due</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : filteredInvoices.length === 0 ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">No invoices</td></tr>
                : filteredInvoices.map(inv => (
                  <tr key={inv.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-3">{customerNameById(inv.customer_id)}</td>
                    <td className="px-4 py-3">{invoiceTypeLabel(inv.invoice_type)}</td>
                    <td className="px-4 py-3">{inv.invoice_date}</td>
                    <td className="px-4 py-3">{inv.due_date || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(inv.total_amount)}</td>
                    <td className="px-4 py-3 text-right font-medium text-red-600">{inv.amount_due > 0 ? formatAmount(inv.amount_due) : '-'}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[inv.status] || 'bg-gray-100'}`}>{formatStatusLabel(inv.status)}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button onClick={() => handleViewInvoice(inv)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">View</button>
                        {inv.status === 'draft' && <button onClick={() => handleIssue(inv.id)} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Issue</button>}
                        <button
                          onClick={() => handleDownloadPDF(inv)}
                          className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-white px-2.5 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                          title="Download PDF"
                        >
                          <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                          Download PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Showing {filteredInvoices.length} of {invoices.length}</p>}
        </div>

        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-2 sm:p-4 backdrop-blur-sm">
            <div className="hms-card my-4 sm:my-8 w-[min(96vw,1500px)] max-w-none space-y-6 p-4 sm:p-6">
              <h2 className="font-display text-xl font-bold">{editingId ? 'Modify/Change' : 'New'} Invoice</h2>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              
              {!editingId && (
                <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-600">
                  Invoice creation is independent of Sales Order auto-fill.
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
                {/* SAL-025: Customer select triggers due date auto-calc */}
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={customerId} onChange={e => handleCustomerChange(e.target.value)}><option value="">Select</option>{customers.map(c => <option key={c.id} value={c.id}>{c.company_name} ({c.customer_code})</option>)}</select></div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Invoice Type *</label>
                  <select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={invoiceType} onChange={e => setInvoiceType(e.target.value as InvoiceTypeValue)}>
                    {allowedInvoiceTypeOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                  </select>
                  {!isExportInvoice && <p className="mt-1 text-xs text-neutral-500">Applied Tax Type: {gstColumnLabel(invoiceType).replace(' %', '')}</p>}
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Import &amp; Export Code</label>
                  <input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={importExportCode} onChange={e => setImportExportCode(e.target.value)} placeholder="Optional" />
                </div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Invoice Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)} /></div>
                {/* SAL-029: Due Date is fully auto-calculated for invoices */}
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Due Date <span className="text-xs text-neutral-400">(auto from payment terms)</span></label><input type="date" className="w-full rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-600" value={dueDate} readOnly disabled /></div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Items</h3><button onClick={addItem} className="rounded bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">+ Add</button></div>
                <div className="overflow-x-auto rounded-lg border border-neutral-200">
                  <table className="w-full min-w-[1600px] table-fixed text-sm">
                    <thead>
                      <tr className="bg-neutral-50">
                        <th className="w-[18%] px-3 py-2 text-left">Product</th>
                        <th className="w-[8%] px-3 py-2 text-left">Product ID</th>
                        <th className="w-[10%] px-3 py-2 text-left">Description</th>
                        <th className="w-[8%] px-3 py-2 text-left">Order Unit</th>
                        <th className="w-[8%] px-3 py-2 text-left">Batch</th>
                        <th className="w-[8%] px-3 py-2 text-left">MFG Date</th>
                        <th className="w-[8%] px-3 py-2 text-left">EXP Date</th>
                        <th className="w-[7%] px-3 py-2 text-left">HSN</th>
                        <th className="w-16 px-3 py-2 text-right">Qty</th>
                        <th className="w-16 px-3 py-2 text-right">Free</th>
                        <th className="w-28 px-3 py-2 text-right">MRP (₹)</th>
                        <th className="w-16 px-3 py-2 text-right">Disc %</th>
                        {!isExportInvoice && <th className="w-28 px-3 py-2 text-right">{gstColumnLabel(invoiceType)}</th>}
                        <th className="w-28 px-3 py-2 text-right">Total</th>
                        <th className="w-20 px-3 py-2 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => {
                        const prod = productById(item.product_id);
                        return (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2">
                            <select className="w-full rounded border px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                              <option value="">Select</option>
                              {products.map(p => <option key={p.id} value={p.id}>{p.name} ({p.product_code})</option>)}
                            </select>
                          </td>
                          {/* SAL-013: Product ID column */}
                          <td className="px-3 py-2 text-xs text-neutral-500 font-mono">{prod?.product_code || '-'}</td>
                          {/* SAL-014: Description column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.description || prod?.name || '-'}</td>
                          <td className="px-3 py-2">
                            <input type="text" className="w-full rounded border px-2 py-1.5 text-sm" value={item.order_unit || ''} onChange={e => updateItem(idx, 'order_unit', e.target.value)} placeholder="e.g. Box" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="text" className="w-full rounded border px-2 py-1.5 text-sm" value={item.batch_no || ''} onChange={e => updateItem(idx, 'batch_no', e.target.value)} placeholder="Batch" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className="w-full rounded border px-2 py-1.5 text-sm" value={item.manufacture_date || ''} onChange={e => updateItem(idx, 'manufacture_date', e.target.value)} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className="w-full rounded border px-2 py-1.5 text-sm" value={item.expiry_date || ''} onChange={e => updateItem(idx, 'expiry_date', e.target.value)} />
                          </td>
                          {/* SAL-021: HSN Code column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.hsn_code || '-'}</td>
                          <td className="px-3 py-2">
                            <input type="number" min="0.01" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.quantity} onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={emptyWhenZero(item.free_quantity)} onChange={e => updateItem(idx, 'free_quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          {/* SAL-020: MRP auto-fills from Product Master */}
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.unit_price ? paiseToRupees(item.unit_price) : ''} onChange={e => updateItem(idx, 'unit_price', rupeesToPaise(e.target.value))} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" max="100" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={emptyWhenZero(item.discount_percent)} onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} />
                          </td>
                          {!isExportInvoice && (
                            <td className="px-3 py-2">
                              <select className="w-full min-w-[60px] rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-900 appearance-auto" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
                                <option value={0}>0%</option>
                                <option value={5}>5%</option>
                                <option value={12}>12%</option>
                                <option value={18}>18%</option>
                                <option value={28}>28%</option>
                              </select>
                            </td>
                          )}
                          <td className="px-3 py-2 text-right font-medium">{formatAmount(calcTotal(item))}</td>
                          <td className="px-3 py-2 text-right">
                            <button onClick={() => removeItem(idx)} className="inline-flex items-center gap-1 whitespace-nowrap text-red-500">
                              <span className="material-icons text-sm" aria-hidden="true">delete_outline</span>Remove
                            </button>
                          </td>
                        </tr>
                        );
                      })}
                  {items.length === 0 && <tr><td colSpan={lineItemColumnCount} className="px-3 py-4 text-center text-neutral-400">No items</td></tr>}
                    </tbody>
                    {items.length > 0 && (
                      <tfoot>
                        <tr className="border-t-2 bg-neutral-50">
                          <td colSpan={lineItemTotalLabelColSpan} className="px-3 py-2 text-right font-semibold">Total:</td>
                          <td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(items.reduce((s, i) => s + calcTotal(i), 0))}</td>
                          <td></td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </div>
              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Saving...' : editingId ? 'Update' : 'Create Invoice'}</button>
              </div>
            </div>
          </div>,
          document.body
        )}

        {showInvoiceDetail && selectedInvoice && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm" onClick={() => setShowInvoiceDetail(false)}>
            <div className="hms-card my-8 w-full max-w-3xl space-y-6 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">Invoice: {selectedInvoice.invoice_number}</h2>
                  <p className="mt-1 text-sm text-neutral-600">Customer: {customers.find(c => c.id === selectedInvoice.customer_id)?.company_name || '-'}</p>
                </div>
                <div className="flex items-center gap-2">
                  {/* SAL-027: Edit button in Invoice View for draft invoices */}
                  {selectedInvoice.status === 'draft' && (
                    <button
                      onClick={() => {
                        setShowInvoiceDetail(false);
                        // Load into edit form
                        setEditingId(selectedInvoice.id);
                        setCustomerId(selectedInvoice.customer_id);
                        setInvoiceType((selectedInvoice.invoice_type as InvoiceTypeValue) || deriveDefaultInvoiceType(selectedInvoice.customer_id));
                        setImportExportCode(selectedInvoice.import_export_code || '');
                        setInvoiceDate(selectedInvoice.invoice_date);
                        setDueDate(selectedInvoice.due_date || '');
                        setNotes(selectedInvoice.notes || '');
                        setItems(selectedInvoiceItems.map(i => ({
                          product_id: i.product_id,
                          order_unit: i.order_unit || '',
                          batch_no: i.batch_no || '',
                          manufacture_date: i.manufacture_date || '',
                          expiry_date: i.expiry_date || '',
                          quantity: i.quantity,
                          free_quantity: i.free_quantity || 0,
                          unit_price: i.unit_price,
                          discount_percent: i.discount_percent || 0,
                          gst_rate: i.gst_rate,
                        })));
                        setShowForm(true);
                      }}
                      className="inline-flex items-center gap-1 rounded-lg border border-primary bg-primary/5 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10"
                    >
                      <span className="material-icons text-sm" aria-hidden="true">edit</span>
                      Edit Invoice
                    </button>
                  )}
                  <button
                    onClick={() => handleDownloadPDF(selectedInvoice)}
                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                  >
                    <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                    Download PDF
                  </button>
                  <button onClick={() => setShowInvoiceDetail(false)} className="text-2xl text-neutral-400 hover:text-neutral-600">&times;</button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 rounded-lg bg-neutral-50 p-4 md:grid-cols-5">
                <div>
                  <p className="text-xs text-neutral-600">Invoice Date</p>
                  <p className="font-medium">{selectedInvoice.invoice_date}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Due Date</p>
                  <p className="font-medium">{selectedInvoice.due_date || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Invoice Type</p>
                  <p className="font-medium">{invoiceTypeLabel(selectedInvoice.invoice_type)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Status</p>
                  <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[selectedInvoice.status] || 'bg-gray-100'}`}>
                    {formatStatusLabel(selectedInvoice.status)}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Total</p>
                  <p className="font-semibold">{formatAmount(selectedInvoice.total_amount)}</p>
                </div>
              </div>

              {selectedInvoice.import_export_code && (
                <div className="rounded-lg border border-neutral-200 p-3">
                  <p className="text-xs text-neutral-600">Import &amp; Export Code</p>
                  <p className="font-medium text-neutral-800">{selectedInvoice.import_export_code}</p>
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 rounded-lg border border-neutral-200 p-4 md:grid-cols-3">
                <div>
                  <p className="text-xs text-neutral-600">Subtotal</p>
                  <p className="font-medium">{formatAmount(selectedInvoice.subtotal)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Amount Paid</p>
                  <p className="font-medium text-green-700">{formatAmount(selectedInvoice.amount_paid)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Amount Due</p>
                  <p className="font-medium text-red-600">{selectedInvoice.amount_due > 0 ? formatAmount(selectedInvoice.amount_due) : '-'}</p>
                </div>
              </div>

              {selectedInvoice.notes && (
                <div>
                  <p className="mb-1 text-xs text-neutral-600">Notes</p>
                  <p className="rounded-lg bg-neutral-50 p-3 text-sm text-neutral-700">{selectedInvoice.notes}</p>
                </div>
              )}

              {selectedInvoiceItems.length > 0 && (
                <div>
                  <p className="mb-2 text-sm font-semibold text-neutral-700">Items</p>
                  <div className="overflow-x-auto rounded-lg border border-neutral-200">
                    <table className="w-full min-w-[700px] text-sm">
                      <thead>
                        <tr className="bg-neutral-50">
                          <th className="px-3 py-2 text-left">Product</th>
                          <th className="px-3 py-2 text-right">Qty</th>
                          <th className="px-3 py-2 text-right">Unit Price</th>
                          <th className="px-3 py-2 text-right">Discount %</th>
                          {selectedInvoice.invoice_type !== 'export_invoice' && <th className="px-3 py-2 text-right">{gstColumnLabel(selectedInvoice.invoice_type)}</th>}
                          <th className="px-3 py-2 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedInvoiceItems.map((item) => (
                          <tr key={item.id} className="border-t border-neutral-100">
                            <td className="px-3 py-2">{item.description || productNameById(item.product_id)}</td>
                            <td className="px-3 py-2 text-right">{item.quantity}</td>
                            <td className="px-3 py-2 text-right">{formatAmount(item.unit_price)}</td>
                            <td className="px-3 py-2 text-right">{item.discount_percent || 0}</td>
                            {selectedInvoice.invoice_type !== 'export_invoice' && <td className="px-3 py-2 text-right">{item.gst_rate}</td>}
                            <td className="px-3 py-2 text-right font-medium">{formatAmount(item.total_amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="flex justify-end">
                <button onClick={() => setShowInvoiceDetail(false)} className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold hover:bg-neutral-50">
                  Close
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppLayout>
  );
};

export default InvoicesPage;

